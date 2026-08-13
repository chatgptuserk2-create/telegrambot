"""
ربات تلگرام برای سفارش‌گیری در گروه

دستورات گروه:
  /menu      - نمایش منوی آیتم‌های قابل سفارش
  /order     - ثبت سفارش جدید (مثال: /order یک قهوه)
  /orders    - نمایش تمام سفارش‌های ثبت‌شده

دستورات خصوصی (فقط DM):
  /start     - معرفی ربات
  /setgroup  - تنظیم آیدی گروه دستی
  /setmenu   - آیتم جدید به منو اضافه کن
  /removemenu - آیتم از منو حذف کن
  /viewmenu  - نمایش منوی فعلی
  /open      - اعلام شروع تهیه آیتم در گروه
  /ready     - آمادگی آیتم + درخواست عکس برای گروه
  /message   - ارسال پیام به گروه
"""
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import storage

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = 7985483389

# فایل برای ذخیره‌ی state
PENDING_FILE = os.path.join(os.path.dirname(__file__), "pending.json")
GROUP_FILE = os.path.join(os.path.dirname(__file__), "group.json")


def load_pending():
    if not os.path.exists(PENDING_FILE):
        return {}
    with open(PENDING_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_pending(data):
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_group():
    if not os.path.exists(GROUP_FILE):
        return {}
    with open(GROUP_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_group(data):
    with open(GROUP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def set_group_id(group_id):
    """آیدی گروه رو ذخیره می‌کنه"""
    data = load_group()
    data["group_id"] = group_id
    save_group(data)


def get_group_id():
    """آیدی گروه رو برمی‌گردونه"""
    data = load_group()
    return data.get("group_id")


# ---------- سرور سلامت ----------

class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass


def _run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    logger.info(f"سرور سلامت روی پورت {port} بالا اومد")
    server.serve_forever()


# ---------- دستورات ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    
    await update.message.reply_text(
        "👋 سلام! من یک **دستیار شخصی** هستم که در گروه‌های شما سفارش می‌گیرم.\n\n"
        "وقتی مرا به یک گروه اضافه کنید، می‌توانید از دستورات زیر استفاده کنید:\n\n"
        "📋 **/menu** - نمایش لیست آیتم‌های قابل سفارش\n"
        "🛒 **/order** - ثبت سفارش جدید (مثال: `/order یک قهوه`)\n"
        "📝 **/orders** - نمایش تمام سفارش‌های ثبت‌شده\n\n"
        "از هر یک از این دستورات در گروه استفاده کنید تا شروع کنیم! 😊",
        parse_mode="Markdown"
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu = storage.load_menu()
    
    if not menu:
        await update.message.reply_text("❌ منو خالیه.")
        return
    
    message = "🍽 **منو:**\n\n"
    for item, price in menu.items():
        message += f"{item} - {price:,} تومان\n"
    
    message += "\n💡 برای سفارش، از دستور `/order` استفاده کنید."
    await update.message.reply_text(message, parse_mode="Markdown")


async def order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ لطفاً سفارش خود را مشخص کنید.\n\nمثال: `/order یک قهوه`",
            parse_mode="Markdown"
        )
        return
    
    order_text = " ".join(context.args)
    user_name = update.effective_user.first_name or "کاربر"
    
    order_id = storage.add_order(update.effective_chat.id, order_text, user_name)
    
    # ذخیره‌ی آیدی گروه (اولین بار)
    if not get_group_id():
        set_group_id(update.effective_chat.id)
    
    await update.message.reply_text(
        f"✅ سفارش ثبت شد!\n\n"
        f"👤 {user_name}\n"
        f"🛒 سفارش: {order_text}\n"
        f"📍 شماره سفارش: #{order_id}",
        parse_mode="Markdown"
    )
    
    try:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"📢 **سفارش جدید!**\n\n"
                 f"👤 {user_name}\n"
                 f"🛒 {order_text}\n"
                 f"📍 شماره: #{order_id}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"خطا در ارسال پیام به صاحب: {e}")


async def orders_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    orders = storage.list_orders(update.effective_chat.id)
    
    if not orders:
        await update.message.reply_text("📭 هنوز سفارشی ثبت نشده.")
        return
    
    message = "📋 **تمام سفارش‌ها:**\n\n"
    
    for order in orders:
        message += f"#{order['id']} | {order['timestamp']}\n"
        message += f"👤 {order['user']}: {order['text']}\n\n"
    
    message += f"✅ **کل سفارش‌ها: {len(orders)} عدد**"
    
    await update.message.reply_text(message, parse_mode="Markdown")


async def help_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "🤖 **دستیار سفارش‌گیری**\n\n"
        "دستورات موجود:\n\n"
        "📋 **/menu** - لیست آیتم‌های قابل سفارش\n"
        "🛒 **/order [سفارش شما]** - ثبت سفارش جدید\n"
        "📝 **/orders** - نمایش تمام سفارش‌های ثبت‌شده\n\n"
        "💡 مثال: `/order یک قهوه و یک کیک`"
    )
    await update.message.reply_text(message, parse_mode="Markdown")


# ---------- دستورات مدیریت منو (فقط DM) ----------

async def setmenu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("❌ این دستور فقط در پیام شخصی کار می‌کنه.")
        return
    
    if len(context.args) < 2 or not context.args[-1].isdigit():
        await update.message.reply_text(
            "❌ فرمت درست: `/setmenu [نام آیتم] [قیمت]`\n\nمثال: `/setmenu قهوه سیاه 15000`",
            parse_mode="Markdown"
        )
        return
    
    price = int(context.args[-1])
    item_name = " ".join(context.args[:-1])
    
    if storage.add_menu_item(item_name, price):
        await update.message.reply_text(
            f"✅ آیتم اضافه شد!\n\n{item_name} - {price:,} تومان",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(f"❌ این آیتم قبلاً در منو وجود داره.")


async def removemenu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("❌ این دستور فقط در پیام شخصی کار می‌کنه.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ لطفاً نام آیتم رو بنویس.\n\nمثال: `/removemenu قهوه سیاه`",
            parse_mode="Markdown"
        )
        return
    
    item_name = " ".join(context.args)
    
    if storage.remove_menu_item(item_name):
        await update.message.reply_text(f"✅ آیتم حذف شد: {item_name}")
    else:
        await update.message.reply_text(f"❌ این آیتم در منو وجود نداره.")


async def viewmenu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("❌ این دستور فقط در پیام شخصی کار می‌کنه.")
        return
    
    menu = storage.load_menu()
    
    if not menu:
        await update.message.reply_text("❌ منو خالیه.")
        return
    
    message = "📋 **منوی فعلی:**\n\n"
    for item, price in menu.items():
        message += f"{item} - {price:,} تومان\n"
    
    await update.message.reply_text(message, parse_mode="Markdown")


# ---------- دستورات /open، /ready، /message ----------

async def open_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اعلام شروع تهیه آیتم در گروه"""
    if update.effective_chat.type != "private":
        await update.message.reply_text("❌ این دستور فقط در پیام شخصی کار می‌کنه.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ لطفاً نام آیتم رو بنویس.\n\nمثال: `/open قهوه`",
            parse_mode="Markdown"
        )
        return
    
    item_name = " ".join(context.args)
    group_id = get_group_id()
    
    if not group_id:
        await update.message.reply_text("❌ هنوز هیچ گروهی ثبت نشده.")
        return
    
    try:
        await context.bot.send_message(
            chat_id=group_id,
            text=f"🍳 **در حال تهیه:** {item_name}",
            parse_mode="Markdown"
        )
        
        await update.message.reply_text(
            f"✅ اعلام فرستادم!\n\n🍳 در حال تهیه: {item_name}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"خطا در ارسال پیام: {e}")
        await update.message.reply_text("❌ خطایی رخ داد.")


async def ready_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """آمادگی آیتم + درخواست عکس"""
    if update.effective_chat.type != "private":
        await update.message.reply_text("❌ این دستور فقط در پیام شخصی کار می‌کنه.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ لطفاً نام آیتم رو بنویس.\n\nمثال: `/ready قهوه`",
            parse_mode="Markdown"
        )
        return
    
    item_name = " ".join(context.args)
    user_id = str(update.effective_user.id)
    
    pending = load_pending()
    pending[user_id] = {
        "item_name": item_name,
        "state": "waiting_for_image"
    }
    save_pending(pending)
    
    await update.message.reply_text(
        f"📸 لطفاً عکس {item_name} رو بفرست",
        parse_mode="Markdown"
    )


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت عکس برای ready"""
    user_id = str(update.effective_user.id)
    pending = load_pending()
    
    if user_id not in pending or pending[user_id].get("state") != "waiting_for_image":
        await update.message.reply_text("❌ شما هیچ درخواست منتظری ندارید.")
        return
    
    item_name = pending[user_id]["item_name"]
    group_id = get_group_id()
    photo_file_id = update.message.photo[-1].file_id
    
    try:
        await context.bot.send_photo(
            chat_id=group_id,
            photo=photo_file_id,
            caption=f"✅ **{item_name} آماده هست!**",
            parse_mode="Markdown"
        )
        
        await update.message.reply_text(
            f"✅ عکس {item_name} برای گروه فرستاده شد!",
            parse_mode="Markdown"
        )
        
        del pending[user_id]
        save_pending(pending)
        
    except Exception as e:
        logger.error(f"خطا در ارسال عکس: {e}")
        await update.message.reply_text("❌ خطایی رخ داد.")


async def message_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ارسال پیام به گروه"""
    if update.effective_chat.type != "private":
        await update.message.reply_text("❌ این دستور فقط در پیام شخصی کار می‌کنه.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ لطفاً پیام رو بنویس.\n\nمثال: `/message سلام! ما بسته هستیم`",
            parse_mode="Markdown"
        )
        return
    
    message_text = " ".join(context.args)
    group_id = get_group_id()
    
    if not group_id:
        await update.message.reply_text("❌ هنوز هیچ گروهی ثبت نشده.")
        return
    
    try:
        await context.bot.send_message(
            chat_id=group_id,
            text=message_text,
            parse_mode="Markdown"
        )
        
        await update.message.reply_text(
            f"✅ پیام برای گروه فرستاده شد!",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"خطا در ارسال پیام: {e}")
        await update.message.reply_text("❌ خطایی رخ داد.")


async def setgroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنظیم آیدی گروه دستی"""
    if update.effective_chat.type != "private":
        await update.message.reply_text("❌ این دستور فقط در پیام شخصی کار می‌کنه.")
        return
    
    if not context.args or not context.args[0].lstrip('-').isdigit():
        await update.message.reply_text(
            "❌ لطفاً آیدی گروه رو بنویس.\n\nمثال: `/setgroup -1004343833443`",
            parse_mode="Markdown"
        )
        return
    
    group_id = int(context.args[0])
    set_group_id(group_id)
    
    await update.message.reply_text(
        f"✅ گروه تنظیم شد!\n\nآیدی: `{group_id}`",
        parse_mode="Markdown"
    )


# ---------- اجرای ربات ----------

def main():
    if not BOT_TOKEN:
        raise RuntimeError("متغیر محیطی BOT_TOKEN تنظیم نشده.")

    threading.Thread(target=_run_health_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("order", order_command))
    app.add_handler(CommandHandler("orders", orders_list))
    app.add_handler(CommandHandler("help", help_group))
    app.add_handler(CommandHandler("setmenu", setmenu_command))
    app.add_handler(CommandHandler("removemenu", removemenu_command))
    app.add_handler(CommandHandler("viewmenu", viewmenu_command))
    app.add_handler(CommandHandler("open", open_command))
    app.add_handler(CommandHandler("ready", ready_command))
    app.add_handler(CommandHandler("message", message_command))
    app.add_handler(CommandHandler("setgroup", setgroup_command))
    
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_image))

    logger.info("ربات در حال اجراست...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

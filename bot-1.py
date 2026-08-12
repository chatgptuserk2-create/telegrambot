"""
ربات تلگرام برای سفارش‌گیری در گروه

دستورات گروه:
  /menu      - نمایش منوی آیتم‌های قابل سفارش
  /order     - ثبت سفارش جدید (مثال: /order یک قهوه)
  /orders    - نمایش تمام سفارش‌های ثبت‌شده

دستورات خصوصی (فقط DM):
  /start     - معرفی ربات
  /setmenu   - آیتم جدید به منو اضافه کن
  /removemenu - آیتم از منو حذف کن
  /viewmenu  - نمایش منوی فعلی (برای مدیریت)
"""
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

import storage

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = 7985483389  # شماره‌ی شخصی تو


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
    """فقط توی DM (پیام شخصی) جواب می‌ده"""
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
    """نمایش منو"""
    menu = storage.load_menu()
    
    if not menu:
        await update.message.reply_text("❌ منو خالیه، هنوز آیتمی اضافه نشده.")
        return
    
    message = "🍽 **منو:**\n\n"
    for item, price in menu.items():
        message += f"{item} - {price:,} تومان\n"
    
    message += "\n💡 برای سفارش، از دستور `/order` استفاده کنید."
    await update.message.reply_text(message, parse_mode="Markdown")


async def order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ثبت سفارش جدید"""
    if not context.args:
        await update.message.reply_text(
            "❌ لطفاً سفارش خود را مشخص کنید.\n\n"
            "مثال: `/order یک قهوه` یا `/order دو کاپ‌کیک و یک کرواسان`",
            parse_mode="Markdown"
        )
        return
    
    order_text = " ".join(context.args)
    user_name = update.effective_user.first_name or "کاربر"
    
    order_id = storage.add_order(update.effective_chat.id, order_text, user_name)
    
    # تایید در گروه
    await update.message.reply_text(
        f"✅ سفارش ثبت شد!\n\n"
        f"👤 {user_name}\n"
        f"🛒 سفارش: {order_text}\n"
        f"📍 شماره سفارش: #{order_id}",
        parse_mode="Markdown"
    )
    
    # ارسال پیام به صاحب (OWNER)
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
    """نمایش تمام سفارش‌ها"""
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
    """راهنمای گروه"""
    message = (
        "🤖 **دستیار سفارش‌گیری**\n\n"
        "دستورات موجود:\n\n"
        "📋 **/menu** - لیست آیتم‌های قابل سفارش\n"
        "🛒 **/order [سفارش شما]** - ثبت سفارش جدید\n"
        "📝 **/orders** - نمایش تمام سفارش‌های ثبت‌شده\n\n"
        "💡 مثال: `/order یک قهوه و یک کیک`"
    )
    await update.message.reply_text(message, parse_mode="Markdown")


# ---------- دستورات مدیریت منو (فقط در DM) ----------

async def setmenu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """آیتم جدید به منو اضافه کن (فقط DM)"""
    if update.effective_chat.type != "private":
        await update.message.reply_text("❌ این دستور فقط در پیام شخصی کار می‌کنه.")
        return
    
    if len(context.args) < 2 or not context.args[-1].isdigit():
        await update.message.reply_text(
            "❌ فرمت درست: `/setmenu [نام آیتم] [قیمت]`\n\n"
            "مثال: `/setmenu قهوه سیاه 15000`",
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
        await update.message.reply_text(
            f"❌ این آیتم قبلاً در منو وجود داره.",
            parse_mode="Markdown"
        )


async def removemenu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """آیتم از منو حذف کن (فقط DM)"""
    if update.effective_chat.type != "private":
        await update.message.reply_text("❌ این دستور فقط در پیام شخصی کار می‌کنه.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ لطفاً نام آیتم رو بنویس.\n\n"
            "مثال: `/removemenu قهوه سیاه`",
            parse_mode="Markdown"
        )
        return
    
    item_name = " ".join(context.args)
    
    if storage.remove_menu_item(item_name):
        await update.message.reply_text(
            f"✅ آیتم حذف شد: {item_name}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"❌ این آیتم در منو وجود نداره.",
            parse_mode="Markdown"
        )


async def viewmenu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش منوی فعلی برای مدیریت (فقط DM)"""
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
    
    message += "\n💡 برای اضافه کردن: `/setmenu [نام] [قیمت]`\n"
    message += "💡 برای حذف کردن: `/removemenu [نام]`"
    
    await update.message.reply_text(message, parse_mode="Markdown")


# ---------- اجرای ربات ----------

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "متغیر محیطی BOT_TOKEN تنظیم نشده."
        )

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

    logger.info("ربات در حال اجراست...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

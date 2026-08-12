"""
ماژول ساده برای ذخیره‌سازی سفارش‌ها و منو روی فایل JSON.
"""
import json
import os
from threading import Lock
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
MENU_FILE = os.path.join(os.path.dirname(__file__), "menu.json")
_lock = Lock()


def _load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_order(chat_id: int, order_text: str, user_name: str = "ناشناس") -> int:
    """یک سفارش جدید اضافه می‌کنه و شماره‌ی (id) اون رو برمی‌گردونه."""
    with _lock:
        data = _load_data()
        chat_key = str(chat_id)
        orders = data.get(chat_key, [])
        new_id = (max([o["id"] for o in orders], default=0)) + 1
        orders.append({
            "id": new_id,
            "text": order_text,
            "user": user_name,
            "timestamp": datetime.now().strftime("%H:%M")
        })
        data[chat_key] = orders
        _save_data(data)
        return new_id


def list_orders(chat_id: int):
    with _lock:
        data = _load_data()
        return data.get(str(chat_id), [])


# ---------- مدیریت منو ----------

def load_menu() -> dict:
    """منو رو از فایل می‌خونه"""
    with _lock:
        if not os.path.exists(MENU_FILE):
            return {}
        with open(MENU_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}


def save_menu(menu: dict):
    """منو رو در فایل ذخیره می‌کنه"""
    with _lock:
        with open(MENU_FILE, "w", encoding="utf-8") as f:
            json.dump(menu, f, ensure_ascii=False, indent=2)


def add_menu_item(item_name: str, price: int) -> bool:
    """آیتم جدید به منو اضافه می‌کنه"""
    menu = load_menu()
    if item_name in menu:
        return False  # آیتم قبلاً وجود داره
    menu[item_name] = price
    save_menu(menu)
    return True


def remove_menu_item(item_name: str) -> bool:
    """آیتم رو از منو حذف می‌کنه"""
    menu = load_menu()
    if item_name not in menu:
        return False  # آیتم وجود نداره
    del menu[item_name]
    save_menu(menu)
    return True

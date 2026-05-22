from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from core.config import settings

def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍️ Открыть магазин", web_app=WebAppInfo(url=settings.mini_app_url))],
            [KeyboardButton(text="📜 История заказов")]
        ],
        resize_keyboard=True,
    )
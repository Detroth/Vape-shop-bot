from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

def get_main_menu_keyboard(web_app_url: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Открыть магазин", web_app=WebAppInfo(url=web_app_url))],
            [KeyboardButton(text="📜 История заказов")]
        ],
        resize_keyboard=True,
        is_persistent=True
    )
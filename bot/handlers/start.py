from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards import get_main_menu_keyboard

start_router = Router()

@start_router.message(CommandStart())
async def cmd_start(message: Message):
    # В будущем URL лучше вынести в core/config.py
    web_app_url = "https://your-mini-app-domain.com"
    
    await message.answer(
        "Привет! Добро пожаловать в наш вейп-шоп 💨\n\n"
        "Нажми кнопку ниже, чтобы открыть магазин и сделать заказ.",
        reply_markup=get_main_menu_keyboard(web_app_url)
    )
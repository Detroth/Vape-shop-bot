from aiogram import Router, F, html
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards import get_main_keyboard

start_router = Router()

@start_router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        f"Привет, {html.bold(message.from_user.full_name)}! Добро пожаловать в наш современный вейп-шоп 💨\n\n"
        "Нажми кнопку ниже, чтобы открыть магазин и сделать заказ.",
        reply_markup=get_main_keyboard()
    )

@start_router.message(F.text == "📜 История заказов")
async def history_stub(message: Message):
    await message.answer(
        "У вас пока нет оформленных заказов. Чтобы сделать заказ, откройте наш Web-магазин! 👇",
        reply_markup=get_main_keyboard()
    )
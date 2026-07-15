import os
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from core.config import settings

# Получаем адрес прокси из переменных окружения
telegram_proxy = os.getenv("TELEGRAM_PROXY")

if telegram_proxy:
    session = AiohttpSession(proxy=telegram_proxy, timeout=30.0)
else:
    session = AiohttpSession(timeout=30.0)

# Инициализируем бота с настроенной сессией и parse_mode HTML
bot = Bot(
    token=settings.bot_token,
    session=session,
    default=DefaultBotProperties(parse_mode="HTML")
)

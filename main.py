import asyncio
import logging
import uvicorn
from fastapi import FastAPI
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from core.config import settings
from core.database import init_db
from bot.handlers.start import start_router
from bot.handlers.admin import admin_router

# Импорт роутеров API
from api.routes import api_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Инициализация FastAPI
app = FastAPI(title="Vape Shop API", version="1.0.0")

# Регистрация эндпоинтов Mini App
app.include_router(api_router, prefix="/api")

# Инициализация бота и диспетчера
bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# Регистрация хэндлеров бота
dp.include_router(start_router)
dp.include_router(admin_router)

@app.get("/health", tags=["System"])
async def health_check():
    """Простейший эндпоинт для проверки жизнеспособности (Railway healthcheck)."""
    return {"status": "ok"}

@app.on_event("startup")
async def on_startup():
    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("Запуск Telegram-бота в фоновом режиме (polling)...")
    # Запускаем polling бота параллельно с FastAPI сервером
    asyncio.create_task(dp.start_polling(bot))

if __name__ == "__main__":
    # Запуск сервера uvicorn на порту из конфигурации
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=False)
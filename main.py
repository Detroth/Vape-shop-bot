import asyncio
import logging
import uvicorn
from fastapi import FastAPI
from aiogram import Bot, Dispatcher
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from aiogram.client.default import DefaultBotProperties
from sqladmin import Admin

from core.config import settings
from core.database import init_db, engine, async_session_maker, setup_initial_database
from bot.handlers.start import start_router
from bot.handlers.admin import admin_router
from api.admin_panel import authentication_backend, UserAdmin, CategoryAdmin, ProductAdmin, OrderAdmin, PromocodeAdmin

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

# Настройка CORS для локального тестирования
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Регистрация эндпоинтов Mini App
app.include_router(api_router, prefix="/api")

app.mount("/store", StaticFiles(directory="web", html=True), name="store")

# Настройка визуальной админ-панели (SQLAdmin)
admin = Admin(app, engine, authentication_backend=authentication_backend, title="Vape Shop Admin")
admin.add_view(UserAdmin)
admin.add_view(CategoryAdmin)
admin.add_view(ProductAdmin)
admin.add_view(OrderAdmin)
admin.add_view(PromocodeAdmin)

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
    
    logger.info("Проверка и наполнение начальными данными...")
    async with async_session_maker() as session:
        await setup_initial_database(session)
        
    logger.info("Запуск Telegram-бота в фоновом режиме (polling)...")
    # Запускаем polling бота параллельно с FastAPI сервером
    asyncio.create_task(dp.start_polling(bot))

if __name__ == "__main__":
    # Запуск сервера uvicorn на порту из конфигурации
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=False)
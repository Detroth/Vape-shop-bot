import asyncio
import re
import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from aiogram import Bot, Dispatcher
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from aiogram.client.default import DefaultBotProperties

from core.config import settings
from core.database import init_db, engine, async_session_maker, setup_initial_database, Base
from sqlalchemy import text
from bot.handlers.start import start_router
from bot.handlers.admin import admin_router
from api.admin_panel import setup_admin

# Импорт роутеров API
from api.routes import api_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Маскируем пароль регулярным выражением для безопасного вывода в логи
    safe_url = re.sub(r":([^:@]+)@", r":******@", settings.database_url)
    logger.info(f"Попытка подключения к БД по адресу: {safe_url}")
    
    logger.info("Инициализация базы данных...")
    try:
        await init_db()
        
        logger.info("Проверка и наполнение начальными данными...")
        async with async_session_maker() as session:
            await setup_initial_database(session)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при инициализации БД: {e}")
        raise e
        
    logger.info("Запуск Telegram-бота в фоновом режиме (polling)...")
    # Запускаем polling бота параллельно с FastAPI сервером
    polling_task = asyncio.create_task(dp.start_polling(bot))
    
    yield
    
    logger.info("Остановка приложения...")
    polling_task.cancel()
    await bot.session.close()

# Инициализация FastAPI
app = FastAPI(title="Vape Shop API", version="1.0.0", lifespan=lifespan)

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

# Инициализация современной админ-панели (FastAPI Amis Admin)
setup_admin(app)

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

@app.get("/db-status", tags=["System"])
async def db_status_check():
    """Диагностический эндпоинт для проверки реального состояния базы данных."""
    try:
        async with engine.connect() as conn:
            # Запрашиваем у самого PostgreSQL список реально существующих таблиц
            result = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public';"))
            tables = [row[0] for row in result.fetchall()]
            
            return {"status": "ok", "tables_in_postgres": tables, "models_in_app": list(Base.metadata.tables.keys())}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# Монтируем статику в корень (ДОЛЖНО БЫТЬ В САМОМ НИЗУ, чтобы не перекрыть /api и /admin)
app.mount("/", StaticFiles(directory="web", html=True), name="web")

if __name__ == "__main__":
    # Передаем объект app напрямую, чтобы избежать двойного импорта файла и ошибки "Router is already attached"
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
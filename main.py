import asyncio
import re
import os
import logging
import uvicorn
from contextlib import asynccontextmanager
from aiogram import Dispatcher, BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, Update
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from bot.create_bot import bot

from core.config import settings
from core.database import init_db, engine, async_session_maker, setup_initial_database, Base
from sqlalchemy import text
from bot.handlers.start import start_router
from bot.handlers.admin import admin_router
from api.admin_panel import setup_admin

from api.routes import api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
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
        
    webhook_url = f"{settings.mini_app_url}/api/bot/webhook"
    logger.info(f"Установка webhook для бота на URL: {webhook_url}")
    try:
        await bot.set_webhook(url=webhook_url)
    except Exception as e:
        logger.error(f"❌ Не удалось установить webhook: {e}")
    
    yield
    
    logger.info("Удаление webhook...")
    try:
        await bot.delete_webhook()
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении webhook: {e}")
    
    logger.info("Закрытие сессии бота...")
    await bot.session.close()

app = FastAPI(title="Vape Shop API", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def check_maintenance(request: Request, call_next):
    if os.path.exists("maintenance.lock"):
        path = request.url.path
        if not path.startswith("/health") and not path.startswith("/admin") and not path.startswith("/db-status"):
            return JSONResponse(
                status_code=503,
                content={"status": "maintenance", "message": "Сервис временно недоступен."}
            )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

setup_admin(app)

dp = Dispatcher()

class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        if os.path.exists("maintenance.lock"):
            from_user = getattr(event, "from_user", None)
            user_id = from_user.id if from_user else None
            if user_id not in (settings.bot_chat_id, settings.admin_main_id, settings.yookassa_test_id):
                if isinstance(event, Message):
                    await event.answer("⚠️ Бот временно недоступен.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("⚠️ Сервис временно недоступен.", show_alert=True)
                return
        return await handler(event, data)

dp.message.outer_middleware(MaintenanceMiddleware())
dp.callback_query.outer_middleware(MaintenanceMiddleware())

dp.include_router(start_router)
dp.include_router(admin_router)

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok"}

@app.post("/api/bot/webhook")
async def telegram_webhook(update: dict, request: Request):
    # Передаем пришедший апдейт напрямую в диспетчер aiogram
    tg_update = Update.model_validate(update, context={"bot": bot})
    await dp.feed_update(bot, tg_update)
    return {"status": "ok"}

@app.get("/db-status", tags=["System"])
async def db_status_check():
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public';"))
            tables = [row[0] for row in result.fetchall()]
            
            return {"status": "ok", "tables_in_postgres": tables, "models_in_app": list(Base.metadata.tables.keys())}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/config", tags=["System"])
async def get_public_config():
    return {"support_account": os.getenv("SUPPORT_ACCOUNT", "")}

app.mount("/", StaticFiles(directory="web", html=True), name="web")

if __name__ == "__main__":
    port = int(os.getenv("PORT", settings.port))
    uvicorn.run(app, host="0.0.0.0", port=port)
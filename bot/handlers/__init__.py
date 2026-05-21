from aiogram import Router

from .start import start_router
from .admin import admin_router

def get_routers() -> list[Router]:
    """Возвращает список всех роутеров бота для регистрации в Dispatcher."""
    return [start_router, admin_router]
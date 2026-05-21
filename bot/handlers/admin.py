from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command

admin_router = Router()

# Пример: команда, доступная только в админском чате или админам
@admin_router.message(Command("admin"))
async def cmd_admin(message: Message):
    await message.answer("Панель администратора. Здесь будут доступны отчеты и настройки.")

# Утилита для вызова из FastAPI эндпоинта (api/routes/orders.py)
async def notify_new_order(bot: Bot, admin_chat_id: int, order_id: int, total_price: float):
    """Отправляет уведомление о новом заказе в рабочий чат."""
    text = (
        f"🚨 <b>Новый заказ!</b>\n"
        f"ID заказа: #{order_id}\n"
        f"Сумма: {total_price} руб.\n\n"
        f"Детали можно посмотреть в админке или базе."
    )
    # Используем HTML для форматирования жирного текста
    await bot.send_message(chat_id=admin_chat_id, text=text, parse_mode="HTML")
import asyncio
from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError

from core.database import async_session_maker
from core.models import Order, OrderStatus, Product, User
from core.config import settings

admin_router = Router()

class BroadcastStates(StatesGroup):
    waiting_for_message = State()

# Пример: команда, доступная только в админском чате или админам
@admin_router.message(Command("admin"))
async def cmd_admin(message: Message):
    await message.answer("Панель администратора. Здесь будут доступны отчеты и настройки.")

# Утилита для вызова из FastAPI эндпоинта (api/routes/orders.py)
async def notify_new_order(bot: Bot, admin_chat_id: int, order_id: int, username: str, user_id: int, items_text: str, address: str, total_price: float):
    """Отправляет уведомление о новом заказе в рабочий чат."""
    text = (
        f"🚨 <b>Новый заказ №{order_id}!</b>\n"
        f"👤 Клиент: {username} (ID: {user_id})\n"
        f"📦 Товар(ы):\n{items_text}\n"
        f"📍 Адрес: {address}\n"
        f"💰 Итого: {total_price} Br"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Доставлен", callback_data=f"deliver_{order_id}")]
    ])
    
    await bot.send_message(chat_id=admin_chat_id, text=text, reply_markup=keyboard, parse_mode="HTML")

@admin_router.callback_query(F.data.startswith("deliver_"))
async def process_deliver_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    
    try:
        async with async_session_maker() as session:
            async with session.begin():
                result = await session.execute(
                    select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
                )
                order = result.scalar_one_or_none()
                
                if not order:
                    await callback.answer("Заказ не найден!", show_alert=True)
                    return
                    
                if order.status == OrderStatus.DELIVERED:
                    await callback.answer("Заказ уже доставлен!", show_alert=True)
                    return
                    
                if order.status in (OrderStatus.PENDING, OrderStatus.PAID):
                    for item in order.items:
                        if item.product_id:
                            prod_res = await session.execute(select(Product).where(Product.id == item.product_id))
                            product = prod_res.scalar_one()
                            
                            if product.stock < item.quantity:
                                await callback.message.answer(f"❌ Ошибка! Недостаточно товара {product.name} на складе!")
                                await callback.answer()
                                raise ValueError("Insufficient stock")  # Вызовет автоматический rollback транзакции
                                
                            product.stock -= item.quantity
                            
                    order.status = OrderStatus.DELIVERED
                    
        # Выполнится только если транзакция завершена успешно и зафиксирована
        await callback.message.edit_text(f"Заказ №{order_id} успешно доставлен. Остатки списаны. ✅")
        await callback.answer()
    except ValueError:
        pass # Транзакция прервана из-за нехватки товара

@admin_router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    # Проверка на права администратора
    if message.from_user.id != settings.admin_chat_id:
        return
        
    await message.answer("Отправьте сообщение для рассылки (текст и/или фото):")
    await state.set_state(BroadcastStates.waiting_for_message)

@admin_router.message(BroadcastStates.waiting_for_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    # Сохраняем ID сообщения и чата, чтобы скопировать его (с сохранением форматирования и медиа)
    await state.update_data(msg_id=message.message_id, from_chat_id=message.chat.id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚀 Запустить", callback_data="broadcast_start"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")
        ]
    ])
    
    # Отправляем предпросмотр сообщения админу
    await message.copy_to(chat_id=message.chat.id, reply_markup=keyboard)

@admin_router.callback_query(F.data == "broadcast_cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❌ Рассылка отменена.")
    await callback.answer()

@admin_router.callback_query(F.data == "broadcast_start")
async def start_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    msg_id = data.get("msg_id")
    from_chat_id = data.get("from_chat_id")
    
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("🚀 Рассылка запущена! Это может занять некоторое время...")
    await callback.answer()
    
    success_count = 0
    error_count = 0
    
    async with async_session_maker() as session:
        result = await session.execute(select(User.telegram_id))
        user_ids = result.scalars().all()
        
    for uid in user_ids:
        try:
            await bot.copy_message(chat_id=uid, from_chat_id=from_chat_id, message_id=msg_id)
            success_count += 1
        except (TelegramForbiddenError, TelegramAPIError):
            error_count += 1
            
        await asyncio.sleep(0.05) # Защита от Rate Limit
        
    await callback.message.answer(f"✅ Рассылка завершена.\nУспешно отправлено: {success_count}\nОшибок (блок): {error_count}")
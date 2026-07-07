import asyncio
import tempfile
import json
import os
import enum
from datetime import datetime
from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command, BaseFilter
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError
from decimal import Decimal

from core.database import async_session_maker
from core.models import (
    Order, OrderStatus, Product, User, Category, OrderItem,
    Promocode, FortunePrize, FortuneHistory, UserBonus, DeliveryTime
)
from core.config import settings

class BotAdminFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if not settings.bot_chat_id or not settings.yookassa_test_id:
            return False
        return message.from_user.id == settings.bot_chat_id

def model_to_dict(model_instance) -> dict:
    if not model_instance:
        return None
    d = {}
    for column in model_instance.__table__.columns:
        val = getattr(model_instance, column.name)
        if isinstance(val, Decimal):
            d[column.name] = float(val)
        elif isinstance(val, datetime):
            d[column.name] = val.isoformat()
        elif isinstance(val, enum.Enum):
            d[column.name] = val.value
        else:
            d[column.name] = val
    return d

admin_router = Router()

class BroadcastStates(StatesGroup):
    waiting_for_message = State()

@admin_router.message(Command("admin"))
async def cmd_admin(message: Message):
    await message.answer("Панель администратора. Здесь будут доступны отчеты и настройки.")

async def notify_new_order(
    bot: Bot, admin_chat_id: int, order_id: int, client_name: str, client_phone: str, 
    tg_username: str, delivery_type: str, payment_method: str, address: str, comment: str, items_text: str, 
    total_price: float, paid_from_balance: float = 0.0, promo_code_used: str = None,
    delivery_date: str = None, delivery_time: str = None
):
    """Отправляет уведомление о новом заказе в рабочий чат."""
    if delivery_type == "delivery":
        delivery_str = "Доставка"
    elif delivery_type == "paid":
        delivery_str = "Платная доставка"
    else:
        delivery_str = "Самовывоз"
        
    addr_str = address if address else "Самовывоз"
    comment_str = comment if comment else "Нет"
    promo_str = f" (Применен код: {promo_code_used})" if promo_code_used else ""
    tg_username_str = tg_username if tg_username else "скрыт"
    
    date_str = f"📅 <b>Дата:</b> {delivery_date}\n" if delivery_date else ""
    time_str = f"⏰ <b>Время:</b> {delivery_time}\n" if delivery_time else ""

    if payment_method == "card":
        payment_str = "💳 Картой"
    else:
        payment_str = "💵 Наличными"

    status_text = "✅ Оплачен (с баланса)" if total_price - paid_from_balance <= 0 else "⏳ Ожидает оплаты"
    balance_str = f"\n💳 <b>Списано с баланса:</b> {paid_from_balance:.2f} Br" if paid_from_balance > 0 else ""
    to_pay = total_price - paid_from_balance

    text = (
        f"📦 <b>ПОСТУПИЛ НОВЫЙ ЗАКАЗ №{order_id}</b> [{status_text}]\n"
        f"---------------------------------\n"
        f"🛒 <b>Товары:</b>\n"
        f"{items_text}\n"
        f"---------------------------------\n"
        f"👤 <b>Клиент:</b> {client_name}\n"
        f"📞 <b>Телефон:</b> {client_phone}\n"
        f"✈️ <b>Telegram:</b> @{tg_username_str}\n\n"
        f"⚙️ <b>Тип доставки:</b> {delivery_str}\n"
        f"📍 <b>Адрес:</b> {addr_str}\n"
        f"{date_str}{time_str}"
        f"💳 <b>Оплата:</b> {payment_str}\n"
        f"💬 <b>Комментарий:</b> {comment_str}\n"
        f"---------------------------------\n"
        f"💰 <b>Сумма заказа:</b> {total_price:.2f} Br{promo_str}{balance_str}\n"
        f"💵 <b>Итого к оплате:</b> {to_pay:.2f} Br"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Доставлен", callback_data=f"deliver_{order_id}")]
    ])
    
    await bot.send_message(chat_id=admin_chat_id, text=text, reply_markup=keyboard, parse_mode="HTML")

@admin_router.callback_query(F.data.startswith("deliver_"))
async def process_deliver_order(callback: CallbackQuery, bot: Bot):
    order_id = int(callback.data.split("_")[1])
    
    try:
        async with async_session_maker() as session:
            async with session.begin():
                result = await session.execute(
                    select(Order).options(selectinload(Order.items)).where(Order.id == order_id).with_for_update()
                )
                order = result.scalar_one_or_none()
                
                if not order:
                    await callback.answer("Заказ не найден!", show_alert=True)
                    return
                    
                if order.status in (OrderStatus.DELIVERED, OrderStatus.CANCELED):
                    await callback.answer("Этот заказ уже обработан!", show_alert=True)
                    await callback.message.edit_reply_markup(reply_markup=None)
                    return
                    
                if order.status in (OrderStatus.PENDING, OrderStatus.PAID):
                    for item in order.items:
                        if item.product_id:
                            prod_res = await session.execute(
                                select(Product).where(Product.id == item.product_id).with_for_update()
                            )
                            product = prod_res.scalar_one()
                            
                            if product.stock < item.quantity:
                                await callback.message.answer(f"❌ Ошибка! Невозможно доставить заказ №{order_id}, так как товара {product.name} нет в наличии в нужном количестве!")
                                await callback.answer()
                                raise ValueError("Insufficient stock") 
                                
                            product.stock -= item.quantity
                            
                    order.status = OrderStatus.DELIVERED
                
                user_id = order.user_id
                    
        original_text = callback.message.html_text or f"Заказ №{order_id}"
        await callback.message.edit_text(f"{original_text}\n\n✅ <b>Заказ №{order_id} успешно выполнен, остатки списаны.</b>", reply_markup=None)
        await callback.answer()
        
        try:
            await bot.send_message(
                chat_id=user_id,
                text=f"🎉 Ваш заказ №{order_id} успешно доставлен! Приятного использования!"
            )
        except Exception:
            pass 
            
    except ValueError:
        pass 

@admin_router.callback_query(F.data.startswith("deposit_confirm_"))
async def process_deposit_confirm(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split("_")
    user_id = int(parts[2])
    amount = Decimal(parts[3])
    
    try:
        async with async_session_maker() as session:
            async with session.begin():
                result = await session.execute(
                    select(User).where(User.telegram_id == user_id).with_for_update()
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    await callback.answer("Пользователь не найден!", show_alert=True)
                    return
                    
                user.balance += amount
                username = user.username or str(user_id)
        
        await callback.message.edit_text(f"✅ Пополнение на {amount:.2f} Br для @{username} одобрено.", reply_markup=None)
        await callback.answer()
        
        try:
            await bot.send_message(
                chat_id=user_id,
                text=f"💳 Ваш баланс успешно пополнен на {amount:.2f} Br!"
            )
        except Exception:
            pass
    except Exception:
        await callback.answer("Ошибка при пополнении!", show_alert=True)

@admin_router.callback_query(F.data.startswith("deposit_reject_"))
async def process_deposit_reject(callback: CallbackQuery):
    await callback.message.edit_text("❌ Заявка на пополнение отклонена.", reply_markup=None)
    await callback.answer()

@admin_router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != settings.admin_main_id:
        return
        
    await message.answer("Отправьте сообщение для рассылки (текст и/или фото):")
    await state.set_state(BroadcastStates.waiting_for_message)

@admin_router.message(BroadcastStates.waiting_for_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    await state.update_data(msg_id=message.message_id, from_chat_id=message.chat.id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚀 Запустить", callback_data="broadcast_start"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")
        ]
    ])
    
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
            
        await asyncio.sleep(0.05) 
        
    await callback.message.answer(f"✅ Рассылка завершена.\nУспешно отправлено: {success_count}\nОшибок (блок): {error_count}")

@admin_router.message(Command("backup"), BotAdminFilter())
async def cmd_backup(message: Message):
    status_msg = await message.answer("⌛ Подготовка резервной копии базы данных...")
    try:
        async with async_session_maker() as session:
            users_res = await session.execute(select(User))
            categories_res = await session.execute(select(Category))
            products_res = await session.execute(select(Product))
            orders_res = await session.execute(select(Order))
            items_res = await session.execute(select(OrderItem))
            promo_res = await session.execute(select(Promocode))
            prizes_res = await session.execute(select(FortunePrize))
            history_res = await session.execute(select(FortuneHistory))
            bonuses_res = await session.execute(select(UserBonus))
            delivery_res = await session.execute(select(DeliveryTime))

            backup_data = {
                "backup_created_at": datetime.now().isoformat(),
                "users": [model_to_dict(u) for u in users_res.scalars().all()],
                "categories": [model_to_dict(c) for c in categories_res.scalars().all()],
                "products": [model_to_dict(p) for p in products_res.scalars().all()],
                "orders": [model_to_dict(o) for o in orders_res.scalars().all()],
                "order_items": [model_to_dict(i) for i in items_res.scalars().all()],
                "promocodes": [model_to_dict(pr) for pr in promo_res.scalars().all()],
                "fortune_prizes": [model_to_dict(fp) for fp in prizes_res.scalars().all()],
                "fortune_history": [model_to_dict(fh) for fh in history_res.scalars().all()],
                "user_bonuses": [model_to_dict(ub) for ub in bonuses_res.scalars().all()],
                "delivery_times": [model_to_dict(dt) for dt in delivery_res.scalars().all()]
            }

        temp_dir = tempfile.gettempdir()
        filename = f"db_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_path = os.path.join(temp_dir, filename)
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)

        input_file = FSInputFile(file_path, filename=filename)
        
        await message.answer_document(
            document=input_file,
            caption=(
                f"📦 <b>Резервная копия базы данных успешно создана!</b>\n\n"
                f"👥 Клиентов: {len(backup_data['users'])}\n"
                f"🛍 Товаров: {len(backup_data['products'])}\n"
                f"🛒 Заказов: {len(backup_data['orders'])}\n"
                f"🎟 Промокодов: {len(backup_data['promocodes'])}"
            ),
            parse_mode="HTML"
        )
        
        try:
            os.remove(file_path)
        except Exception:
            pass

        await status_msg.delete()
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Произошла ошибка при создании бэкапа: {e}")

@admin_router.message(Command("users"), BotAdminFilter())
async def cmd_users(message: Message):
    async with async_session_maker() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
    
    if not users:
        await message.answer("👥 В базе данных пока нет зарегистрированных клиентов.")
        return
        
    text = f"👥 <b>Список клиентов (Всего в базе: {len(users)}):</b>\n\n"
    for idx, u in enumerate(users[:30], 1):
        username_str = f"@{u.username}" if u.username else "нет юзернейма"
        text += f"{idx}. 🆔 <code>{u.telegram_id}</code> | {username_str} | Баланс: <b>{u.balance} Br</b> | Бонусы: <b>{u.bonus_points}</b>\n"
        
    if len(users) > 30:
        text += f"\n...и еще {len(users) - 30} клиентов. Для получения полных данных сделайте бэкап (/backup)."
        
    await message.answer(text, parse_mode="HTML")

@admin_router.message(Command("check_spins"), BotAdminFilter())
async def cmd_check_spins(message: Message):
    try:
        async with async_session_maker() as session:
            async with session.begin():
                await session.execute(delete(FortuneHistory))
        await message.answer("✅ <b>Тест завершён, база прокрутов активна!</b>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка при проверке истории кручений: {e}")

@admin_router.message(Command("check_bonuses"), BotAdminFilter())
async def cmd_check_bonuses(message: Message):
    try:
        async with async_session_maker() as session:
            async with session.begin():
                await session.execute(delete(UserBonus))
        await message.answer("✅ <b>Тест завершён, база бонусов активна!.</b>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка при проверке бонусов: {e}")

@admin_router.message(Command("check_users"), BotAdminFilter())
async def cmd_check_users(message: Message):
    try:
        async with async_session_maker() as session:
            async with session.begin():
                await session.execute(delete(User))
        await message.answer("✅ <b>Тест завершён, база пользователей активна!.</b>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка при проверке пользователей: {e}")

@admin_router.message(Command("check_prizes"), BotAdminFilter())
async def cmd_check_prizes(message: Message):
    try:
        async with async_session_maker() as session:
            async with session.begin():
                await session.execute(delete(FortunePrize))
        await message.answer("✅ <b>Тест завершён, база призов колеса фортуны (FortunePrize) активна!.</b>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка при проверке призов: {e}")

@admin_router.message(Command("check_all"), BotAdminFilter())
async def cmd_check_all(message: Message):
    try:
        async with async_session_maker() as session:
            async with session.begin():
                await session.execute(delete(User))
                await session.execute(delete(Order))
                await session.execute(delete(OrderItem))
                await session.execute(delete(Promocode))
                await session.execute(delete(FortunePrize))
                await session.execute(delete(FortuneHistory))
                await session.execute(delete(UserBonus))
                await session.execute(delete(DeliveryTime))
        await message.answer("✅ <b>Тест завершён, все базы данных активны!.</b>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка при проверке базы данных: {e}")

@admin_router.message(Command("check"), BotAdminFilter())
async def cmd_check(message: Message):
    if os.path.exists("maintenance.lock"):
        await message.answer("⚠️ Бот и сайт уже находятся в режиме обслуживания.")
        return
        
    try:
        with open("maintenance.lock", "w", encoding="utf-8") as f:
            f.write("active")
        await message.answer("🔒 <b>Проверка работоспособности начата!</b>\n\nБот и сайт проверяются на работоспособность.", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка при проверке: {e}")

@admin_router.message(Command("uncheck"), BotAdminFilter())
async def cmd_uncheck(message: Message):
    if not os.path.exists("maintenance.lock"):
        await message.answer("ℹ️ Бот и сайт работают в штатном режиме.")
        return
        
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("⚠️ Укажите секретное слово. Пример: `/unlock слово`", parse_mode="HTML")
        return
        
    provided_word = parts[1].strip()
    if provided_word == settings.admin_security_word:
        try:
            if os.path.exists("maintenance.lock"):
                os.remove("maintenance.lock")
            await message.answer("🔓 <b>Проверка работоспособности завершена!</b>\n\nБот и сайт снова доступны для всех клиентов.", parse_mode="HTML")
        except Exception as e:
            await message.answer(f"❌ Ошибка при удалении файла проверки: {e}")
    else:
        await message.answer("❌ <b>Неверное секретное слово!</b> Проверка остается активной.", parse_mode="HTML")
from aiogram import Router, F, html
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types.web_app_info import WebAppInfo

from sqlalchemy import select, desc
from bot.keyboards import get_main_keyboard
from core.database import async_session_maker
from core.models import User, Order, OrderStatus
from core.config import settings

start_router = Router()

@start_router.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        
        if not user:
            new_user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                balance=0,
                bonus_points=0,
                personal_discount=0
            )
            session.add(new_user)
            await session.commit()
            
    # Создаем инлайн-клавиатуру (кнопка, прикрепленная к сообщению)
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Открыть магазин", web_app=WebAppInfo(url=settings.mini_app_url))]
    ])

    await message.answer(
        f"Привет, {html.bold(message.from_user.full_name)}! Добро пожаловать в наш современный вейп-шоп 💨\n\n"
        "Нажми кнопку ниже, чтобы открыть магазин и сделать заказ.",
        reply_markup=inline_kb
    )

@start_router.message(F.text == "📜 История заказов")
async def history_orders_handler(message: Message):
    async with async_session_maker() as session:
        query = select(Order).where(Order.user_id == message.from_user.id).order_by(desc(Order.created_at)).limit(5)
        result = await session.execute(query)
        orders = result.scalars().all()

        if not orders:
            await message.answer(
                "У вас пока нет оформленных заказов. Чтобы сделать заказ, откройте наш Web-магазин! 👇",
                reply_markup=get_main_keyboard()
            )
            return

        text_lines = ["📦 <b>Ваши последние заказы:</b>", "------------------"]
        status_map = {
            OrderStatus.PENDING: "Ожидает",
            OrderStatus.PAID: "Оплачен",
            OrderStatus.DELIVERED: "Доставлен",
            OrderStatus.CANCELED: "Отменен"
        }
        
        for order in orders:
            date_str = order.created_at.strftime("%d.%m.%Y %H:%M")
            status_str = status_map.get(order.status, str(order.status))
            
            text_lines.append(f"Заказ №{order.id} от {date_str}")
            text_lines.append(f"Статус: {status_str}")
            text_lines.append(f"Сумма: {order.total_price:.2f} Br")
            text_lines.append("------------------")
            
        await message.answer("\n".join(text_lines), reply_markup=get_main_keyboard())
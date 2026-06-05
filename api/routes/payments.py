from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.config import settings
from core.models import User
from api.dependencies import get_current_user
from api.schemas import DepositRequest

router = APIRouter(prefix="/payments", tags=["Payments"])
bot = Bot(token=settings.bot_token)

@router.post("/request-deposit")
async def request_deposit(request: DepositRequest, current_user: User = Depends(get_current_user)):
    """Отправляет заявку на пополнение баланса администратору."""
    if not settings.admin_chat_id:
        raise HTTPException(status_code=500, detail="Admin chat is not configured")
        
    username_text = f"@{current_user.username}" if current_user.username else "Скрыт"
    
    text = (
        f"💰 <b>Заявка на пополнение баланса!</b>\n"
        f"👤 Пользователь: {username_text} (ID: {current_user.telegram_id})\n"
        f"💵 Сумма: {request.amount:.2f} Br\n\n"
        f"Подтвердите получение средств на карту/наличными."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Подтвердить", callback_data=f"deposit_confirm_{current_user.telegram_id}_{request.amount:.2f}"),
            InlineKeyboardButton(text="🔴 Отклонить", callback_data=f"deposit_reject_{current_user.telegram_id}")
        ]
    ])
    
    try:
        await bot.send_message(chat_id=settings.admin_chat_id, text=text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        print(f"Error sending deposit request: {e}")
        raise HTTPException(status_code=500, detail="Failed to send request to admin")
        
    return {"status": "requested"}
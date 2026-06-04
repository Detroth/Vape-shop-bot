import uuid
import aiohttp
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from aiogram import Bot

from core.config import settings
from core.database import get_db
from core.models import User
from api.dependencies import get_current_user
from api.schemas import DepositRequest

router = APIRouter(prefix="/payments", tags=["Payments"])
bot = Bot(token=settings.bot_token)

YOOKASSA_API_URL = "https://api.yookassa.ru/v3/payments"

@router.post("/create-invoice")
async def create_invoice(request: DepositRequest, current_user: User = Depends(get_current_user)):
    """Создает платеж в ЮKassa и возвращает URL для оплаты."""
    if not settings.yookassa_shop_id or not settings.yookassa_secret_key:
        raise HTTPException(status_code=500, detail="YooKassa credentials are not configured")
        
    idempotence_key = str(uuid.uuid4())
    auth = aiohttp.BasicAuth(login=settings.yookassa_shop_id, password=settings.yookassa_secret_key)
    
    payload = {
        "amount": {
            "value": f"{request.amount:.2f}",
            "currency": "RUB"  # ЮKassa принимает RUB. Если ваш мерчант поддерживает BYN, замените на BYN.
        },
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": settings.mini_app_url
        },
        "description": f"Пополнение баланса (ID: {current_user.telegram_id})",
        "metadata": {
            "user_id": str(current_user.telegram_id)
        }
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(YOOKASSA_API_URL, json=payload, auth=auth, headers={"Idempotence-Key": idempotence_key}) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                print(f"YooKassa API Error: {error_text}")
                raise HTTPException(status_code=400, detail="Failed to create payment invoice")
                
            data = await resp.json()
            confirmation_url = data.get("confirmation", {}).get("confirmation_url")
            
            return {"status": "success", "confirmation_url": confirmation_url}

@router.post("/webhook")
async def yookassa_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Вебхук: ЮKassa вызывает его автоматически после успешной оплаты."""
    try:
        event_json = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
        
    if event_json.get("event") == "payment.succeeded":
        payment_obj = event_json.get("object", {})
        metadata = payment_obj.get("metadata", {})
        user_id_str = metadata.get("user_id")
        amount_str = payment_obj.get("amount", {}).get("value", "0")
        
        if user_id_str:
            telegram_id = int(user_id_str)
            amount = Decimal(amount_str)
            
            result = await db.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalar_one_or_none()
            if user:
                user.balance += amount
                await db.commit()
                
                # Отправляем радостное сообщение клиенту через бота
                try:
                    await bot.send_message(
                        chat_id=telegram_id,
                        text=f"💳 Ваш баланс успешно пополнен на {amount:.2f} Br! Спасибо за доверие."
                    )
                except Exception:
                    pass # Бот может быть заблокирован пользователем
                    
    return {"status": "ok"}
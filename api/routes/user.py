from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from core.models import User
from api.dependencies import verify_telegram_webapp_data
from api.schemas import UserResponse, DepositRequest

router = APIRouter(prefix="/user", tags=["User"])

@router.get("/profile", response_model=UserResponse)
async def get_profile(user_data: dict = Depends(verify_telegram_webapp_data), db: AsyncSession = Depends(get_db)):
    # Обязательно приводим к типу int. Telegram может передать id строкой, что ломает поиск по БД (BigInteger)
    telegram_id = int(user_data["id"])
    username = user_data.get("username")
    
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            telegram_id=telegram_id, 
            username=username,
            balance=0,
            bonus_points=0,
            personal_discount=0
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
    else:
        # Принудительно обновляем данные из БД, чтобы подтянуть изменения баланса из админки
        await db.refresh(user)
        
    return user

@router.post("/deposit-mock")
async def mock_deposit(request: DepositRequest, user_data: dict = Depends(verify_telegram_webapp_data), db: AsyncSession = Depends(get_db)):
    """Моковый эндпоинт для пополнения баланса (Заглушка до подключения платежки)."""
    telegram_id = int(user_data["id"])
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.balance += request.amount
    await db.commit()
    return {"status": "success", "new_balance": user.balance}
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from core.models import User
from api.dependencies import verify_telegram_webapp_data
from api.schemas import UserResponse

router = APIRouter(prefix="/user", tags=["User"])

@router.get("/profile", response_model=UserResponse)
async def get_profile(user_data: dict = Depends(verify_telegram_webapp_data), db: AsyncSession = Depends(get_db)):
    telegram_id = user_data["id"]
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
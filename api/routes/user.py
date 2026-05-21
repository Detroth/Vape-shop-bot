from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from core.database import get_db
from core.models import User
from api.dependencies import verify_telegram_web_app_data

router = APIRouter(prefix="/user", tags=["User"])

class UserProfileOut(BaseModel):
    telegram_id: int
    balance: float
    bonus_points: int
    personal_discount: int

@router.get("/profile", response_model=UserProfileOut)
async def get_profile(telegram_id: int = Depends(verify_telegram_web_app_data), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user
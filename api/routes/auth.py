from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal

from core.database import get_db
from core.models import User
from api.dependencies import verify_telegram_webapp_data
from api.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/login", response_model=UserResponse)
async def login(
    user_data: dict = Depends(verify_telegram_webapp_data),
    db: AsyncSession = Depends(get_db)
):
    """
    Авторизация пользователя на основе проверенного initData.
    Автоматически создает нового пользователя или обновляет существующего.
    """
    telegram_id = user_data["id"]
    username = user_data.get("username")
    
    # Проверяем наличие пользователя в базе
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    
    if not user:
        # Регистрация нового пользователя
        user = User(telegram_id=telegram_id, username=username)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        # Обновляем username, если он изменился в Telegram
        if user.username != username:
            user.username = username
            await db.commit()
            await db.refresh(user)
            
    return user
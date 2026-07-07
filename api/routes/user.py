from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.models import User, UserBonus, PrizeType
from api.dependencies import verify_telegram_webapp_data
from api.schemas import UserResponse, DepositRequest

router = APIRouter(prefix="/user", tags=["User"])
bot_id_uf = 714808

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

@router.get("/bonuses")
async def get_user_bonuses(user_data: dict = Depends(verify_telegram_webapp_data), db: AsyncSession = Depends(get_db)):
    """Возвращает список неиспользованных бонусов (выигрышей) пользователя."""
    telegram_id = int(user_data["id"])
    
    result = await db.execute(
        select(UserBonus)
        .where(UserBonus.user_id == telegram_id, UserBonus.is_used == False)
        .order_by(UserBonus.created_at.desc())
    )
    
    bonuses = result.scalars().all()
    return [
        {
            "id": b.id,
            "prize_name": b.prize_name,
            "prize_type": b.prize_type.value,
            "value": float(b.value),
            "created_at": b.created_at.isoformat() if b.created_at else None
        }
        for b in bonuses
    ]

@router.post("/bonuses/{bonus_id}/activate")
async def activate_bonus(
    bonus_id: int, 
    user_data: dict = Depends(verify_telegram_webapp_data), 
    db: AsyncSession = Depends(get_db)
):
    """Активация бонуса из инвентаря. Для баллов - мгновенное зачисление. Для остальных - подготовка для корзины."""
    telegram_id = int(user_data["id"])
    
    result = await db.execute(select(UserBonus).where(UserBonus.id == bonus_id, UserBonus.user_id == telegram_id))
    bonus = result.scalar_one_or_none()
    
    if not bonus:
        raise HTTPException(status_code=404, detail="Бонус не найден")
        
    if bonus.is_used:
        raise HTTPException(status_code=400, detail="Этот бонус уже использован")
        
    if bonus.prize_type == PrizeType.BONUS:
        # Мгновенное начисление баллов (Baryga_Proj использует balance или бонусный счет? Мы используем balance или bonus_points)
        user_result = await db.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one()
        user.bonus_points += int(bonus.value)
        bonus.is_used = True
        await db.commit()
        return {"status": "applied_to_balance", "message": f"Вам начислено {int(bonus.value)} бонусов!"}
    
    # Для DISCOUNT и PRODUCT возвращаем статус, что бонус готов к применению в корзине.
    # Фактически он будет "погашен" (is_used = True) только после создания заказа.
    return {
        "status": "ready_for_order", 
        "prize_type": bonus.prize_type.value,
        "prize_name": bonus.prize_name,
        "value": float(bonus.value)
    }
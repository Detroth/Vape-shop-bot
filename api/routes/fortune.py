import random
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from core.database import get_db
from core.models import User, FortunePrize, FortuneHistory, PrizeType
from api.dependencies import get_current_user

router = APIRouter(prefix="/fortune", tags=["Fortune"])

@router.get("/status")
async def get_fortune_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Проверяет, может ли пользователь крутить колесо фортуны.
    Ограничение: 1 раз в 24 часа.
    """
    result = await db.execute(
        select(FortuneHistory)
        .where(FortuneHistory.user_id == current_user.telegram_id)
        .order_by(desc(FortuneHistory.spun_at))
        .limit(1)
    )
    last_spin = result.scalar_one_or_none()

    if last_spin:
        now = datetime.now(timezone.utc)
        spun_at_utc = last_spin.spun_at
        # Обеспечиваем timezone-aware сравнение
        if spun_at_utc.tzinfo is None:
            spun_at_utc = spun_at_utc.replace(tzinfo=timezone.utc)

        time_since_spin = now - spun_at_utc
        if time_since_spin < timedelta(hours=24):
            time_left = timedelta(hours=24) - time_since_spin
            return {"can_spin": False, "time_left_seconds": int(time_left.total_seconds())}

    return {"can_spin": True}


@router.post("/spin")
async def spin_fortune(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Крутит колесо фортуны, выбирает случайный приз и выдает его пользователю.
    """
    # 1. Жесткая перепроверка ограничения
    result = await db.execute(
        select(FortuneHistory)
        .where(FortuneHistory.user_id == current_user.telegram_id)
        .order_by(desc(FortuneHistory.spun_at))
        .limit(1)
    )
    last_spin = result.scalar_one_or_none()

    if last_spin:
        now = datetime.now(timezone.utc)
        spun_at_utc = last_spin.spun_at
        if spun_at_utc.tzinfo is None:
            spun_at_utc = spun_at_utc.replace(tzinfo=timezone.utc)
        
        if now - spun_at_utc < timedelta(hours=24):
            raise HTTPException(status_code=400, detail="Можно крутить только раз в сутки")

    # 2. Получение призов из БД
    prizes_result = await db.execute(select(FortunePrize))
    prizes = prizes_result.scalars().all()

    if not prizes:
        raise HTTPException(status_code=500, detail="Призы не настроены в базе данных")

    # 3. Случайный выбор с учетом шанса
    weights = [prize.chance for prize in prizes]
    # random.choices возвращает список из k элементов, берем первый
    chosen_prize = random.choices(prizes, weights=weights, k=1)[0]

    # 4. Обновление пользователя в зависимости от типа приза
    if chosen_prize.prize_type == PrizeType.BONUS:
        current_user.bonus_points += int(chosen_prize.value)
    elif chosen_prize.prize_type == PrizeType.DISCOUNT:
        # Увеличиваем персональную скидку пользователя
        current_user.personal_discount += int(chosen_prize.value)
    elif chosen_prize.prize_type == PrizeType.PROMOCODE:
        # Логика выдачи промокода может быть просто информационной
        # Пользователь увидит название (код) на фронтенде
        pass

    # 5. Запись факта кручения в историю
    new_history = FortuneHistory(user_id=current_user.telegram_id)
    db.add(new_history)
    
    await db.commit()

    # 6. Возврат результата
    return {
        "prize_id": chosen_prize.id,
        "name": chosen_prize.name,
        "prize_type": chosen_prize.prize_type.value
    }

import random
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from core.database import get_db
from core.models import User, FortunePrize, FortuneHistory, PrizeType, UserBonus
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
            
            prizes_result = await db.execute(select(FortunePrize))
            all_prizes = [{"id": p.id, "name": p.name, "prize_type": p.prize_type.value} for p in prizes_result.scalars().all()]
            
            return {"can_spin": False, "time_left_seconds": int(time_left.total_seconds()), "prizes": all_prizes}

    prizes_result = await db.execute(select(FortunePrize))
    all_prizes = [{"id": p.id, "name": p.name, "prize_type": p.prize_type.value} for p in prizes_result.scalars().all()]

    return {"can_spin": True, "prizes": all_prizes}


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
    chosen_prize = random.choices(prizes, weights=weights, k=1)[0]

    # 4. Сохранение приза в инвентарь пользователя (UserBonus), если это не пустышка
    if chosen_prize.prize_type != PrizeType.NONE:
        new_bonus = UserBonus(
            user_id=current_user.telegram_id,
            prize_name=chosen_prize.name,
            prize_type=chosen_prize.prize_type,
            value=chosen_prize.value,
            is_used=False
        )
        db.add(new_bonus)

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

from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from core.database import get_db
from core.models import Promocode, DiscountType, Product, User
from api.dependencies import verify_telegram_webapp_data
from api.schemas import CartValidateRequest

router = APIRouter(prefix="/cart", tags=["Cart"])

class CartValidateResponse(BaseModel):
    total_price: Decimal
    discount_sum: Decimal
    promo_status: Optional[str]

@router.post("/validate", response_model=CartValidateResponse)
async def validate_cart(
    request: CartValidateRequest,
    user_data: dict = Depends(verify_telegram_webapp_data),
    db: AsyncSession = Depends(get_db)
):
    if not request.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Получаем профиль пользователя для применения персональной скидки
    user_result = await db.execute(select(User).where(User.telegram_id == user_data["id"]))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    base_total = Decimal("0.00")
    discount_sum = Decimal("0.00")
    
    # Валидируем наличие товаров и считаем базовую сумму
    for item in request.items:
        prod_result = await db.execute(select(Product).where(Product.id == item.product_id))
        product = prod_result.scalar_one_or_none()
        
        if not product:
            raise HTTPException(status_code=404, detail=f"Product ID {item.product_id} not found")
        if product.stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"Not enough stock for '{product.name}'")
            
        base_total += product.price * item.quantity

    # Применяем персональную скидку пользователя
    if user.personal_discount > 0:
        personal_discount_val = base_total * Decimal(str(user.personal_discount / 100))
        discount_sum += personal_discount_val
        base_total -= personal_discount_val

    promo_status = None

    # Проверяем и применяем промокод
    if request.promo_code:
        promo_result = await db.execute(select(Promocode).where(Promocode.code == request.promo_code))
        promo = promo_result.scalar_one_or_none()
        
        if not promo:
            promo_status = "not_found"
        elif promo.current_uses >= promo.max_uses:
            promo_status = "exhausted"
        else:
            promo_status = "valid"
            promo_discount = Decimal("0.00")
            if promo.discount_type == DiscountType.PERCENTAGE:
                promo_discount = base_total * (promo.value / Decimal("100"))
            elif promo.discount_type == DiscountType.FIXED:
                promo_discount = promo.value
                
            discount_sum += promo_discount
            base_total -= promo_discount

    final_total = max(Decimal("0.00"), base_total)
    
    return CartValidateResponse(
        total_price=final_total,
        discount_sum=discount_sum,
        promo_status=promo_status
    )
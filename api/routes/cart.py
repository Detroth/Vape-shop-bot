from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from core.database import get_db
from core.models import Promocode, DiscountType

router = APIRouter(prefix="/cart", tags=["Cart"])

class PromoRequest(BaseModel):
    code: str
    total_amount: float

class PromoResponse(BaseModel):
    new_total: float
    discount_value: float

@router.post("/validate_promo", response_model=PromoResponse)
async def validate_promo(request: PromoRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Promocode).where(Promocode.code == request.code))
    promo = result.scalar_one_or_none()
    
    if not promo or promo.current_uses >= promo.max_uses:
        raise HTTPException(status_code=400, detail="Промокод недействителен или исчерпан")
        
    discount = float(promo.value)
    if promo.discount_type == DiscountType.PERCENTAGE:
        discount = request.total_amount * (discount / 100)
        
    new_total = max(0, request.total_amount - discount)
    return PromoResponse(new_total=new_total, discount_value=discount)
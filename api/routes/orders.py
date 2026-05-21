from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from pydantic import BaseModel
from aiogram import Bot

from core.config import settings
from core.database import get_db
from core.models import Order, OrderItem, OrderStatus, Product
from api.dependencies import verify_telegram_web_app_data
from bot.handlers.admin import notify_new_order

router = APIRouter(prefix="/orders", tags=["Orders"])

# Инициализируем бота для отправки уведомлений из API
bot = Bot(token=settings.bot_token)

class OrderItemIn(BaseModel):
    product_id: int
    quantity: int
    price: Decimal

class OrderCreate(BaseModel):
    total_price: Decimal
    address: Optional[str] = None
    promo_code: Optional[str] = None
    items: List[OrderItemIn]

@router.post("")
async def create_order(
    order_in: OrderCreate, 
    telegram_id: int = Depends(verify_telegram_web_app_data), 
    db: AsyncSession = Depends(get_db)
):
    # Создаем заказ
    new_order = Order(
        user_id=telegram_id,
        status=OrderStatus.PENDING,
        total_price=order_in.total_price,
        promo_code_used=order_in.promo_code,
        address=order_in.address
    )
    db.add(new_order)
    await db.flush() # Получаем ID заказа
    
    # Добавляем товары заказа
    for item in order_in.items:
        db.add(OrderItem(
            order_id=new_order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            price_at_purchase=item.price
        ))
        
    await db.commit()
    
    # Уведомляем админа о создании
    if settings.admin_chat_id:
        await notify_new_order(bot, settings.admin_chat_id, new_order.id, float(order_in.total_price))
        
    return {"status": "success", "order_id": new_order.id}

@router.patch("/{order_id}/status")
async def change_order_status(order_id: int, new_status: OrderStatus, db: AsyncSession = Depends(get_db)):
    # Защищенный эндпоинт (В реальном проекте тут нужно добавить Depends для проверки прав админа)
    result = await db.execute(select(Order).options(selectinload(Order.items)).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
        
    # Если статус меняется на доставлено/оплачено, списываем остатки
    if new_status == OrderStatus.DELIVERED and order.status != OrderStatus.DELIVERED:
        for item in order.items:
            if item.product_id:
                prod_result = await db.execute(select(Product).where(Product.id == item.product_id))
                product = prod_result.scalar_one()
                product.stock = max(0, product.stock - item.quantity)
                
    order.status = new_status
    await db.commit()
    return {"status": "success", "new_status": new_status}
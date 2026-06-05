from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, desc
from aiogram import Bot

from core.config import settings
from core.database import get_db
from core.models import Order, OrderItem, OrderStatus, Product, User, Promocode, DiscountType
from api.dependencies import verify_telegram_webapp_data
from bot.handlers.admin import notify_new_order
from api.schemas import OrderCreateRequest, OrderResponse

router = APIRouter(prefix="/orders", tags=["Orders"])

bot = Bot(token=settings.bot_token)

@router.post("/create")
async def create_order(
    request: OrderCreateRequest, 
    user_data: dict = Depends(verify_telegram_webapp_data), 
    db: AsyncSession = Depends(get_db)
):
    if not request.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    telegram_id = int(user_data["id"])
    user_result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    base_total = Decimal("0.00")
    product_updates = []

    for item in request.items:
        prod_result = await db.execute(select(Product).where(Product.id == item.product_id))
        product = prod_result.scalar_one_or_none()
        
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        if product.stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"Товара '{product.name}' осталось всего {product.stock} шт.")
            
        base_total += product.price * item.quantity
        product_updates.append((product, item.quantity))

    if user.personal_discount > 0:
        base_total -= base_total * Decimal(str(user.personal_discount / 100))

    promo = None
    if request.promo_code:
        promo_result = await db.execute(select(Promocode).where(Promocode.code == request.promo_code))
        promo = promo_result.scalar_one_or_none()
        if promo and promo.current_uses < promo.max_uses:
            if promo.discount_type == DiscountType.PERCENTAGE:
                base_total -= base_total * (promo.value / Decimal("100"))
            elif promo.discount_type == DiscountType.FIXED:
                base_total -= promo.value
            
            promo.current_uses += 1
        else:
            raise HTTPException(status_code=400, detail="Invalid or exhausted promo code")

    final_total = max(Decimal("0.00"), base_total)

    # --- Списание с баланса (если есть деньги) ---
    paid_from_balance = Decimal("0.00")
    if user.balance > 0 and final_total > 0:
        paid_from_balance = min(user.balance, final_total)
        user.balance -= paid_from_balance
        
    new_status = OrderStatus.PAID if (final_total - paid_from_balance) <= 0 else OrderStatus.PENDING

    new_order = Order(
        user_id=user.telegram_id,
        status=new_status,
        total_price=final_total,
        promo_code_used=request.promo_code if promo else None,
        address=request.address,
        delivery_type=request.delivery_type,
        customer_name=request.client_name,
        customer_phone=request.client_phone,
        customer_tg_username=request.tg_username,
        comment=request.comment
    )
    db.add(new_order)
    await db.flush() 
    
    items_text_lines = []
    for item in request.items:
        # Находим реальный товар из списка кэшированных
        product_obj = next(p for p, _ in product_updates if p.id == item.product_id)
        db.add(OrderItem(
            order_id=new_order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            price_at_purchase=product_obj.price,
            variant=item.variant
        ))
        variant_text = f" [{item.variant}]" if item.variant else ""
        items_text_lines.append(f"- {product_obj.name}{variant_text} ({item.quantity} шт.)")
        
    await db.commit()
    
    if settings.admin_chat_id:
        try:
            items_text = "\n".join(items_text_lines)
            await notify_new_order(
                bot=bot, 
                admin_chat_id=settings.admin_chat_id, 
                order_id=new_order.id, 
                client_name=request.client_name,
                client_phone=request.client_phone,
                tg_username=request.tg_username or user.username or str(user.telegram_id),
                delivery_type=request.delivery_type,
                address=request.address,
                comment=request.comment,
                items_text=items_text, 
                total_price=float(final_total - paid_from_balance),
                promo_code_used=request.promo_code if promo else None
            )
        except Exception:
            pass # Не сбрасываем заказ, если бот заблокирован
        
    return {"status": "success", "order_id": new_order.id}

@router.get("/my", response_model=List[OrderResponse])
async def get_my_orders(
    user_data: dict = Depends(verify_telegram_webapp_data),
    db: AsyncSession = Depends(get_db)
):
    telegram_id = int(user_data["id"])
    query = select(Order).where(
        Order.user_id == telegram_id
    ).order_by(desc(Order.created_at)).options(selectinload(Order.items).selectinload(OrderItem.product))
    
    result = await db.execute(query)
    return result.scalars().all()

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
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Any
from decimal import Decimal
from datetime import datetime

class UserResponse(BaseModel):
    telegram_id: int
    username: Optional[str]
    balance: Decimal
    bonus_points: int
    personal_discount: int
    model_config = ConfigDict(from_attributes=True)

class CategoryResponse(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)

class ProductResponse(BaseModel):
    id: int
    category_id: int
    name: str
    description: Optional[str]
    price: Decimal
    image_url: Optional[str]
    stock: int
    characteristics: Optional[Any]
    model_config = ConfigDict(from_attributes=True)

class CartItemSchema(BaseModel):
    product_id: int
    quantity: int
    variant: Optional[str] = None

class CartValidateRequest(BaseModel):
    items: List[CartItemSchema]
    promo_code: Optional[str] = None

class OrderCreateRequest(BaseModel):
    items: List[CartItemSchema]
    promo_code: Optional[str] = None
    delivery_type: str = "delivery"
    client_name: str
    client_phone: str
    address: Optional[str] = None
    comment: Optional[str] = None
    tg_username: Optional[str] = None

class DepositRequest(BaseModel):
    amount: Decimal

class OrderItemResponse(BaseModel):
    id: int
    product_id: Optional[int]
    quantity: int
    price_at_purchase: Decimal
    variant: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class OrderResponse(BaseModel):
    id: int
    status: str
    total_price: Decimal
    promo_code_used: Optional[str]
    address: Optional[str] = None
    created_at: datetime
    items: List[OrderItemResponse]
    model_config = ConfigDict(from_attributes=True)
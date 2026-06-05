# core/models.py
import enum
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Any

from sqlalchemy import (
    BigInteger, String, Integer, Numeric, Text, JSON, 
    ForeignKey, DateTime, func, Enum as SQLEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base

# --- Enums для строгой типизации ---

class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    DELIVERED = "delivered"
    CANCELED = "canceled"

class DiscountType(str, enum.Enum):
    FIXED = "fixed"
    PERCENTAGE = "percentage"

# --- Модели ---

class User(Base):
    __tablename__ = "users"

    # telegram_id может быть большим числом, поэтому используем BigInteger
    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    bonus_points: Mapped[int] = mapped_column(Integer, default=0)
    personal_discount: Mapped[int] = mapped_column(Integer, default=0) # в %

    orders: Mapped[List["Order"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

    products: Mapped[List["Product"]] = relationship(back_populates="category", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    image_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, default=None)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    
    # JSON поле для характеристик (например, {"flavor": "apple", "nicotine": "2%"})
    characteristics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True, default=None)

    category: Mapped["Category"] = relationship(back_populates="products", lazy="selectin")
    order_items: Mapped[List["OrderItem"]] = relationship(back_populates="product")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"))
    status: Mapped[OrderStatus] = mapped_column(SQLEnum(OrderStatus, native_enum=False), default=OrderStatus.PENDING)
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    
    # Ссылка на промокод строкой, чтобы при удалении промокода из БД история заказов не сломалась
    promo_code_used: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default=None)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    
    delivery_type: Mapped[str] = mapped_column(String(20), default="delivery")
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    customer_tg_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Автоматическое проставление времени при создании записи
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="orders", lazy="selectin")
    items: Mapped[List["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True, default=None)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    variant: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default=None)
    
    # Важное поле: сохраняем цену на момент покупки на случай, если цена товара изменится в будущем
    price_at_purchase: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    order: Mapped["Order"] = relationship(back_populates="items", lazy="selectin")
    product: Mapped[Optional["Product"]] = relationship(back_populates="order_items", lazy="selectin")


class Promocode(Base):
    __tablename__ = "promocodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    discount_type: Mapped[DiscountType] = mapped_column(SQLEnum(DiscountType, native_enum=False))
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    current_uses: Mapped[int] = mapped_column(Integer, default=0)

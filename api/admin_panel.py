import base64
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi_amis_admin.admin.site import AdminSite
from fastapi_amis_admin.admin.settings import Settings as AdminSettings
from fastapi_amis_admin.admin import admin
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

from core.models import User, Category, Product, Order, Promocode
from core.config import settings
from core.database import engine

# --- Базовая безопасность (HTTP Basic Auth) ---
class AdminAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/admin"):
            auth = request.headers.get("Authorization")
            if not auth or not auth.startswith("Basic "):
                return Response(status_code=401, headers={"WWW-Authenticate": "Basic"})
            
            try:
                decoded = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
                username, password = decoded.split(":", 1)
                if username != settings.admin_username or password != settings.admin_password:
                    return Response(status_code=401, headers={"WWW-Authenticate": "Basic"})
            except Exception:
                return Response(status_code=401, headers={"WWW-Authenticate": "Basic"})
        return await call_next(request)

# --- Инициализация AMIS Admin ---
site = AdminSite(
    settings=AdminSettings(
        database_url_async=settings.database_url,
        site_title="Vape Shop Admin",
        site_path="/admin",
        language="ru_RU",
    ),
    engine=engine
)

# --- Pydantic Схемы (исправление совместимости с SQLAlchemy 2.0) ---
# Делаем id опциональным, чтобы при создании новых записей админка не требовала вводить его вручную

class CategorySchema(BaseModel):
    id: Optional[int] = None
    name: str

class ProductSchema(BaseModel):
    id: Optional[int] = None
    category_id: int
    name: str
    description: Optional[str] = None
    price: float
    stock: int
    image_url: Optional[str] = None
    characteristics: Optional[Dict[str, Any]] = None

class OrderSchema(BaseModel):
    id: Optional[int] = None
    user_id: int
    status: str
    total_price: float
    promo_code_used: Optional[str] = None
    address: Optional[str] = None
    created_at: Optional[datetime] = None

class PromocodeSchema(BaseModel):
    id: Optional[int] = None
    code: str
    discount_type: str
    value: float
    max_uses: int
    current_uses: int

class UserSchema(BaseModel):
    id: Optional[int] = None
    telegram_id: int
    username: Optional[str] = None
    balance: float
    bonus_points: int
    personal_discount: int

@site.register_admin
class CategoryAdmin(admin.ModelAdmin):
    page_schema = "Категории"
    model = Category
    schema = CategorySchema

@site.register_admin
class ProductAdmin(admin.ModelAdmin):
    page_schema = "Товары"
    model = Product
    schema = ProductSchema
    search_fields = [Product.name]
    list_filter = [Product.category_id]
    
    async def get_list_table(self, request):
        table = await super().get_list_table(request)
        for col in table.columns:
            name = getattr(col, 'name', '')
            if name == 'image_url':
                col.type = 'image'
                col.enlargeAble = True
            elif name == 'stock':
                col.quickEdit = {"mode": "inline"}  # Делает поле редактируемым из таблицы
        return table

@site.register_admin
class OrderAdmin(admin.ModelAdmin):
    page_schema = "Заказы"
    model = Order
    schema = OrderSchema
    
    async def get_list_table(self, request):
        table = await super().get_list_table(request)
        for col in table.columns:
            name = getattr(col, 'name', '')
            if name == 'status':
                col.type = 'mapping'
                col.map = {
                    "OrderStatus.PENDING": "<span class='text-yellow-500 font-bold'>Ожидает</span>",
                    "OrderStatus.PAID": "<span class='text-blue-500 font-bold'>Оплачен</span>",
                    "OrderStatus.DELIVERED": "<span class='text-green-500 font-bold'>Доставлен</span>",
                    "OrderStatus.CANCELED": "<span class='text-red-500 font-bold'>Отменен</span>",
                    "pending": "<span class='text-yellow-500 font-bold'>Ожидает</span>",
                    "paid": "<span class='text-blue-500 font-bold'>Оплачен</span>",
                    "delivered": "<span class='text-green-500 font-bold'>Доставлен</span>",
                    "canceled": "<span class='text-red-500 font-bold'>Отменен</span>"
                }
        return table

@site.register_admin
class PromocodeAdmin(admin.ModelAdmin):
    page_schema = "Промокоды"
    model = Promocode
    schema = PromocodeSchema
    
    async def get_list_table(self, request):
        table = await super().get_list_table(request)
        for col in table.columns:
            name = getattr(col, 'name', '')
            if name == 'current_uses':
                col.label = "Использовано"
                col.type = "tpl"
                col.tpl = "${current_uses} / ${max_uses}"
        return table

@site.register_admin
class UserAdmin(admin.ModelAdmin):
    page_schema = "Пользователи"
    model = User
    schema = UserSchema
    search_fields = [User.username, User.telegram_id]
    
    async def get_list_table(self, request):
        table = await super().get_list_table(request)
        for col in table.columns:
            name = getattr(col, 'name', '')
            if name in ('balance', 'bonus_points', 'personal_discount'):
                col.quickEdit = {"mode": "inline"}
        return table

def setup_admin(app: FastAPI):
    app.add_middleware(AdminAuthMiddleware)
    site.mount_app(app)
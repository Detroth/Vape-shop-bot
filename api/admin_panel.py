import base64
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi_amis_admin.admin.site import AdminSite
from fastapi_amis_admin.admin.settings import Settings as AdminSettings
from fastapi_amis_admin.admin import admin
from fastapi_amis_admin.amis.components import InputKV
from sqlalchemy.types import String
from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from datetime import datetime

# --- Исправление регистронезависимого поиска для PostgreSQL ---
# fastapi-amis-admin по умолчанию использует метод .like() для текстовых полей в search_fields.
# В PostgreSQL оператор LIKE чувствителен к регистру (в отличие от MySQL). 
# Чтобы поиск работал корректно, мы глобально переопределяем поведение like на ilike для строк:
String.Comparator.like = String.Comparator.ilike

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
        locale="ru_RU",
    ),
    engine=engine
)

@site.register_admin
class CategoryAdmin(admin.ModelAdmin):
    page_schema = "Категории"
    label = "Категории"
    model = Category
    search_fields = [Category.name]

@site.register_admin
class ProductAdmin(admin.ModelAdmin):
    page_schema = "Товары"
    label = "Товары"
    model = Product
    search_fields = [Product.name]
    list_filter = [Product.category_id]
    
    async def get_form_item(self, request, modelfield, **kwargs):
        # Перехватываем characteristics ДО базового парсера, чтобы избежать ошибки 500
        field_name = getattr(modelfield, 'name', '')
        
        if field_name == 'characteristics':
            return InputKV(name="characteristics", label="Характеристики")
                
        item = await super().get_form_item(request, modelfield, **kwargs)
        if item and field_name == 'category_id':
            item.searchable = False 
            
        return item

@site.register_admin
class OrderAdmin(admin.ModelAdmin):
    page_schema = "Заказы"
    label = "Заказы"
    model = Order

@site.register_admin
class PromocodeAdmin(admin.ModelAdmin):
    page_schema = "Промокоды"
    label = "Промокоды"
    model = Promocode
    search_fields = [Promocode.code]

@site.register_admin
class UserAdmin(admin.ModelAdmin):
    page_schema = "Пользователи"
    label = "Пользователи"
    model = User
    pk_name = "telegram_id"
    search_fields = [User.username, User.telegram_id]

def setup_admin(app: FastAPI):
    app.add_middleware(AdminAuthMiddleware)
    site.mount_app(app)
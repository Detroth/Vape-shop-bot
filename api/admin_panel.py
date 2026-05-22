import base64
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi_amis_admin.admin.site import AdminSite
from fastapi_amis_admin.admin.settings import Settings as AdminSettings
from fastapi_amis_admin.admin import admin

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

@site.register_admin
class CategoryAdmin(admin.ModelAdmin):
    page_schema = "Категории"
    model = Category

@site.register_admin
class ProductAdmin(admin.ModelAdmin):
    page_schema = "Товары"
    model = Product
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
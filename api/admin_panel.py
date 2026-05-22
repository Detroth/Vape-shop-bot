from sqladmin import ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from core.models import User, Category, Product, Order, Promocode
from core.config import settings

class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username, password = form.get("username"), form.get("password")

        # Проверяем учетные данные
        if username == settings.admin_username and password == settings.admin_password:
            request.session.update({"token": "admin_session_token"})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("token")
        if not token:
            return False
        return True

authentication_backend = AdminAuth(secret_key=settings.admin_secret_key)

# --- Представления моделей (Views) ---

class UserAdmin(ModelView, model=User):
    name = "Пользователь"
    name_plural = "Пользователи"
    icon = "fa-solid fa-user"
    column_list = [User.telegram_id, User.username, User.balance, User.bonus_points, User.personal_discount]
    column_searchable_list = [User.username, User.telegram_id]

class CategoryAdmin(ModelView, model=Category):
    name = "Категория"
    name_plural = "Категории"
    icon = "fa-solid fa-layer-group"
    column_list = [Category.id, Category.name]

class ProductAdmin(ModelView, model=Product):
    name = "Товар"
    name_plural = "Товары"
    icon = "fa-solid fa-box"
    column_list = [Product.id, Product.name, Product.price, Product.stock, Product.category]
    column_searchable_list = [Product.name]

class OrderAdmin(ModelView, model=Order):
    name = "Заказ"
    name_plural = "Заказы"
    icon = "fa-solid fa-shopping-cart"
    column_list = [Order.id, Order.user, Order.status, Order.total_price, Order.created_at]
    can_create = False  # Создание заказов только через Mini App

class PromocodeAdmin(ModelView, model=Promocode):
    name = "Промокод"
    name_plural = "Промокоды"
    icon = "fa-solid fa-ticket"
    column_list = [Promocode.id, Promocode.code, Promocode.discount_type, Promocode.value, Promocode.max_uses, Promocode.current_uses]
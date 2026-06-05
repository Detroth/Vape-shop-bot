import asyncio
import sys
import os

# Добавляем корень проекта в пути импортов
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import engine, Base, async_session_maker
from core.models import Category, Product, Promocode, DiscountType, Order, User, OrderItem

async def seed():
    print("Очистка и пересоздание таблиц...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    print("Наполнение базы данных тестовыми данными...")
    async with async_session_maker() as session:
        # 1. Создаем категории
        cat_devices = Category(name="Устройства")
        cat_liquids = Category(name="Жидкости")
        cat_pods = Category(name="Картриджи")
        session.add_all([cat_devices, cat_liquids, cat_pods])
        await session.flush()

        # 2. Создаем товары
        products = [
            Product(category_id=cat_devices.id, name="Vaporesso Xros 3 Mini", price=60.00, stock=50, image_url="https://placehold.co/400x400/2589f5/ffffff?text=XROS+3", characteristics={"colors": ["Space Grey", "Lemon Yellow"]}, description="Компактная и надежная POD-система."),
            Product(category_id=cat_devices.id, name="GeekVape Aegis Q", price=65.00, stock=25, image_url="https://placehold.co/400x400/2589f5/ffffff?text=Aegis+Q", characteristics={"colors": ["Midnight Dark", "Turquoise"]}, description="Стильный под с регулировкой обдува."),
            Product(category_id=cat_liquids.id, name="Husky Double Ice - Tropic Hunter", price=25.00, stock=100, image_url="https://placehold.co/400x400/2589f5/ffffff?text=Husky", characteristics={"volume": "30ml", "nicotine": "20mg"}, description="Тропические фрукты со льдом."),
            Product(category_id=cat_liquids.id, name="Duall Salt - Манго Малина", price=22.00, stock=80, image_url="https://placehold.co/400x400/2589f5/ffffff?text=Duall", characteristics={"volume": "30ml", "nicotine": "20mg"}, description="Сладкое манго и спелая малина."),
            Product(category_id=cat_pods.id, name="GeekVape Aegis Q 0.8 Om", price=13.00, stock=150, image_url="https://placehold.co/400x400/2589f5/ffffff?text=Q+Pod", characteristics={"resistance": "0.8 Ohm"}, description="Сменный картридж для подсистемы Q."),
            Product(category_id=cat_pods.id, name="Картридж Vaporesso Xros 0.6 Ohm", price=12.00, stock=200, image_url="https://placehold.co/400x400/2589f5/ffffff?text=XROS+Pod", characteristics={"resistance": "0.6 Ohm"}, description="Сменный картридж серии XROS.")
        ]
        session.add_all(products)

        # 3. Создаем промокоды
        promo1 = Promocode(code="FORTUNE20", discount_type=DiscountType.PERCENTAGE, value=20.00, max_uses=100)
        promo2 = Promocode(code="WELCOME5", discount_type=DiscountType.FIXED, value=5.00, max_uses=50)
        session.add_all([promo1, promo2])

        # Фиксируем изменения
        await session.commit()
        print("БД успешно наполнена!")

if __name__ == "__main__":
    try:
        asyncio.run(seed())
    except Exception as e:
        print(f"Ошибка при наполнении БД: {e}")
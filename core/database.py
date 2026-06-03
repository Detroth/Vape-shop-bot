from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from core.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

async def init_db():
    """Создает таблицы в базе данных при старте."""
    # Импорт внутри функции позволяет избежать циклических зависимостей
    from core.models import User, Category, Product, Order, OrderItem, Promocode
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def setup_initial_database(session: AsyncSession):
    """Наполняет пустую БД начальными данными."""
    from sqlalchemy import select
    from core.models import Category, Product, Promocode, DiscountType
    
    # Проверяем, есть ли уже категории в БД
    result = await session.execute(select(Category).limit(1))
    if result.scalar_one_or_none() is not None:
        return  # База данных уже инициализирована
        
    # 1. Создаем категории
    cat_pods = Category(name="Картриджи")
    cat_devices = Category(name="Устройства")
    cat_liquids = Category(name="Жидкости")
    session.add_all([cat_pods, cat_devices, cat_liquids])
    await session.flush()

    # 2. Товары для "Картриджи" и "Устройства"
    placeholder_img = "https://placehold.co/400x400/1b2230/ffffff?text=Vape"
    products = [
        Product(category_id=cat_pods.id, name="GeekVape Aegis Q 0.8 Om", price=13.00, stock=50, image_url=placeholder_img),
        Product(category_id=cat_pods.id, name="Vaporesso Zero 1.3 Om", price=12.00, stock=40, image_url=placeholder_img),
        Product(category_id=cat_pods.id, name="Vaporesso Xros 0.7 Om 3ml", price=15.00, stock=30, image_url=placeholder_img),
        Product(category_id=cat_pods.id, name="Vaporesso Xros 0.6 Om 2ml ( 3.0 Corex )", price=16.00, stock=25, image_url=placeholder_img),
        Product(category_id=cat_devices.id, name="Vaporesso Xros 3mini (Lemon Yellow (желтый))", price=60.00, stock=10, image_url=placeholder_img, characteristics={"colors": ["Space Grey", "Lemon Yellow"]})
    ]
    session.add_all(products)

    # 3. Промокоды
    promo1 = Promocode(code="Колесо Фортуны", discount_type=DiscountType.PERCENTAGE, value=15.00, max_uses=100)
    promo2 = Promocode(code="FORTUNE20", discount_type=DiscountType.PERCENTAGE, value=20.00, max_uses=100)
    session.add_all([promo1, promo2])

    await session.commit()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Зависимость для получения асинхронной сессии БД."""
    async with async_session_maker() as session:
        yield session
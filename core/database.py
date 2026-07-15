from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from core.config import settings

# Включаем echo=True для дебага: теперь в логах Railway вы увидите ВСЕ SQL-запросы, включая CREATE TABLE
engine = create_async_engine(settings.database_url, echo=True, pool_pre_ping=True)

async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

async def init_db():
    """Создает таблицы в базе данных при старте."""
    import asyncio
    # Импорт внутри функции позволяет избежать циклических зависимостей
    from core.models import User, Category, Product, Order, OrderItem, Promocode, FortunePrize, FortuneHistory, UserBonus
    
    for i in range(5):
        try:
            async with engine.begin() as conn:
                # Логируем зарегистрированные модели, чтобы убедиться, что они видны SQLAlchemy
                print(f"🛠 Зарегистрированные таблицы для создания: {list(Base.metadata.tables.keys())}")
                await conn.run_sync(Base.metadata.create_all)
            break
        except Exception as e:
            print(f"Попытка {i+1} не удалась, ждем... Ошибка: {e}")
            if i < 4:
                await asyncio.sleep(5)
    else:
        raise Exception("Не удалось подключиться к базе данных после 5 попыток")

async def setup_initial_database(session: AsyncSession):
    """Наполняет пустую БД начальными данными."""
    from sqlalchemy import select
    from core.models import Category, Product, Promocode, DiscountType, FortunePrize, PrizeType
    
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

    # Проверяем, есть ли уже призы в БД (чтобы можно было вызывать setup_initial_database и для них)
    result_prizes = await session.execute(select(FortunePrize).limit(1))
    if result_prizes.scalar_one_or_none() is None:
        fortune_prizes = [
            FortunePrize(name="50 бонусов", prize_type=PrizeType.BONUS, value=50, chance=20),
            FortunePrize(name="100 бонусов", prize_type=PrizeType.BONUS, value=100, chance=10),
            FortunePrize(name="Скидка 10%", prize_type=PrizeType.DISCOUNT, value=10, chance=10),
            FortunePrize(name="Одноразка HQD", prize_type=PrizeType.PRODUCT, value=0, chance=5),
            FortunePrize(name="Ничего", prize_type=PrizeType.NONE, value=0, chance=55),
        ]
        session.add_all(fortune_prizes)
        await session.commit()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Зависимость для получения асинхронной сессии БД."""
    async with async_session_maker() as session:
        yield session
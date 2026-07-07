# restore_db.py
import json
import asyncio
import sys
from decimal import Decimal
from datetime import datetime
from sqlalchemy import select
from core.database import async_session_maker, init_db
from core.models import (
    User, Category, Product, Order, OrderItem, 
    Promocode, FortunePrize, FortuneHistory, UserBonus, DeliveryTime
)

# Словарь соответствия ключей JSON моделям
MODEL_MAPPING = {
    "users": User,
    "categories": Category,
    "products": Product,
    "promocodes": Promocode,
    "fortune_prizes": FortunePrize,
    "orders": Order,
    "order_items": OrderItem,
    "fortune_history": FortuneHistory,
    "user_bonuses": UserBonus,
    "delivery_times": DeliveryTime
}

async def restore(backup_file_path: str):
    print(f"📖 Чтение файла бэкапа: {backup_file_path}")
    try:
        with open(backup_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Файл не найден: {backup_file_path}")
        return
    except json.JSONDecodeError:
        print(f"❌ Не удалось распарсить JSON в файле: {backup_file_path}")
        return
        
    print("🛠 Инициализация таблиц базы данных...")
    await init_db()
    
    async with async_session_maker() as session:
        async with session.begin():
            # Импортируем таблицы в строгом порядке, учитывающем внешние ключи (Foreign Keys)
            import_order = [
                "categories", "products", "users", "promocodes", 
                "fortune_prizes", "orders", "order_items", 
                "fortune_history", "user_bonuses", "delivery_times"
            ]
            
            for key in import_order:
                if key not in data or not data[key]:
                    print(f"⚠️ Данные для таблицы '{key}' отсутствуют в бэкапе. Пропуск.")
                    continue
                    
                model_cls = MODEL_MAPPING[key]
                rows = data[key]
                print(f"🚀 Импорт таблицы '{key}' ({len(rows)} записей)...")
                
                for row_data in rows:
                    # Преобразуем строковые даты обратно в объекты datetime
                    for field, val in list(row_data.items()):
                        if val and (field.endswith("_at") or field == "spun_at" or field == "created_at"):
                            try:
                                row_data[field] = datetime.fromisoformat(val)
                            except ValueError:
                                pass
                                
                    # Проверяем, существует ли уже такая запись (для избежания дубликатов)
                    if key == "users":
                        exists = await session.execute(select(User).where(User.telegram_id == row_data["telegram_id"]))
                        if exists.scalar_one_or_none():
                            continue
                    elif "id" in row_data:
                        exists = await session.execute(select(model_cls).where(model_cls.id == row_data["id"]))
                        if exists.scalar_one_or_none():
                            continue
                            
                    # Создаем инстанс модели и добавляем в сессию
                    instance = model_cls(**row_data)
                    session.add(instance)
                    
        await session.commit()
    print("✅ Восстановление базы данных успешно завершено!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Укажите путь к файлу бэкапа. Пример: python restore_db.py backup.json")
        sys.exit(1)
        
    asyncio.run(restore(sys.argv[1]))

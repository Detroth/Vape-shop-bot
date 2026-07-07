import tempfile
import json
import os
import enum
from datetime import datetime
from decimal import Decimal
from aiogram import Router
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command, BaseFilter
from sqlalchemy import select, delete

from core.config import settings
from core.database import async_session_maker
from core.models import (
    User, Category, Product, Order, OrderItem, 
    Promocode, FortunePrize, FortuneHistory, UserBonus, DeliveryTime
)

backup_router = Router()

class BackupAdminFilter(BaseFilter):
    """Фильтр для проверки, что сообщение пришло именно от владельца/админа резервного бота."""
    async def __call__(self, message: Message) -> bool:
        if not settings.backup_admin_id:
            return False
        return message.from_user.id == settings.backup_admin_id

def model_to_dict(model_instance) -> dict:
    """Вспомогательная функция для сериализации объекта SQLAlchemy модели в словарь."""
    if not model_instance:
        return None
    d = {}
    for column in model_instance.__table__.columns:
        val = getattr(model_instance, column.name)
        if isinstance(val, Decimal):
            d[column.name] = float(val)
        elif isinstance(val, datetime):
            d[column.name] = val.isoformat()
        elif isinstance(val, enum.Enum):
            d[column.name] = val.value
        else:
            d[column.name] = val
    return d

@backup_router.message(Command("start"), BackupAdminFilter())
async def cmd_start(message: Message):
    """Обработчик команды /start для резервного администратора."""
    await message.answer(
        "👋 <b>Резервная панель управления Vape Shop</b>\n\n"
        "Этот бот имеет прямой доступ к базе данных и предназначен для экстренных "
        "бэкапов на случай проблем с инфраструктурой (например, если Railway перестанет быть доступен).\n\n"
        "<b>Доступные команды управления:</b>\n"
        "📁 /backup — выгрузить полную резервную копию БД (JSON)\n"
        "👥 /users — посмотреть список клиентов и их балансы\n\n"
        "<b>Команды очистки (защита от абуза):</b>\n"
        "🔄 /clear_spins — сбросить историю кручений (все смогут крутить колесо снова)\n"
        "🎁 /clear_bonuses — удалить все выигранные неиспользованные бонусы клиентов\n"
        "🎯 /clear_prizes — очистить список призов колеса фортуны\n\n"
        "ℹ️ Доступ закрыт для всех аккаунтов, кроме указанного в коде или настройках.",
        parse_mode="HTML"
    )

@backup_router.message(Command("backup"), BackupAdminFilter())
async def cmd_backup(message: Message):
    """Обработчик команды /backup для экспорта базы данных."""
    status_msg = await message.answer("⌛ Подготовка резервной копии базы данных...")
    try:
        async with async_session_maker() as session:
            # Делаем запросы ко всем таблицам
            users_res = await session.execute(select(User))
            categories_res = await session.execute(select(Category))
            products_res = await session.execute(select(Product))
            orders_res = await session.execute(select(Order))
            items_res = await session.execute(select(OrderItem))
            promo_res = await session.execute(select(Promocode))
            prizes_res = await session.execute(select(FortunePrize))
            history_res = await session.execute(select(FortuneHistory))
            bonuses_res = await session.execute(select(UserBonus))
            delivery_res = await session.execute(select(DeliveryTime))

            backup_data = {
                "backup_created_at": datetime.now().isoformat(),
                "users": [model_to_dict(u) for u in users_res.scalars().all()],
                "categories": [model_to_dict(c) for c in categories_res.scalars().all()],
                "products": [model_to_dict(p) for p in products_res.scalars().all()],
                "orders": [model_to_dict(o) for o in orders_res.scalars().all()],
                "order_items": [model_to_dict(i) for i in items_res.scalars().all()],
                "promocodes": [model_to_dict(pr) for pr in promo_res.scalars().all()],
                "fortune_prizes": [model_to_dict(fp) for fp in prizes_res.scalars().all()],
                "fortune_history": [model_to_dict(fh) for fh in history_res.scalars().all()],
                "user_bonuses": [model_to_dict(ub) for ub in bonuses_res.scalars().all()],
                "delivery_times": [model_to_dict(dt) for dt in delivery_res.scalars().all()]
            }

        # Создаем временный файл
        temp_dir = tempfile.gettempdir()
        filename = f"vapesha_db_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_path = os.path.join(temp_dir, filename)
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)

        input_file = FSInputFile(file_path, filename=filename)
        
        await message.answer_document(
            document=input_file,
            caption=(
                f"📦 <b>Резервная копия базы данных успешно создана!</b>\n\n"
                f"👥 Клиентов: {len(backup_data['users'])}\n"
                f"🛍 Товаров: {len(backup_data['products'])}\n"
                f"🛒 Заказов: {len(backup_data['orders'])}\n"
                f"🎟 Промокодов: {len(backup_data['promocodes'])}\n"
                f"🎁 Выигранных бонусов: {len(backup_data['user_bonuses'])}"
            ),
            parse_mode="HTML"
        )
        
        # Удаляем временный файл с диска
        try:
            os.remove(file_path)
        except Exception:
            pass

        await status_msg.delete()
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Произошла ошибка при создании бэкапа: {e}")

@backup_router.message(Command("users"), BackupAdminFilter())
async def cmd_users(message: Message):
    """Отображение краткой сводки по пользователям."""
    async with async_session_maker() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
    
    if not users:
        await message.answer("👥 В базе данных пока нет зарегистрированных клиентов.")
        return
        
    text = f"👥 <b>Список клиентов (Всего в базе: {len(users)}):</b>\n\n"
    for idx, u in enumerate(users[:30], 1):  # Показываем только первые 30 записей в сообщении
        username_str = f"@{u.username}" if u.username else "нет юзернейма"
        text += f"{idx}. 🆔 <code>{u.telegram_id}</code> | {username_str} | Баланс: <b>{u.balance} Br</b> | Бонусы: <b>{u.bonus_points}</b>\n"
        
    if len(users) > 30:
        text += f"\n...и еще {len(users) - 30} клиентов. Для получения полных данных сделайте бэкап (/backup)."
        
    await message.answer(text, parse_mode="HTML")

@backup_router.message(Command("clear_spins"), BackupAdminFilter())
async def cmd_clear_spins(message: Message):
    """Сброс истории кручений колеса фортуны для всех пользователей."""
    try:
        async with async_session_maker() as session:
            async with session.begin():
                await session.execute(delete(FortuneHistory))
        await message.answer("✅ <b>История кручений колеса фортуны очищена.</b> Теперь все пользователи могут крутить колесо снова!", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка при очистке истории кручений: {e}")

@backup_router.message(Command("clear_bonuses"), BackupAdminFilter())
async def cmd_clear_bonuses(message: Message):
    """Удаление всех выигранных призов/бонусов пользователей."""
    try:
        async with async_session_maker() as session:
            async with session.begin():
                await session.execute(delete(UserBonus))
        await message.answer("✅ <b>Все выигранные бонусы/призы пользователей удалены из базы.</b>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка при очистке бонусов: {e}")

@backup_router.message(Command("clear_users"), BackupAdminFilter())
async def cmd_clear_users(message: Message):
    """Удаление всех пользователей."""
    try:
        async with async_session_maker() as session:
            async with session.begin():
                await session.execute(delete(User))
        await message.answer("✅ <b>Все пользователи удалены из базы.</b>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка при очистке пользователей: {e}")

@backup_router.message(Command("clear_prizes"), BackupAdminFilter())
async def cmd_clear_prizes(message: Message):
    """Удаление списка призов колеса фортуны."""
    try:
        async with async_session_maker() as session:
            async with session.begin():
                await session.execute(delete(FortunePrize))
        await message.answer("✅ <b>Настройки доступных призов колеса фортуны (FortunePrize) удалены.</b>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка при очистке призов: {e}")

@backup_router.message()
async def ignore_non_admins(message: Message):
    """Игнорируем любые входящие сообщения от неавторизованных аккаунтов."""
    # Никакой реакции, чтобы бот казался выключенным для посторонних лиц.
    pass

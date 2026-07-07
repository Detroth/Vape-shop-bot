# Архитектура и Руководство по Резервному Копированию (Vape Shop Bot)

Этот документ содержит детальное описание архитектуры проекта, жизненного цикла приложения, схемы работы с Telegram-ботом, а также руководство по обеспечению фундаментальной отказоустойчивости, очистке и резервному копированию базы данных.

---

## 1. Схема работы и инициализации приложения

Приложение совмещает в себе асинхронный веб-сервер **FastAPI** (для обслуживания API Mini App и панели администратора) и одного Telegram-бота на библиотеке **Aiogram 3.x** (который обслуживает как обычных клиентов, так и специальные команды владельца/администратора).

### Схема жизненного цикла (Lifespan) в [main.py](file:///Users/dmitriyliakhovets/Documents/Baryga_Proj/main.py):

```mermaid
graph TD
    A[Запуск uvicorn main:app] --> B[lifespan: Подключение к БД]
    B --> C[lifespan: Создание таблиц init_db]
    C --> D[lifespan: Наполнение начальными данными setup_initial_database]
    D --> E[lifespan: Запуск Polling основного бота]
    E --> F[Приложение готово и обслуживает запросы]
    F --> G[Завершение работы / Остановка сервера]
    G --> H[lifespan: Остановка Polling задачи]
    H --> I[lifespan: Закрытие сессии бота]
```

### Основные пути и файлы инициализации:

1. **Загрузка конфигурации**:
   - Путь: [core/config.py](file:///Users/dmitriyliakhovets/Documents/Baryga_Proj/core/config.py)
   - При старте `Settings()` считывает переменные из окружения или файла `.env` с помощью библиотеки `pydantic-settings`.
   - Автоматически трансформирует стандартную строку подключения PostgreSQL (`postgresql://...` или `postgres://...`), генерируемую Railway, в асинхронный формат `postgresql+asyncpg://` для корректной работы SQLAlchemy.

2. **Подключение к БД**:
   - Путь: [core/database.py](file:///Users/dmitriyliakhovets/Documents/Baryga_Proj/core/database.py)
   - Создается асинхронный движок SQLAlchemy (`create_async_engine`) и фабрика сессий `async_session_maker`.
   - В функции `init_db()` регистрируются все модели данных из [core/models.py](file:///Users/dmitriyliakhovets/Documents/Baryga_Proj/core/models.py) и создаются таблицы (если они отсутствуют).

3. **Инициализация бота и роутеров**:
   - Путь: [main.py](file:///Users/dmitriyliakhovets/Documents/Baryga_Proj/main.py)
   - Бот инициализируется глобально через `settings.bot_token`. К нему подключаются роутеры `start_router` и `admin_router`.
   - Вся логика для администратора (включая команды бэкапа и очистки) находится в роутере `admin_router`.

---

## 2. Схема работы с переменными окружения

Программа считывает настройки из системного окружения (Environment) или локального файла `.env`.
Все переменные описаны в [core/config.py](file:///Users/dmitriyliakhovets/Documents/Baryga_Proj/core/config.py):

* `BOT_TOKEN` — API токен Telegram-бота.
* `MINI_APP_URL` — ссылка на веб-интерфейс (Mini App).
* `DATABASE_URL` / `POSTGRES_URL` — строка подключения к базе данных PostgreSQL.
* `ADMIN_CHAT_ID` — ID чата, куда приходят уведомления о новых заказах и заявки на пополнение.
* `BACKUP_ADMIN_ID` — Ваш личный Telegram ID (число, например `1115714808`), которому разрешено выполнять резервные команды.

---

## 3. Методы добавления и удаления данных в БД (SQLAlchemy)

### Как добавляются данные в коде:
Для работы с базой данных используется **SQLAlchemy ORM**. Добавление новой записи происходит через сессию:
1. Создается экземпляр модели: `new_item = ModelClass(field1=value1, ...)`
2. Добавляется в сессию: `session.add(new_item)`
3. Изменения сохраняются: `await session.commit()` (или `await session.flush()`, чтобы получить автогенерируемый ID до коммита).

**Примеры в коде:**
* Создание заказа: файл [api/routes/orders.py:L97-L115](file:///Users/dmitriyliakhovets/Documents/Baryga_Proj/api/routes/orders.py#L97-L115) (строка `db.add(new_order)`).
* Сохранение выигрыша Колеса фортуны: файл [api/routes/fortune.py:L90-L108](file:///Users/dmitriyliakhovets/Documents/Baryga_Proj/api/routes/fortune.py#L90-L108) (строки `db.add(new_bonus)` и `db.add(new_history)`).
* Начальный посев товаров: файл [core/database.py:L36-L59](file:///Users/dmitriyliakhovets/Documents/Baryga_Proj/core/database.py#L36-L59) (метод `session.add_all([...])`).

### Как удаляются данные в коде:
Удаление выполняется либо через асинхронную сессию по объекту:
```python
await session.delete(instance)
await session.commit()
```
Либо через массовый SQL-запрос `delete()` (чтобы очистить таблицу целиком или удалить группу строк по фильтру):
```python
from sqlalchemy import delete
await session.execute(delete(ModelClass).where(ModelClass.field == value))
await session.commit()
```

---

## 4. Административные команды бэкапа и экстренной очистки

В основного бота (модуль [bot/handlers/admin.py](file:///Users/dmitriyliakhovets/Documents/Baryga_Proj/bot/handlers/admin.py)) интегрирован блок команд, защищенных фильтром `BackupAdminFilter`. Они доступны **исключительно владельцу `BACKUP_ADMIN_ID`**. Бот просто не будет реагировать на эти команды, если их отправит обычный клиент.

### Доступные команды очистки и управления:
* `/backup` — Генерация полной резервной копии всей БД в файл JSON и его отправка вам в чат.
* `/users` — Список первых 30 зарегистрированных клиентов с их балансами и бонусами.
* `/lock` — Полная блокировка работы бота и сайта (режим обслуживания). Бот перестает реагировать на пользователей, а сайт возвращает статус `503 Service Unavailable` для всех запросов кроме системных.
* `/unlock <секретное_слово>` — Разблокировка работы бота и сайта с проверкой секретного слова.
* `/clear_spins` — Сброс истории кручений (`FortuneHistory`). Позволяет всем пользователям сразу крутить Колесо заново (снимает ограничение 24 часа).
* `/clear_bonuses` — Удаляет все выигранные купоны и подарки пользователей (`UserBonus`). Помогает сбросить ошибочно выданные призы.
* `/clear_users` — Полностью очищает базу данных клиентов (`User`).
* `/clear_prizes` — Удаляет весь пул призов колеса фортуны (`FortunePrize`).

---

## 5. Как жестко зашить ваши настройки в код («Фундаментально»)

Если вы хотите быть абсолютно уверенными, что ваши административные права и секретное слово сохранятся на любом сервере даже без настроенных переменных окружения, пропишите их напрямую в файл [core/config.py](file:///Users/dmitriyliakhovets/Documents/Baryga_Proj/core/config.py):

```python
# Измените значения Field(default=...) на ваши реальные:
backup_admin_id: Optional[int] = Field(default=1115714808, description="Telegram ID владельца/администратора для резервных команд")
maintenance_secret_word: str = Field(default="supersecret", description="Секретное слово для разблокировки бота/сайта")
```

---

## 6. План экстренного восстановления при отключении Railway

1. Периодически вызывайте `/backup` в боте и сохраняйте JSON-файл на ПК.
2. При отключении Railway установите бота на другой сервер/компьютер.
3. Настройте подключение к новой базе данных (например, локальной SQLite `sqlite+aiosqlite:///./vape_shop.db` в `DATABASE_URL`).
4. Запустите скрипт восстановления:
   ```bash
   python restore_db.py <имя_файла_бэкапа>.json
   ```
5. Скрипт [restore_db.py](file:///Users/dmitriyliakhovets/Documents/Baryga_Proj/restore_db.py) автоматически создаст таблицы и импортирует туда все данные клиентов, товаров и заказов.

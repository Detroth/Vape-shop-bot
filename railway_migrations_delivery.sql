-- Создание таблицы для времени платной доставки
CREATE TABLE IF NOT EXISTS delivery_times (
    id SERIAL PRIMARY KEY,
    time_slot VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- Добавление полей даты и времени в заказы
ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_date VARCHAR(20);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_time VARCHAR(50);

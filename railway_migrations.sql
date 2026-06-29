-- Миграции для Railway (PostgreSQL)
-- Добавление новых полей в существующие таблицы

-- Таблица users
ALTER TABLE users ADD COLUMN IF NOT EXISTS bonus_points INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS personal_discount INTEGER DEFAULT 0;

-- Таблица products
ALTER TABLE products ADD COLUMN IF NOT EXISTS characteristics JSON;

-- Таблица order_items
ALTER TABLE order_items ADD COLUMN IF NOT EXISTS variant VARCHAR(100);

-- Таблица orders
ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_type VARCHAR(20) DEFAULT 'delivery';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_name VARCHAR(255);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_phone VARCHAR(50);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_tg_username VARCHAR(255);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS comment TEXT;

-- Создание новой таблицы user_bonuses, если она отсутствует
CREATE TABLE IF NOT EXISTS user_bonuses (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id) ON DELETE CASCADE,
    prize_name VARCHAR(255) NOT NULL,
    prize_type VARCHAR(50) NOT NULL,
    value NUMERIC(10, 2) NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

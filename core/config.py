# core/config.py
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, AliasChoices

class Settings(BaseSettings):
    bot_token: str = Field(..., description="Токен Telegram бота")
    mini_app_url: str = Field(..., description="URL Mini App")
    admin_chat_id: int = Field(default=0, description="ID чата администраторов")
    
    # Прямая ссылка на БД, которую Railway выдает автоматически
    database_url: str = Field(
        ..., 
        validation_alias=AliasChoices("DATABASE_URL", "POSTGRES_URL"),
        description="Полная строка подключения к БД (Railway)"
    )
    
    port: int = Field(default=8000, description="Порт для FastAPI")

    admin_username: str = Field("admin", description="Логин админ-панели")
    admin_password: str = Field("admin", description="Пароль админ-панели")
    admin_secret_key: str = Field("secret", description="Секретный ключ для куки сессий")
    
    # YooKassa
    yookassa_shop_id: Optional[str] = Field(default=None, description="Shop ID в ЮKassa")
    yookassa_secret_key: Optional[str] = Field(default=None, description="Секретный ключ (Secret Key) ЮKassa")

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_postgres_url(cls, v: str) -> str:
        # Railway выдает стандартную ссылку postgresql://..., но для асинхронной SQLAlchemy нужен asyncpg
        if isinstance(v, str):
            if v.startswith("postgresql://"):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

settings = Settings()

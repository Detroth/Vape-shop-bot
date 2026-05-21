# core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    bot_token: str = Field(..., description="Токен Telegram бота")
    # Пример формата: mysql+aiomysql://user:pass@localhost:3306/vape_shop
    database_url: str = Field(..., description="URL для подключения к MySQL")
    admin_chat_id: int = Field(default=0, description="ID чата администраторов")
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

settings = Settings()

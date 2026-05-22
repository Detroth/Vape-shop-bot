# core/config.py
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, computed_field, AliasChoices

class Settings(BaseSettings):
    bot_token: str = Field(..., description="Токен Telegram бота")
    mini_app_url: str = Field(..., description="URL Mini App")
    admin_chat_id: int = Field(default=0, description="ID чата администраторов")
    
    # Делаем поля БД опциональными со значениями по умолчанию
    db_host: str = Field(default="localhost", validation_alias=AliasChoices("DB_HOST", "MYSQLHOST", "MYSQL_HOST"), description="Хост БД")
    db_port: int = Field(default=3306, validation_alias=AliasChoices("DB_PORT", "MYSQLPORT", "MYSQL_PORT"), description="Порт БД")
    db_user: str = Field(default="root", validation_alias=AliasChoices("DB_USER", "MYSQLUSER", "MYSQL_USER"), description="Пользователь БД")
    db_pass: str = Field(default="", validation_alias=AliasChoices("DB_PASS", "MYSQLPASSWORD", "MYSQL_PASSWORD"), description="Пароль БД")
    db_name: str = Field(default="vape_shop", validation_alias=AliasChoices("DB_NAME", "MYSQLDATABASE", "MYSQL_DATABASE"), description="Имя БД")
    
    # Прямая ссылка на БД, которую Railway выдает автоматически (MYSQL_URL)
    database_url_env: Optional[str] = Field(default=None, validation_alias=AliasChoices("DATABASE_URL", "MYSQL_URL", "MYSQLURL"))
    
    port: int = Field(default=8000, description="Порт для FastAPI")

    admin_username: str = Field("admin", description="Логин админ-панели")
    admin_password: str = Field("admin", description="Пароль админ-панели")
    admin_secret_key: str = Field("secret", description="Секретный ключ для куки сессий")
    
    @computed_field
    @property
    def database_url(self) -> str:
        # Если Railway передал готовую ссылку, используем её (заменив синхронный драйвер на aiomysql)
        if self.database_url_env:
            if self.database_url_env.startswith("mysql://"):
                return self.database_url_env.replace("mysql://", "mysql+aiomysql://", 1)
            return self.database_url_env
            
        # Иначе собираем из отдельных переменных
        return f"mysql+aiomysql://{self.db_user}:{self.db_pass}@{self.db_host}:{self.db_port}/{self.db_name}"

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

settings = Settings()

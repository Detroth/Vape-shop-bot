# core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, computed_field, AliasChoices

class Settings(BaseSettings):
    bot_token: str = Field(..., description="Токен Telegram бота")
    mini_app_url: str = Field(..., description="URL Mini App")
    admin_chat_id: int = Field(default=0, description="ID чата администраторов")
    
    db_host: str = Field(..., validation_alias=AliasChoices("DB_HOST", "MYSQLHOST"), description="Хост БД")
    db_port: int = Field(3306, validation_alias=AliasChoices("DB_PORT", "MYSQLPORT"), description="Порт БД")
    db_user: str = Field(..., validation_alias=AliasChoices("DB_USER", "MYSQLUSER"), description="Пользователь БД")
    db_pass: str = Field(..., validation_alias=AliasChoices("DB_PASS", "MYSQLPASSWORD"), description="Пароль БД")
    db_name: str = Field(..., validation_alias=AliasChoices("DB_NAME", "MYSQLDATABASE"), description="Имя БД")
    
    port: int = Field(8000, description="Порт для FastAPI")

    admin_username: str = Field("admin", description="Логин админ-панели")
    admin_password: str = Field("admin", description="Пароль админ-панели")
    admin_secret_key: str = Field("secret", description="Секретный ключ для куки сессий")
    
    @computed_field
    @property
    def database_url(self) -> str:
        return f"mysql+aiomysql://{self.db_user}:{self.db_pass}@{self.db_host}:{self.db_port}/{self.db_name}"

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

settings = Settings()

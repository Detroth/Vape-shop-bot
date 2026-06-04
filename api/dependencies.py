import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl
from fastapi import Header, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.config import settings
from core.database import get_db
from core.models import User

def verify_telegram_webapp_data(request: Request, x_telegram_init_data: str = Header(None, alias="X-Telegram-Init-Data")) -> dict:
    """
    Валидирует данные initData от Telegram, проверяет auth_date и возвращает dict с данными пользователя.
    """
    init_data = x_telegram_init_data
    auth_header = request.headers.get("Authorization")
    if not init_data and auth_header and auth_header.startswith("Bearer "):
        init_data = auth_header.split(" ", 1)[1]

    if not init_data:
        raise HTTPException(status_code=401, detail="Missing Telegram initData")
        
    try:
        parsed_data = dict(parse_qsl(init_data))
        hash_val = parsed_data.pop('hash')
        
        auth_date = int(parsed_data.get('auth_date', 0))
        if time.time() - auth_date > 86400:  # Старше 24 часов
            raise HTTPException(status_code=403, detail="Invalid credentials: Data is outdated")

        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed_data.items())
        )
        
        secret_key = hmac.new(
            "WebAppData".encode(), settings.bot_token.encode(), hashlib.sha256
        ).digest()
        
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()
        
        if calculated_hash != hash_val:
            raise HTTPException(status_code=403, detail="Invalid credentials: Hash mismatch")
            
        user_data = json.loads(parsed_data['user'])
        return user_data
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid credentials")

async def get_current_user(
    user_data: dict = Depends(verify_telegram_webapp_data),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Универсальная зависимость: проверяет подпись Telegram и возвращает ORM-объект User из базы.
    Использовать во всех защищенных эндпоинтах.
    """
    result = await db.execute(select(User).where(User.telegram_id == user_data["id"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not registered. Please log in first.")
    return user
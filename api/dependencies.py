import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl
from fastapi import Header, HTTPException

from core.config import settings

def verify_telegram_webapp_data(x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data")) -> dict:
    """
    Валидирует данные initData от Telegram, проверяет auth_date и возвращает dict с данными пользователя.
    """
    try:
        parsed_data = dict(parse_qsl(x_telegram_init_data))
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
import hashlib
import hmac
import json
from urllib.parse import parse_qsl
from fastapi import Header, HTTPException

from core.config import settings

def verify_telegram_web_app_data(x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data")) -> int:
    """
    Валидирует данные initData от Telegram и возвращает telegram_id пользователя.
    """
    try:
        parsed_data = dict(parse_qsl(x_telegram_init_data))
        hash_val = parsed_data.pop('hash')
        
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
            raise HTTPException(status_code=401, detail="Неверная подпись Telegram")
            
        user_data = json.loads(parsed_data['user'])
        return user_data['id']
    except Exception:
        raise HTTPException(status_code=401, detail="Ошибка валидации InitData")
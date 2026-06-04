from fastapi import APIRouter

from .user import router as user_router
from .catalog import router as catalog_router
from .cart import router as cart_router
from .orders import router as orders_router
from .payments import router as payments_router

api_router = APIRouter()

api_router.include_router(user_router)
api_router.include_router(catalog_router)
api_router.include_router(cart_router)
api_router.include_router(orders_router)
api_router.include_router(payments_router)
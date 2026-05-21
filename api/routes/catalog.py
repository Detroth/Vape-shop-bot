from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc, desc
from pydantic import BaseModel

from core.database import get_db
from core.models import Category, Product

router = APIRouter(prefix="/catalog", tags=["Catalog"])

# --- Pydantic Схемы ---
class CategoryOut(BaseModel):
    id: int
    name: str

class ProductOut(BaseModel):
    id: int
    name: str
    price: float
    stock: int
    image_url: Optional[str] = None

@router.get("/categories", response_model=List[CategoryOut])
async def get_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category))
    return result.scalars().all()

@router.get("/categories/{category_id}/products", response_model=List[ProductOut])
async def get_products(category_id: int, sort_price: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    query = select(Product).where(Product.category_id == category_id)
    
    if sort_price == "asc":
        query = query.order_by(asc(Product.price))
    elif sort_price == "desc":
        query = query.order_by(desc(Product.price))
        
    result = await db.execute(query)
    return result.scalars().all()
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc, desc, or_

from core.database import get_db
from core.models import Category, Product
from api.schemas import CategoryResponse, ProductResponse

router = APIRouter(prefix="/catalog", tags=["Catalog"])

@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category))
    return result.scalars().all()

@router.get("/products", response_model=List[ProductResponse])
async def get_products(
    category_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query(None, description="cheapest, expensive, alphabetical"),
    db: AsyncSession = Depends(get_db)
):
    query = select(Product)
    
    if category_id is not None:
        query = query.where(Product.category_id == category_id)
        
    if search:
        search_term = f"%{search}%"
        query = query.where(or_(
            Product.name.ilike(search_term),
            Product.description.ilike(search_term)
        ))
        
    if sort == "cheapest":
        query = query.order_by(asc(Product.price))
    elif sort == "expensive":
        query = query.order_by(desc(Product.price))
    elif sort == "alphabetical":
        query = query.order_by(asc(Product.name))
        
    result = await db.execute(query)
    return result.scalars().all()
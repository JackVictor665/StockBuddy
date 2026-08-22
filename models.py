from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    category: str = Field(index=True)
    sku: str = Field(index=True, unique=True)
    cost_price: float
    selling_price: float
    current_stock: int = Field(default=0)
    min_stock_alert: int = Field(default=5)
    lead_time_days: int = Field(default=7)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str


class Sale(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    quantity_sold: int
    sale_price: float
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)


class ProductCreate(SQLModel):
    name: str
    category: str
    sku: str
    cost_price: float
    selling_price: float
    current_stock: int = 0
    min_stock_alert: int = 5
    lead_time_days: int = 7


class ProductUpdate(SQLModel):
    name: Optional[str] = None
    category: Optional[str] = None
    sku: Optional[str] = None
    cost_price: Optional[float] = None
    selling_price: Optional[float] = None
    current_stock: Optional[int] = None
    min_stock_alert: Optional[int] = None
    lead_time_days: Optional[int] = None


class SaleCreate(SQLModel):
    product_id: int
    quantity_sold: int = Field(gt=0)
    sale_price: Optional[float] = None


class SaleUpdate(SQLModel):
    product_id: Optional[int] = None
    quantity_sold: Optional[int] = Field(default=None, gt=0)
    sale_price: Optional[float] = None

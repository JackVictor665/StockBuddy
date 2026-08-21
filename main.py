from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from analytics import get_profit_forecast, get_profit_projections, get_restock_recommendations, get_stock_depletion_forecast
from database import get_session, init_db
from models import Product, ProductCreate, Sale, SaleCreate

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="StockBuddy", description="PC hardware inventory intelligence")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
SessionDep = Annotated[Session, Depends(get_session)]


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/products", response_model=list[Product])
def list_products(session: SessionDep):
    return session.exec(select(Product).order_by(Product.category, Product.name)).all()


@app.post("/api/products", response_model=Product, status_code=201)
def add_product(product: ProductCreate, session: SessionDep):
    if session.exec(select(Product).where(Product.sku == product.sku)).first():
        raise HTTPException(409, "SKU already exists")
    record = Product.model_validate(product)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@app.post("/api/sales", response_model=Sale, status_code=201)
def record_sale(sale: SaleCreate, session: SessionDep):
    product = session.get(Product, sale.product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    if sale.quantity_sold > product.current_stock:
        raise HTTPException(400, "Insufficient stock")
    product.current_stock -= sale.quantity_sold
    record = Sale(product_id=product.id, quantity_sold=sale.quantity_sold, sale_price=sale.sale_price or product.selling_price)
    session.add(record)
    session.add(product)
    session.commit()
    session.refresh(record)
    return record


@app.get("/api/forecast")
def forecast(session: SessionDep, horizon_days: int = 30):
    return {"depletion": get_stock_depletion_forecast(session), "restock": get_restock_recommendations(session), "profit": get_profit_projections(session), "profit_forecast": get_profit_forecast(session, horizon_days)}


def page_context(request: Request, session: Session, horizon_days: int = 30) -> dict:
    products = session.exec(select(Product).order_by(Product.category, Product.name)).all()
    sales = session.exec(select(Sale).order_by(Sale.timestamp.desc()).limit(12)).all()
    by_id = {product.id: product for product in products}
    total_stock_value = sum(product.current_stock * product.cost_price for product in products)
    profits = get_profit_projections(session)
    return {"request": request, "products": products, "sales": sales, "by_id": by_id, "forecast": get_stock_depletion_forecast(session), "restock": get_restock_recommendations(session), "profits": profits, "total_stock_value": total_stock_value, "projected_profit": sum(item["monthly_profit"] for item in profits), "low_stock_count": len(get_restock_recommendations(session)), "horizon_days": horizon_days, "profit_forecast": get_profit_forecast(session, horizon_days)}


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: SessionDep):
    return templates.TemplateResponse(request=request, name="dashboard.html", context=page_context(request, session))


@app.get("/inventory", response_class=HTMLResponse)
def inventory(request: Request, session: SessionDep):
    return templates.TemplateResponse(request=request, name="inventory.html", context=page_context(request, session))


@app.post("/inventory", response_class=HTMLResponse)
def create_inventory_item(name: str = Form(...), category: str = Form(...), sku: str = Form(...), cost_price: float = Form(...), selling_price: float = Form(...), current_stock: int = Form(...), min_stock_alert: int = Form(...), lead_time_days: int = Form(...), session: Session = Depends(get_session)):
    session.add(Product(name=name, category=category, sku=sku, cost_price=cost_price, selling_price=selling_price, current_stock=current_stock, min_stock_alert=min_stock_alert, lead_time_days=lead_time_days))
    session.commit()
    return RedirectResponse("/inventory", status_code=303)


@app.get("/forecasting", response_class=HTMLResponse)
def forecasting(request: Request, session: SessionDep, horizon_days: int = 30):
    if horizon_days not in (3, 7, 30, 90):
        horizon_days = 30
    return templates.TemplateResponse(request=request, name="forecasting.html", context=page_context(request, session, horizon_days))


@app.get("/sales", response_class=HTMLResponse)
def sales_page(request: Request, session: SessionDep):
    return templates.TemplateResponse(request=request, name="sales.html", context=page_context(request, session))


@app.post("/sales", response_class=HTMLResponse)
def create_sale(product_id: int = Form(...), quantity_sold: int = Form(...), session: Session = Depends(get_session)):
    product = session.get(Product, product_id)
    if not product or quantity_sold > product.current_stock:
        raise HTTPException(400, "Unable to record sale: check product and available stock")
    product.current_stock -= quantity_sold
    session.add(Sale(product_id=product_id, quantity_sold=quantity_sold, sale_price=product.selling_price))
    session.commit()
    return RedirectResponse("/sales", status_code=303)

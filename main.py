from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from analytics import get_profit_forecast, get_profit_projections, get_restock_recommendations, get_stock_depletion_forecast
from database import get_session, init_db
from models import Product, ProductCreate, ProductUpdate, Sale, SaleCreate, SaleUpdate
from seed_data import seed

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="StockBuddy", description="PC hardware inventory intelligence")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/resources", StaticFiles(directory=BASE_DIR / "resources"), name="resources")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
SessionDep = Annotated[Session, Depends(get_session)]


@app.on_event("startup")
def startup() -> None:
    init_db()
    seed()


@app.get("/healthz")
def health_check():
    return {"status": "ok", "service": "stockbuddy"}


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


@app.put("/api/products/{product_id}", response_model=Product)
def update_product(product_id: int, product: ProductUpdate, session: SessionDep):
    record = session.get(Product, product_id)
    if not record:
        raise HTTPException(404, "Product not found")
    if product.sku and session.exec(select(Product).where(Product.sku == product.sku, Product.id != product_id)).first():
        raise HTTPException(409, "SKU already exists")
    for field, value in product.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@app.delete("/api/products/{product_id}", status_code=204)
def delete_product(product_id: int, session: SessionDep):
    record = session.get(Product, product_id)
    if not record:
        raise HTTPException(404, "Product not found")
    for sale in session.exec(select(Sale).where(Sale.product_id == product_id)).all():
        session.delete(sale)
    session.delete(record)
    session.commit()


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


@app.put("/api/sales/{sale_id}", response_model=Sale)
def update_sale(sale_id: int, sale: SaleUpdate, session: SessionDep):
    record = session.get(Sale, sale_id)
    if not record:
        raise HTTPException(404, "Sale not found")
    old_product = session.get(Product, record.product_id)
    new_product = session.get(Product, sale.product_id or record.product_id)
    new_quantity = sale.quantity_sold if sale.quantity_sold is not None else record.quantity_sold
    if not new_product:
        raise HTTPException(404, "Product not found")
    if old_product.id == new_product.id:
        available = old_product.current_stock + record.quantity_sold
        if new_quantity > available:
            raise HTTPException(400, "Insufficient stock")
        old_product.current_stock = available - new_quantity
    else:
        old_product.current_stock += record.quantity_sold
        if new_quantity > new_product.current_stock:
            raise HTTPException(400, "Insufficient stock")
        new_product.current_stock -= new_quantity
    record.product_id = new_product.id
    record.quantity_sold = new_quantity
    if sale.sale_price is not None:
        record.sale_price = sale.sale_price
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@app.delete("/api/sales/{sale_id}", status_code=204)
def delete_sale(sale_id: int, session: SessionDep):
    record = session.get(Sale, sale_id)
    if not record:
        raise HTTPException(404, "Sale not found")
    product = session.get(Product, record.product_id)
    if product:
        product.current_stock += record.quantity_sold
        session.add(product)
    session.delete(record)
    session.commit()


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


@app.get("/inventory/{product_id}/edit", response_class=HTMLResponse)
def edit_inventory_page(product_id: int, request: Request, session: SessionDep):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    return templates.TemplateResponse(request=request, name="edit_inventory.html", context={"request": request, "product": product})


@app.post("/inventory/{product_id}/edit")
def edit_inventory(product_id: int, name: str = Form(...), category: str = Form(...), sku: str = Form(...), cost_price: float = Form(...), selling_price: float = Form(...), current_stock: int = Form(...), min_stock_alert: int = Form(...), lead_time_days: int = Form(...), session: Session = Depends(get_session)):
    update_product(product_id, ProductUpdate(name=name, category=category, sku=sku, cost_price=cost_price, selling_price=selling_price, current_stock=current_stock, min_stock_alert=min_stock_alert, lead_time_days=lead_time_days), session)
    return RedirectResponse("/inventory", status_code=303)


@app.post("/inventory/{product_id}/delete")
def remove_inventory(product_id: int, session: SessionDep):
    delete_product(product_id, session)
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


@app.get("/sales/{sale_id}/edit", response_class=HTMLResponse)
def edit_sale_page(sale_id: int, request: Request, session: SessionDep):
    sale = session.get(Sale, sale_id)
    if not sale:
        raise HTTPException(404, "Sale not found")
    products = session.exec(select(Product).order_by(Product.name)).all()
    return templates.TemplateResponse(request=request, name="edit_sale.html", context={"request": request, "sale": sale, "products": products})


@app.post("/sales/{sale_id}/edit")
def edit_sale(sale_id: int, product_id: int = Form(...), quantity_sold: int = Form(...), sale_price: float = Form(...), session: Session = Depends(get_session)):
    update_sale(sale_id, SaleUpdate(product_id=product_id, quantity_sold=quantity_sold, sale_price=sale_price), session)
    return RedirectResponse("/sales", status_code=303)


@app.post("/sales/{sale_id}/delete")
def remove_sale(sale_id: int, session: SessionDep):
    delete_sale(sale_id, session)
    return RedirectResponse("/sales", status_code=303)

from datetime import datetime, timedelta

import pandas as pd
from sqlmodel import Session, select

from models import Product, Sale


def _sales_frame(session: Session) -> pd.DataFrame:
    sales = session.exec(select(Sale)).all()
    return pd.DataFrame([
        {"product_id": sale.product_id, "quantity": sale.quantity_sold, "sale_price": sale.sale_price, "timestamp": sale.timestamp}
        for sale in sales
    ])


def get_stock_depletion_forecast(session: Session) -> list[dict]:
    products = session.exec(select(Product)).all()
    frame = _sales_frame(session)
    cutoff = datetime.utcnow() - timedelta(days=30)
    if not frame.empty:
        frame = frame[frame["timestamp"] >= cutoff]
        velocity = frame.groupby("product_id")["quantity"].sum().div(30).to_dict()
    else:
        velocity = {}

    forecast = []
    for product in products:
        daily_velocity = float(velocity.get(product.id, 0))
        days = round(product.current_stock / daily_velocity, 1) if daily_velocity else 999
        forecast.append({
            "product": product,
            "daily_velocity": round(daily_velocity, 2),
            "days_until_out_of_stock": days,
            "critical": days < 7,
        })
    return sorted(forecast, key=lambda item: item["days_until_out_of_stock"])


def get_profit_projections(session: Session) -> list[dict]:
    products = {product.id: product for product in session.exec(select(Product)).all()}
    frame = _sales_frame(session)
    if frame.empty:
        return []
    frame = frame[frame["timestamp"] >= datetime.utcnow() - timedelta(days=30)].copy()
    if frame.empty:
        return []
    frame["revenue"] = frame["quantity"] * frame["sale_price"]
    frame["profit"] = frame.apply(lambda row: (row["sale_price"] - products[row["product_id"]].cost_price) * row["quantity"], axis=1)
    grouped = frame.groupby("product_id").agg(units=("quantity", "sum"), revenue=("revenue", "sum"), profit=("profit", "sum")).reset_index()
    result = []
    for row in grouped.to_dict("records"):
        product = products[row["product_id"]]
        result.append({"product": product, "units": int(row["units"]), "monthly_revenue": round(float(row["revenue"]), 2), "monthly_profit": round(float(row["profit"]), 2), "margin": round((product.selling_price - product.cost_price) / product.selling_price * 100, 1)})
    return sorted(result, key=lambda item: item["monthly_profit"], reverse=True)


def get_restock_recommendations(session: Session) -> list[dict]:
    return [item for item in get_stock_depletion_forecast(session) if item["product"].current_stock <= item["product"].min_stock_alert or item["days_until_out_of_stock"] < 5]


def get_profit_forecast(session: Session, horizon_days: int = 30) -> dict:
    """Project company profit and the current blended margin by day."""
    horizon_days = max(1, min(horizon_days, 90))
    profits = get_profit_projections(session)
    total_profit = sum(item["monthly_profit"] for item in profits)
    total_revenue = sum(item["monthly_revenue"] for item in profits)
    daily_profit = total_profit / 30
    margin = total_profit / total_revenue * 100 if total_revenue else 0
    labels = ["Today"] + [f"+{day}d" for day in range(1, horizon_days + 1)]
    return {
        "labels": labels,
        "profit": [round(daily_profit * day, 2) for day in range(horizon_days + 1)],
        "margin": [round(margin, 1)] * (horizon_days + 1),
        "daily_profit": round(daily_profit, 2),
        "margin_value": round(margin, 1),
    }

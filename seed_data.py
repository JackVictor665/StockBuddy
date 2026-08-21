import random
from datetime import datetime, timedelta

from sqlmodel import Session, select

from database import engine, init_db
from models import Product, Sale

PRODUCTS = [
    ("NVIDIA RTX 4080 Super", "GPU", "GPU-4080S", 999, 1199, 6, 8, 12),
    ("AMD Radeon RX 7900 XTX", "GPU", "GPU-7900XTX", 780, 949, 11, 6, 10),
    ("Intel Core i7-14700K", "CPU", "CPU-I7147K", 355, 419, 9, 7, 8),
    ("AMD Ryzen 7 7800X3D", "CPU", "CPU-R77800", 320, 399, 14, 8, 9),
    ("Corsair Vengeance 32GB DDR5", "RAM", "RAM-COR32D5", 88, 119, 22, 10, 7),
    ("Samsung 990 Pro 2TB NVMe", "Storage", "SSD-S990P2T", 135, 179, 17, 8, 6),
    ("WD Black SN850X 1TB", "Storage", "SSD-WDSN850", 72, 99, 28, 10, 5),
    ("Corsair RM850x 850W", "PSU", "PSU-RM850X", 115, 159, 7, 8, 14),
    ("be quiet! Pure Power 12 M 750W", "PSU", "PSU-BQ750", 91, 129, 19, 8, 11),
]


def seed() -> None:
    init_db()
    with Session(engine) as session:
        if session.exec(select(Product)).first():
            return
        products = []
        for values in PRODUCTS:
            product = Product(name=values[0], category=values[1], sku=values[2], cost_price=values[3], selling_price=values[4], current_stock=values[5], min_stock_alert=values[6], lead_time_days=values[7])
            session.add(product)
            products.append(product)
        session.commit()
        for product in products:
            session.refresh(product)
        for _ in range(90):
            product = random.choice(products)
            quantity = random.randint(1, 3)
            session.add(Sale(product_id=product.id, quantity_sold=quantity, sale_price=product.selling_price, timestamp=datetime.utcnow() - timedelta(days=random.randint(0, 29), hours=random.randint(0, 23))))
        session.commit()
        print(f"Seeded {len(products)} products and 90 sales.")


if __name__ == "__main__":
    seed()

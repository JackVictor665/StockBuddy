# StockBuddy

PC hardware inventory management with FastAPI, SQLite, SQLModel, Pandas, and Jinja2.

## Run locally

```powershell
python -m pip install -r requirements.txt
python seed_data.py
python -m uvicorn main:app --reload
```

Open http://127.0.0.1:8000 for the dashboard. API documentation is available at `/docs`.

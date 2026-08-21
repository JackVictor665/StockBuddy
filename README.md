# StockBuddy

StockBuddy is a PC hardware inventory and sales intelligence dashboard. It tracks stock, wholesale cost, retail value, sales velocity, profit margins, and restock risk.

## Judge the demo

Open the deployed URL, then start with:

1. **Overview** for the business snapshot and depletion watch.
2. **Inventory** to inspect availability bars and add hardware.
3. **Forecasting** to change the `3 days`, `7 days`, `1 month`, or `3 months` profit horizon.
4. **Sales log** to record a sale and see wholesale price, sale value, unit profit, and total generated profit.

The demo seeds representative PC hardware and historical transactions automatically when the database is empty.

## Deploy on Render

1. Push this repository to GitHub.
2. In Render, choose **New > Blueprint** and select this repository.
3. Render reads `render.yaml` and builds the included `Dockerfile`.
4. Share the generated `onrender.com` URL with judges.

The `/healthz` endpoint is available for deployment checks and `/docs` contains the interactive API documentation.

## Run locally

```powershell
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Open http://127.0.0.1:8000. The first startup seeds the SQLite database automatically.

## Important deployment note

SQLite is suitable for this demo and local judging. A production deployment with multiple simultaneous users should replace it with hosted PostgreSQL and add authentication before sharing operational data publicly.

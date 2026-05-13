# Budget Tracker

AI-powered spending dashboard for credit card CSVs.  
Supports **Robinhood** and **Capital One** exports.  
Uses DeepSeek to categorize every transaction.

## Quick Start

```bash
# Backend
pip install -r requirements.txt
python main.py          # → http://localhost:8000

# Frontend (dev mode)
cd frontend
npm install
npm run dev             # → http://localhost:5173
```

The FastAPI server serves the production React build from `frontend/dist/` automatically on `/`.

## Architecture

```
main.py          FastAPI backend (REST + SSE streaming)
parser.py        CSV parser (auto-detects Robinhood / Capital One)
categorizer.py   DeepSeek LLM integration with local JSON cache
app.py           Standalone NiceGUI app (alternative UI)
frontend/        React 18 + TypeScript + Vite + Tailwind
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload` | Upload CSV → session ID + preview |
| `GET` | `/api/categorize/{session_id}?api_key=…` | SSE stream of categorization progress |
| `GET` | `/api/dashboard/{session_id}` | Full dashboard data (metrics, charts, insights) |

### Categorization

Transactions are classified into 8 categories by DeepSeek V4 Flash:

| Category | Examples |
|----------|----------|
| Dining & Drinks | Restaurants, fast food, coffee, boba |
| Groceries & Essentials | Grocery stores, pharmacies, household |
| Transport | Ride share, gas, transit |
| Shopping | Amazon, Target, retail |
| Travel | Airlines, hotels, Airbnb |
| Subscriptions & Services | Spotify, ChatGPT, insurance |
| Entertainment | Movies, events, parks |
| Fees & Charges | Card fees |

Results are cached in `~/.budget-tracker-cache.json` — re-categorization is instant.

## Environment

- Python 3.11+
- DeepSeek API key (entered in the UI)
- Node.js 18+ (for frontend dev)

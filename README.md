# Budget Tracker

A dark-themed web dashboard for Robinhood credit card CSV analysis.  
Uses DeepSeek AI to categorize every transaction. Built with NiceGUI.

## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Open **http://localhost:8080** — dark theme, no setup needed.

1. Drop your Robinhood CSV into the upload zone
2. Enter your [DeepSeek API key](https://platform.deepseek.com/api_keys)
3. Click **Categorize transactions**
4. Explore the dashboard

## Features

- **AI categorization** — DeepSeek V4 classifies every merchant into 8 categories
- **Local cache** — `~/.budget-tracker-cache.json` so you never pay twice for the same merchant
- **Dashboard** — spending by category, monthly trends, top merchants
- **Transaction browser** — filter by category, search, sort
- **Insights** — top category, recurring payments, largest purchase, trends
- **Dark theme** — minimal, designed for long sessions

## Categories

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

## Tech

- **NiceGUI** — Python web UI (Vue/Quasar components)
- **DeepSeek V4 Flash** — LLM for categorization
- **Plotly** — interactive charts
- **Pandas** — data processing

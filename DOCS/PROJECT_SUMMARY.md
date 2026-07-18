# SM — Stock Market Paper Trading App
### Project Summary

---

## What Is This?

**SM** is a full-stack Indian paper trading application where users invest with **virtual ₹10,000**. The goal is to simulate real stock trading on NSE/BSE without any real financial risk. It functions as an educational investing platform with professional-grade data, AI assistance, and gamification.

---

## Repository Structure

```
SM/
├── BACKEND/          # Python Flask API server
│   ├── invest/       # Core application package
│   ├── run.py        # Entry point (python run.py)
│   ├── .env          # Environment variables
│   ├── requirements-backend.txt
│   └── local_setup.sql / rds_export.sql  # DB schema dumps
└── FRONTEND/         # React (Vite) SPA
    └── src/          # All components, pages, CSS
```

---

## Tech Stack

### Backend
| Layer | Technology |
|---|---|
| Language | Python 3.x |
| Web Framework | Flask 2.3.3 |
| ORM | Flask-SQLAlchemy |
| Database (Primary) | MySQL (local: `localhost:3306/investment`) |
| Database (Cloud) | AWS RDS MySQL (kept as commented backup) |
| Cache | Flask-Caching (in-memory, `simple`) |
| Auth | Custom token-based (`local_<userid>` / `dev_<userid>` Bearer tokens), Firebase (Google SSO) |
| AI / LLM | AWS Bedrock — `apac.amazon.nova-micro-v1:0` (Nova Micro) |
| NoSQL (snapshots) | AWS DynamoDB (used by `insert.py` only, not by the main app) |
| Stock Data | yfinance (Yahoo Finance), NSE library, BSE API |
| News | Google News RSS, GNews API, NewsAPI |
| ML Inference | Hugging Face Spaces (external worker) |
| CORS | Flask-CORS |
| Server | Gunicorn (production) / Flask dev server (local) |

### Frontend
| Layer | Technology |
|---|---|
| Framework | React 18 + Vite 8 |
| Routing | React Router v6 |
| State | React Context (UserContext) + localStorage |
| HTTP Client | Axios |
| Charts | Lightweight Charts (TradingView), Chart.js, Recharts, Plotly |
| Styling | Tailwind CSS + per-component CSS files |
| Icons | Lucide React, React Icons |
| Animations | Framer Motion |
| Tables | @tanstack/react-table |
| Auth (Google) | Firebase SDK |
| Notifications | React Toastify |

---

## Database Schema (MySQL — `investment`)

| Table | Purpose |
|---|---|
| `users` | User accounts — name, email, password hash, wallet (money), P/L, progress score, level |
| `stock` | Master stock list — symbol, name |
| `watchlist` | User ↔ Stock many-to-many (which stocks a user is watching) |
| `portfolio` | User holdings — stock, quantity, avg buy price, total invested, sector |
| `transactionhistory` | Buy/sell audit log per user |
| `fifolot` | FIFO lot tracking for sell cost basis (partially used) |
| `stockhistory` | Per-user weekly price history for portfolio trend charts |
| `stockdata` | Global OHLCV price data (fallback LTP source) |
| `useractivity` | Login streak and activity tracking |
| `milestones` | Achievement definitions (portfolio, profit, consistency types) |
| `usermilestones` | Which milestones each user has unlocked |

**Starting wallet:** ₹10,000 per user.

---

## Backend Architecture

### Entry Point
- `run.py` → calls `create_app()` from `invest/__init__.py`

### Application Factory (`invest/__init__.py`)
- Loads `.env` from absolute path
- Builds `DATABASE_URL` from `DB_HOST/PORT/NAME/USER/PASSWORD` env vars
- Registers 3 Flask blueprints: `routes_bp`, `dashboard_bp`, `auth_bp`
- Sets up CORS for `localhost:3000` and `localhost:5173`
- Configures `SQLALCHEMY_ENGINE_OPTIONS` (`pool_pre_ping`, `pool_recycle`)

### Blueprints / Modules

#### `invest/routes.py` (~5,400 lines — the core API)
All stock data endpoints. Data is fetched **live** from yfinance on every request. A `GLOBAL_CACHE` dict with TTL caches P&L data for 24 hours.

#### `invest/auth.py`
Custom JWT-free auth. Tokens are simple strings like `local_1` or `dev_1`. Supports:
- Email/password signup & login
- OTP-based password reset (OTP logged to server console in dev)
- Google login via Firebase ID token (Firebase Admin SDK)
- Dev login (no password, blocked in production via `FLASK_ENV`)

#### `invest/portfolio.py`
Core trading logic:
- `buy()` / `sell()` — deducts/credits wallet, updates portfolio, records transaction
- `gettingfromdb()` — fetches holdings + live prices (parallel, with 4-tier fallback)
- `get_dashboard_data()` — aggregates wallet, portfolio, metrics, trends, transactions
- `calculate_user_metrics()` — computes progress score (0–100), level (Beginner/Intermediate/Advanced), login streak
- `update_user_portfolio_history()` — backfills weekly price history into `stockhistory`
- `backfill_sectors()` — fills missing sector tags on portfolio entries via yfinance

**LTP (Last Traded Price) fallback order:**
1. Live yfinance (5-min cached)
2. Per-user `Stockhistory` table
3. Global `Stockdata` table
4. Average buy price

#### `invest/watchlist.py`
- Add/remove stocks from watchlist
- "Buy from watchlist" shortcut

#### `invest/Agent.py` + `invest/System_prompt.py`
ARIA — the AI chat assistant:
- Fetches user context (holdings, wallet, P/L, level)
- Fetches live stock context from yfinance (if user is on a stock page)
- Builds a structured system prompt
- Calls **AWS Bedrock (Nova Micro)** via the Converse API
- Returns the reply to the `/agent/chat` endpoint
- Tone adapts to user level (Beginner → simple language, Advanced → full financial terminology)

#### `invest/sentiment_service.py` + `invest/ragbased.py`
News sentiment pipeline:
- Fetches news from Google News RSS
- Classifies each article as **bullish / neutral / bearish**
- Aggregates weekly sentiment scores per stock
- Used by the Headlines / News Feed tab

#### `invest/options_service.py`
Fetches NSE options chain data (calls/puts, strike prices, OI, IV) for the Options Desk tab.

#### `invest/dashboard.py`
Blueprint wrapping `get_dashboard_data()` from `portfolio.py`.

#### `invest/insert.py` (~5,400 lines — standalone script)
DynamoDB snapshot ingestion script. **Runs independently** — not called by the Flask app. Replicates all route logic and writes JSON snapshots to AWS DynamoDB for validation/caching. Has its own config, stock list loader, and all calculation functions duplicated from `routes.py`.

#### `invest/validate_dynamo.py`
Compares live API responses against DynamoDB snapshots to detect data drift. Used for regression testing with `DeepDiff`.

---

## Complete API Endpoints

### Auth (`/auth/*`)
| Method | Endpoint | Auth Required | Description |
|---|---|---|---|
| POST | `/auth/signup` | No | Register with name, email, password |
| POST | `/auth/login` | No | Login with email/password |
| POST | `/auth/dev-login` | No | Dev-only, no password check |
| POST | `/auth/send-otp` | No | Send OTP to email (logged in dev) |
| POST | `/auth/verify-otp` | No | Verify OTP code |
| POST | `/auth/reset-password` | No | Reset password after OTP verification |
| POST | `/auth/google-login` | No | Login via Firebase ID token |

### Wallet & User
| Method | Endpoint | Auth Required | Description |
|---|---|---|---|
| GET | `/get_wallet/<userid>` | Yes | Get user's wallet balance |

### Portfolio & Trading
| Method | Endpoint | Auth Required | Description |
|---|---|---|---|
| GET | `/portfolio/<userid>` | Yes | Get holdings with live LTP + logos |
| POST | `/buy` | Yes | Buy shares (deducts wallet) |
| POST | `/sell` | Yes | Sell shares (credits wallet) |
| GET | `/transactions/<userid>` | No | Transaction history |

### Watchlist
| Method | Endpoint | Auth Required | Description |
|---|---|---|---|
| POST | `/add_to_watchlist` | Yes | Add stock to watchlist |
| GET | `/get_watchlist/<userid>` | Yes | Get watchlist with logos |
| DELETE | `/remove_from_watchlist/<userid>/<stock_id>` | Yes | Remove from watchlist |
| POST | `/buy_from_watchlist` | Yes | Buy directly from watchlist |

### Dashboard
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/dashboard/<userid>` | Yes | Full dashboard data (portfolio, metrics, trends, transactions) |
| GET | `/dashboard/<userid>/export` | No | Export dashboard as CSV |

### Stock Data
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/autocomplete?q=` | No | Symbol/name autocomplete |
| GET | `/get-price/<symbol>` | No | Live price + change |
| GET | `/get_stock_id/<symbol>` | No | Stock DB ID lookup |
| GET | `/stock-meta/<symbol>` | No | Logo, sector, industry, summary |
| GET | `/stock-page/<symbol>` | No | Full stock overview (key stats, calendar, financials, debt, etc.) |
| GET | `/stock-chart/<symbol>?period=&interval=` | No | OHLCV + DMA50/DMA200 + market cap |
| GET | `/stock-financials/<symbol>` | No | Income statement, balance sheet, cash flow (2 years) |
| GET | `/stock-earnings/<symbol>` | No | EPS quarterly, revenue, estimates |
| GET | `/stock-dividend-summary/<symbol>` | No | Dividend history, yield, payout ratio |
| GET | `/stock-headlines/<symbol>` | No | News feed with sentiment scores |
| GET | `/stock-competitors/<symbol>` | No | Peer comparison (price, PE, cap, etc.) |
| GET | `/stock-options/<symbol>` | No | NSE options chain |
| GET | `/stock-short-interest/<symbol>` | No | Short interest data |
| GET | `/bse-filings/<symbol>` | No | BSE regulatory disclosures |

### AI & ML
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/agent/chat` | Yes | ARIA AI chat (AWS Bedrock) |
| GET | `/predict-stock/<symbol>` | No | LSTM price prediction (via Hugging Face) |
| GET | `/recommendations/<userid>` | No | Stock recommendations (via Hugging Face) |
| GET | `/learnings/news` | No | Market news summary (via Hugging Face) |

### Utility
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/refresh-sectors` | No | Backfill missing sectors in portfolio |
| GET | `/` | No | Health check |

---

## Frontend Pages & Routes

| Route | Component | Description |
|---|---|---|
| `/` | `Home.jsx` | Landing page (Navbar hidden) |
| `/Log` | `Log.jsx` | Login page |
| `/signup` | `Signup.jsx` | Registration page |
| `/forgot-password` | `OTPReset.jsx` | OTP-based password reset |
| `/watchlist` | `Watchlist.jsx` | Watchlist with buy modal |
| `/portfolio` | `Portfolio.jsx` | Holdings, P/L, sector breakdown |
| `/dashboard` | `Dashboard.jsx` | Portfolio value trend, P/L chart, metrics |
| `/learnings` | `Learnings.jsx` | Market news via HF |
| `/stockprediction` | `StockPrediction.jsx` | LSTM price prediction chart |
| `/stock/:symbol` | `StockDetailPage.jsx` | Full stock overview with 9 data cards |
| `/chart/:symbol` | `StockChart.jsx` | TradingView-style candlestick chart |
| `/stock/:symbol/competitors` | `Competitor.jsx` | Peer comparison table |
| `/dividend/:symbol` | `Dividend.jsx` | Dividend history and yield |
| `/earnings/:symbol` | `EarningsPage.jsx` | EPS & revenue charts |
| `/financials/:symbol` | `FinancialsPage.jsx` | P&L, balance sheet, cash flow |
| `/news/:symbol` | `StockDetailPage (tab=news)` | Headlines with sentiment |
| `/options/:symbol` | `StockDetailPage (tab=options)` | NSE options chain |
| `/sec/:symbol` | `SecFilingsPage.jsx` | BSE disclosures |
| `/shortinterest/:symbol` | `StockDetailPage (tab=shortinterest)` | Short interest radar |

### Global UI
- **Navbar** — visible on all pages except Home
- **ARIABubble** — floating AI chat button on every page (calls `/agent/chat`)
- **UserContext** — global auth state (user object persisted via `localStorage`)

---

## External Integrations

| Service | Used For | Config Key |
|---|---|---|
| yfinance (Yahoo Finance) | All live stock data (price, OHLCV, fundamentals, dividends, info) | None (free) |
| NSE Python Library (`nse`, `nselib`) | Options chain, capital market data | None (free) |
| BSE API (`api.bseindia.com`) | Regulatory filings | None (scrape with browser headers) |
| GNews API | News feed | `GNEWS_API_KEY` |
| NewsAPI | Supplementary news | `NEWSAPI_KEY` |
| Google News RSS | Sentiment pipeline news source | None (free) |
| Hugging Face Spaces | ML worker: price prediction, stock recommendations, news summary | `HF_SPACE_URL` (+ hardcoded Bearer token) |
| AWS Bedrock (Nova Micro) | ARIA AI assistant LLM | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `BEDROCK_MODEL_ID` |
| AWS DynamoDB | Data snapshots (`insert.py` only) | Same AWS keys |
| Firebase | Google SSO login | `GOOGLE_APPLICATION_CREDENTIALS` (serviceAccountKey.json) |

---

## Authentication Flow

1. User logs in → backend returns `userid`
2. Frontend stores a token string `local_<userid>` in `localStorage` as `id_token`
3. Every protected API call sends `Authorization: Bearer local_<userid>` header
4. `require_user` decorator in `auth.py` parses `userid` from token, queries `Users` table, and attaches `g.current_user`

> **Note:** This is a simplified dev auth system — not JWT. For production, full JWT signing would be needed.

---

## Gamification / Progress System

- **Progress Score (0–100):**
  - Profit score: 50% weight (capped at 100% gain)
  - Trade count score: 30% weight (up to 20 trades)
  - Diversification score: 20% weight (up to 10 stocks)
- **Levels:** Beginner (0–39) → Intermediate (40–69) → Advanced (70–100)
- **Login streak:** Tracked via `useractivity` table
- **Milestones:** Defined in `milestones` table, unlocked into `usermilestones`
- **ARIA** adapts its tone and depth based on the user's current level

---

## Stock Universe

- **40 stocks** tracked from a master CSV (`invest/stock_list.csv`)
- All are Nifty 50 / large-cap NSE stocks (e.g., RELIANCE, TCS, INFY, HDFC, ICICI, etc.)
- `stocks_df_ready.csv` — preprocessed version used for ML recommendation model input
- All symbols use the `.NS` suffix for yfinance queries (e.g., `TCS.NS`)
- Special cases handled: `M&M`, `BAJAJ-AUTO`, `UNITDSPR`

---

## Key Design Decisions

| Decision | Reason |
|---|---|
| All stock data fetched live (no DB caching) | Keeps data real-time; 24h in-memory cache for expensive P&L calls |
| yfinance as primary data source | Free, comprehensive; covers NSE/BSE with `.NS`/`.BO` suffixes |
| Parallel LTP fetching (ThreadPoolExecutor) | Reduces portfolio load time when user holds many stocks |
| Hugging Face for ML | Keeps heavy compute off the Flask server (can run on CPU Spaces) |
| AWS Bedrock (Nova Micro) for AI chat | Low latency, low cost, APAC region model for Indian context |
| DynamoDB snapshots (insert.py) separate from app | Validation/testing tool; doesn't affect the main request path |
| Dual DB config (local + RDS) in `.env` | Allows easy local dev without destroying the RDS setup |
| Single `routes.py` (5,400+ lines) | All stock logic in one file for easy cross-reference; no abstraction overhead |

---

## Environment Variables (`.env`)

```ini
# Flask
FLASK_ENV=development
SECRET_KEY=...

# Local MySQL (active)
DB_HOST=localhost
DB_PORT=3306
DB_NAME=investment
DB_USER=root
DB_PASSWORD=
DATABASE_URL=mysql+pymysql://root:@localhost:3306/investment
DB_USE_SSL=false

# AWS RDS (commented out — preserved)
# DB_HOST=investment-db.c3k8wc4ci776.ap-south-1.rds.amazonaws.com
# ...

# APIs
GNEWS_API_KEY=...
NEWSAPI_KEY=...
HF_SPACE_URL=https://hinal123dodia-stock-ai-worker.hf.space

# AWS
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=ap-south-1
BEDROCK_MODEL_ID=apac.amazon.nova-micro-v1:0
```

---

## How To Run Locally

### Backend
```bash
cd BACKEND
venv\Scripts\activate        # Windows
pip install -r requirements-backend.txt
# Set DB_PASSWORD in .env if your MySQL root has a password
python run.py                # Flask dev server on :5000
```

### Frontend
```bash
cd FRONTEND
npm install
npm start                    # Vite dev server on :5173
```

**Frontend talks to backend at** `http://localhost:5000` (configured in `src/config.js`).

---

## Files to Know First

| File | Why |
|---|---|
| `BACKEND/invest/__init__.py` | App factory — DB config, blueprint registration |
| `BACKEND/invest/routes.py` | All stock API endpoints (the biggest file) |
| `BACKEND/invest/portfolio.py` | Buy/sell logic, LTP fetch, dashboard data |
| `BACKEND/invest/models.py` | All SQLAlchemy DB models |
| `BACKEND/invest/auth.py` | Authentication — login, signup, OTP, Google |
| `BACKEND/invest/Agent.py` | ARIA AI assistant pipeline |
| `BACKEND/.env` | All secrets and config |
| `FRONTEND/src/AppWrapper.jsx` | All React routes |
| `FRONTEND/src/StockDetailPage.jsx` | Stock detail page (most complex component) |
| `FRONTEND/src/api.js` | All frontend API call functions |
| `FRONTEND/src/UserContext.jsx` | Global auth state |

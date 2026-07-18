# SM — Stock Market Investment Platform
**Last Updated:** 2026-07-17

---

## Project Overview

SM is a full-stack, gamified **Indian stock market simulation and research platform**. Users can virtually buy/sell NSE/BSE-listed equities, track their portfolio, conduct deep fundamental and technical research, and receive AI-powered advice via the **ARIA** conversational agent — all without risking real money.

---

## Repository Structure

```
SM/
├── BACKEND/                # Flask Python API
│   ├── invest/             # Core application package
│   │   ├── __init__.py     # App factory (Flask, SQLAlchemy, CORS, blueprints)
│   │   ├── routes.py       # All stock-data & trading endpoints (~5 400 lines)
│   │   ├── insert.py       # Standalone DynamoDB ingestion script (~5 900 lines)
│   │   ├── validate_dynamo.py  # DB snapshot ↔ live API comparison tool
│   │   ├── models.py       # SQLAlchemy ORM models
│   │   ├── auth.py         # Email/password + Google OAuth + OTP auth
│   │   ├── Agent.py        # ARIA AI agent (AWS Bedrock Nova Micro)
│   │   ├── System_prompt.py# ARIA system prompt builder
│   │   ├── portfolio.py    # Portfolio P&L, FIFO lot tracking, sector backfill
│   │   ├── watchlist.py    # Watchlist CRUD
│   │   ├── dashboard.py    # Dashboard data aggregation
│   │   ├── options_service.py  # Proxy client for the Node.js options microservice
│   │   ├── create_tables.py    # One-time DB schema creator
│   │   ├── run_and_validate.py # Orchestrator: insert → validate
│   │   ├── stock_list.csv  # ~40 NSE-listed blue-chip stock universe
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── run.py              # Flask entry point
│   ├── local_setup.sql     # Local MySQL schema
│   ├── rds_export.sql      # AWS RDS schema export
│   └── DATABASE_MIGRATION_GUIDE.md
│
├── FRONTEND/               # React 18 + Vite SPA
│   ├── src/
│   │   ├── App.jsx / AppWrapper.jsx    # Router & layout shell
│   │   ├── StockDetailPage.jsx         # Stock detail hub (tabs)
│   │   ├── StockChart.jsx              # OHLC + DMA candlestick chart
│   │   ├── StockTabs.jsx               # Tab controller (Overview/News/Insiders/Options/…)
│   │   ├── Dashboard.jsx               # User P&L dashboard
│   │   ├── Portfolio.jsx               # Holdings view
│   │   ├── Watchlist.jsx               # Watchlist management
│   │   ├── Competitor.jsx              # Peer comparison
│   │   ├── Dividend.jsx                # Dividend history & calendar
│   │   ├── EarningsPage.jsx            # Quarterly earnings
│   │   ├── FinancialsPage.jsx          # P&L / Balance Sheet / Cash Flow
│   │   ├── ShortInterest.jsx           # NSE short interest data
│   │   ├── SecFilingsPage.jsx          # BSE regulatory filings
│   │   ├── OptionsChain.jsx            # Options chain viewer
│   │   ├── StockPrediction.jsx         # HuggingFace LSTM price prediction
│   │   ├── Learnings.jsx               # AI-curated market news & education
│   │   ├── Headlines/                  # News sub-components (card, sentiment, skeleton)
│   │   │   ├── HeadlinesView.jsx
│   │   │   ├── NewsCard.jsx
│   │   │   ├── SentimentOverview.jsx
│   │   │   └── TopicChips.jsx
│   │   ├── components/
│   │   │   └── ARIABubble.jsx          # Floating ARIA chat widget
│   │   ├── auth.py ↔ Log.jsx/Signup.jsx/OTPReset.jsx  # Auth UI
│   │   ├── api.js                      # Centralised Axios client
│   │   ├── firebase.jsx                # Firebase SDK init (Google OAuth)
│   │   └── UserContext.jsx             # Auth context provider
│   ├── package.json
│   └── vite.config.js
│
├── Option/                 # Node.js Options Microservice
│   ├── Server.js           # Express app serving /options/:symbol
│   ├── Dockerfile
│   └── package.json
│
└── DOCS/
    └── AI-AGENT-PHASES.png # ARIA agent architecture diagram
```

---

## Technology Stack

### Backend (Flask / Python)

| Layer | Technology |
|-------|-----------|
| Framework | Flask 2.3 + Gunicorn |
| ORM | Flask-SQLAlchemy 3.1 |
| Database | MySQL (local dev) / AWS RDS (production) |
| Cache | Flask-Caching (SimpleCache, in-memory) |
| Auth | Custom email/password + Google Firebase Admin + OTP |
| Market Data | `yfinance`, `nse`, `nselib`, `feedparser`, BSE REST API |
| ML / AI | AWS Bedrock (Nova Micro) for ARIA; HuggingFace Space for LSTM price prediction |
| Data Store | AWS DynamoDB (11 tables for pre-computed stock snapshots) |
| File Storage | AWS S3 (`sm-bse-filings` bucket) |
| Options Data | Proxied from the Node.js microservice via `OptionsService` |
| Validation | `deepdiff`, `colorama`, custom fuzzy-equal engine |

### Frontend (React / Vite)

| Layer | Technology |
|-------|-----------|
| Framework | React 18.3 + Vite 8 |
| Routing | React Router v6 |
| Styling | TailwindCSS 3.4 + vanilla CSS modules |
| Charts | Lightweight Charts v4, Chart.js 4, Recharts 3, Plotly.js 3 |
| State | React Context + `useState`/`localStorage` (no Redux in active use) |
| Auth | Firebase 12 (Google sign-in); custom JWT-like `local_`/`dev_` tokens |
| Animations | Framer Motion 12 |
| HTTP | Axios 1.x (centralised in `api.js`) |
| Tables | TanStack Table v8 |

### Options Microservice (Node.js)

| Layer | Technology |
|-------|-----------|
| Framework | Express.js |
| NSE Data | `stock-nse-india` npm package |
| Deployment | Lambda-compatible via `serverless-http`; also runs locally on port 5001 |
| Caching | In-memory 60-second TTL (ensures insert + validate see identical snapshots) |

---

## Database Schema (MySQL)

| Table | Description |
|-------|-------------|
| `users` | Accounts: name, email, password_hash, OTP, wallet balance (₹10 000 default), progress score, level |
| `stock` | Stock master: symbol, name |
| `watchlist` | User ↔ stock many-to-many |
| `portfolio` | Aggregated holdings: qty, average buy price, total invested, sector |
| `transactionhistory` | All buy/sell events |
| `fifolot` | FIFO lot tracking for accurate cost-basis P&L |
| `stockhistory` | Historical close prices per user |
| `useractivity` | Gamification event log |
| `stockdata` | Raw OHLCV snapshots |
| `milestones` | Gamification milestone definitions |
| `usermilestones` | User ↔ milestone achievement records |

---

## DynamoDB Tables (Pre-Computed Snapshots)

| Table | Key Pattern | Content |
|-------|-------------|---------|
| `stock-page` | `SYMBOL#<sym>` / `SNAPSHOT#<date>` | Full stock overview & fundamentals |
| `stock-chart` | `SYMBOL#<sym>` / `CHART#<period>#<interval>` | OHLC + DMA50/200 time series |
| `stock-financials` | `SYMBOL#<sym>` / `FINANCIALS#annual\|quarterly` | Income statement, balance sheet, cash flow |
| `stock-earnings` | `SYMBOL#<sym>` | Quarterly EPS actuals vs. estimates |
| `stock-dividend-summary` | `SYMBOL#<sym>` / `DIVIDEND_SUMMARY#<date>` | Dividend calendar & yield data |
| `stock-headlines` | `SYMBOL#<sym>` | News articles with sentiment scores |
| `stock-competitors` | `SYMBOL#<sym>` | Peer comparison data |
| `stock-options` | `SYMBOL#<sym>` | NSE options chain snapshot |
| `stock-short-interest` | `SYMBOL#<sym>` | NSE short-selling & FII/DII data |
| `stock-meta` | `SYMBOL#<sym>` | Company logo, sector, description |
| `bse-filings` | `SYMBOL#<sym>` | BSE regulatory disclosure filings |

---

## Key Backend Files

### `routes.py` (~5 400 lines)
The primary Flask API. Key endpoint groups:

- **Auth:** `/auth/signup`, `/auth/login`, `/auth/google-login`, `/auth/send-otp`, `/auth/verify-otp`, `/auth/reset-password`
- **Trading:** `/buy`, `/sell`, `/portfolio/<userid>`, `/get_wallet/<userid>`
- **Watchlist:** `/add_to_watchlist`, `/get_watchlist/<userid>`, `/remove_from_watchlist`, `/buy_from_watchlist`
- **Stock Research:** `/stock-page/<symbol>`, `/stock-chart/<symbol>`, `/financials/<symbol>`, `/earnings/<symbol>`, `/dividend-summary/<symbol>`, `/competitors/<symbol>`, `/headlines/<symbol>`, `/short-interest/<symbol>`, `/bse-filings/<symbol>`, `/sec-filings/<symbol>`
- **Options:** `/options/<symbol>` (proxied from Node.js microservice)
- **Prediction:** `/predict-stock/<symbol>` (HuggingFace LSTM)
- **AI Agent:** `/agent/chat` (AWS Bedrock Nova Micro via `Agent.py`)
- **Recommendations:** `/recommendations/<userid>` (HuggingFace collaborative-filter model)
- **Dashboard:** `/dashboard/<userid>`, `/dashboard/<userid>/export` (CSV)
- **Utilities:** `/autocomplete`, `/stock-meta/<symbol>`, `/get-price/<symbol>`, `/refresh-sectors`

### `insert.py` (~5 900 lines)
Standalone DynamoDB ingestion script — **fully decoupled from Flask**. Replicates all fetch + calculation logic from `routes.py` and persists results to DynamoDB. Supports:
- `--symbols`, `--endpoints`, `--period`, `--interval`, `--dry-run`, `--skip-existing` CLI flags
- 11 endpoint handlers, one per DynamoDB table
- BSE filings ingestion with S3 PDF attachment storage
- 5-minute lightweight price-only snapshots (`stock_page_live_snapshot`)
- Concurrent batch processing via `ThreadPoolExecutor`

### `validate_dynamo.py` (~1 048 lines)
Validation tool that fetches stored DynamoDB snapshots and compares them against live Flask endpoint responses. Features:
- **Tolerant comparison engine** with 5% relative numeric tolerance
- Timestamp bucketing (600-second windows)
- Wildcard suppression for volatile fields (`volume`, `avg_volume`, `turnover`)
- BSE filing identity keyed on attachment GUID (not list position) to handle newly published filings
- Count-tolerant fields for news article counts (`±3` articles)
- Colourised CLI output with `✅ / ❌ / 🟡` status icons

---

## Frontend Routes

| URL | Component | Description |
|-----|-----------|-------------|
| `/` | `Home` | Landing page |
| `/Log` | `Log` | Login page |
| `/signup` | `Signup` | Registration |
| `/forgot-password` | `OTPReset` | OTP-based password reset |
| `/dashboard` | `Dashboard` | P&L overview, gamification metrics |
| `/portfolio` | `Portfolio` | Holdings & transactions |
| `/watchlist` | `Watchlist` | Watchlist management |
| `/stock/:symbol` | `StockDetailPage` | Stock hub (overview, news, insiders, options, short interest) |
| `/chart/:symbol` | `StockChart` | Interactive OHLC candlestick chart |
| `/stock/:symbol/competitors` | `Competitor` | Peer comparison |
| `/dividend/:symbol` | `Dividend` | Dividend calendar & history |
| `/earnings/:symbol` | `EarningsPage` | Quarterly earnings |
| `/financials/:symbol` | `FinancialsPage` | P&L / Balance Sheet / Cash Flow |
| `/sec/:symbol` | `SecFilingsPage` | BSE regulatory filings |
| `/shortinterest/:symbol` | `StockDetailPage` (tab) | NSE short interest |
| `/options/:symbol` | `StockDetailPage` (tab) | Options chain |
| `/stockprediction` | `StockPrediction` | LSTM price prediction UI |
| `/learnings` | `Learnings` | AI-curated market education |

**ARIA** (`ARIABubble.jsx`) is a persistent floating chat widget rendered globally on all authenticated routes.

---

## AI & ML Components

### ARIA Agent (`Agent.py` + `System_prompt.py`)
- **Model:** AWS Bedrock `amazon.nova-micro-v1:0` (ap-south-1)
- **Pipeline:** Fetch user portfolio + wallet context → fetch live stock context via yfinance → build personalised system prompt → call Bedrock Converse API → return reply
- **Context:** User's name, wallet, P&L %, progress level, all holdings with current prices; plus live stock data (price, P/E, sector, 52-week range, etc.) for whichever stock is currently on screen
- **Config:** `maxTokens=600`, `temperature=0.3`

### Stock Price Prediction
- **Model:** LSTM trained on-demand via HuggingFace Space (`hinal123dodia-stock-ai-worker`)
- **Features:** 100-day close prices, MA100, MA200, historical prediction overlay, next-day forecast
- **Endpoint:** `/predict-stock/<symbol>` (120-second timeout)

### Stock Recommendations
- **Model:** Collaborative-filter model on HuggingFace Space
- **Endpoint:** `/recommendations/<userid>`
- **Logic:** Excludes stocks already in user's portfolio; falls back to top-6 from CSV if model returns nothing

---

## Authentication Flow

1. **Email/Password:** Hash via Werkzeug `bcrypt`; stored in MySQL `users.password_hash`
2. **Google OAuth:** Firebase client-side sign-in → `idToken` sent to `/auth/google-login` → verified by Firebase Admin SDK → upserts user in MySQL
3. **OTP Password Reset:** 6-digit OTP stored in `users.otp_code` (10-minute TTL); delivered via server logs in dev
4. **Route Protection:** `require_user` decorator in `auth.py` validates `Bearer local_<userid>` / `Bearer dev_<userid>` tokens for local development

---

## Data Ingestion Pipeline

```
insert.py (run daily / on-demand)
    │
    ├─ Fetches data from: yfinance, BSE API, NSE API (via nselib),
    │   HuggingFace Space, feedparser RSS, BeautifulSoup scraping
    │
    ├─ Transforms data (same logic as routes.py for parity)
    │
    └─ Writes to DynamoDB (11 tables)
            │
            └─ validate_dynamo.py
                    │
                    ├─ Reads DynamoDB snapshot
                    ├─ Calls live Flask endpoints
                    └─ Compares with fuzzy-equal tolerance engine
```

**Stock Universe:** ~40 NSE blue-chip stocks defined in `stock_list.csv` (RELIANCE, TCS, INFY, HDFCBANK, etc.)

---

## Infrastructure

| Component | Service |
|-----------|---------|
| Backend API | AWS EC2 (Flask + Gunicorn) |
| Database | MySQL — local dev / AWS RDS (commented-out config in `__init__.py`) |
| Stock snapshots | AWS DynamoDB (ap-south-1) |
| BSE filing PDFs | AWS S3 (`sm-bse-filings`) |
| AI inference | AWS Bedrock (Nova Micro) |
| ML models | HuggingFace Spaces (`hinal123dodia-stock-ai-worker`) |
| Options data | Node.js microservice on port 5001 (also Lambda-deployable) |
| Frontend | Vite dev server (local) / `dist/` build for production |
| Frontend Auth | Firebase (Google OAuth) |

---

## Current Development State

### Active / Completed
- ✅ Full trading simulation (buy, sell, FIFO P&L, wallet)
- ✅ Real-time stock data via yfinance & NSE/BSE APIs
- ✅ OHLC candlestick charts with DMA50/200 overlays
- ✅ Comprehensive stock research pages (financials, earnings, dividends, competitors, options, short interest, SEC/BSE filings)
- ✅ ARIA AI chat agent (AWS Bedrock, context-aware)
- ✅ LSTM price prediction via HuggingFace
- ✅ DynamoDB ingestion pipeline (`insert.py`) fully decoupled from Flask
- ✅ DynamoDB validation suite (`validate_dynamo.py`) with tolerant fuzzy-equal engine
- ✅ Gamification: progress score, level, milestones, login streak
- ✅ Google OAuth via Firebase
- ✅ OTP-based password reset
- ✅ NSE Options chain via dedicated Node.js microservice

### Known Configuration Notes
- **Database:** Currently configured for **local MySQL** (`localhost:3306/investment`). AWS RDS config is preserved but commented out in `__init__.py` — switch by uncommenting the RDS block.
- **Auth tokens:** Production should use real JWT; dev uses `local_<userid>` / `dev_<userid>` bearer tokens.
- **HuggingFace Space:** May need a wake-up call if the space is sleeping (cold start up to ~60s).
- **`insert.py`** imports `options_service` as a local (non-package) module — must be run from the `invest/` directory.

---

## Local Development Setup

### Backend
```bash
cd BACKEND
python -m venv venv && venv\Scripts\activate
pip install -r invest/requirements.txt
# Ensure .env is populated (DB_HOST, DB_USER, DB_PASSWORD, AWS_*, HF_SPACE_URL, GNEWS_API_KEY, NEWSAPI_KEY)
python run.py          # Flask on http://localhost:5000
```

### Frontend
```bash
cd FRONTEND
npm install
npm start              # Vite dev server on http://localhost:5173
```

### Options Microservice
```bash
cd Option
npm install
node Server.js         # Express on http://localhost:5001
```

### Data Ingestion
```bash
cd BACKEND/invest
python insert.py --symbols INFY TCS --endpoints stock-page stock-chart
python validate_dynamo.py --symbol INFY --diff
```

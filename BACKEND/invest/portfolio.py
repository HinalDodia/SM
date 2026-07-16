import yfinance as yf
import requests
import certifi
import pandas as pd
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy.orm.exc import NoResultFound
import concurrent.futures
import time
from .models import (
    Users, Portfolio, Transactionhistory, FIFOLot,
    Useractivity, Stockhistory, Stockdata, Milestones, UserMilestones, db
)

# ---------------- LTP Cache ----------------
LTP_CACHE = {}
CACHE_TTL = 300  # seconds

# Ensure requests uses a valid certificate bundle (helps yfinance on some systems)
try:
    _old_get = requests.get
    def _safe_get(*args, **kwargs):
        kwargs.setdefault("verify", certifi.where())
        return _old_get(*args, **kwargs)
    requests.get = _safe_get  # type: ignore
except Exception:
    pass

def _get_live_price_for_symbol(symbol_plain):
    """Fetch live price with in-memory caching and correct symbol handling."""
    symbol_plain = symbol_plain.upper()
    now = time.time()

    cached = LTP_CACHE.get(symbol_plain)
    if cached and (now - cached["timestamp"] < CACHE_TTL):
        return cached["price"], cached["change"], cached["change_percent"]

    try:
        ticker_symbol = symbol_plain
        if not (ticker_symbol.endswith(".NS") or ticker_symbol.endswith(".BO")):
            ticker_symbol += ".NS"
            
        t = yf.Ticker(ticker_symbol)
        info = t.info or {}

        price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
        prev = info.get("previousClose")

        # Fallback to recent historical close if live fields are missing
        if price is None:
            try:
                hist = t.history(period="5d", interval="1d", auto_adjust=False)
                if hist is not None and not hist.empty:
                    # Use the latest available Close as current price
                    price = float(hist["Close"].dropna().iloc[-1])
                    # Previous close if available
                    if len(hist["Close"].dropna()) >= 2:
                        prev = float(hist["Close"].dropna().iloc[-2])
                    else:
                        prev = price
                else:
                    # as a final fallback, try 1mo window
                    hist = t.history(period="1mo", interval="1d", auto_adjust=False)
                    if hist is not None and not hist.empty:
                        price = float(hist["Close"].dropna().iloc[-1])
                        if len(hist["Close"].dropna()) >= 2:
                            prev = float(hist["Close"].dropna().iloc[-2])
                        else:
                            prev = price
            except Exception:
                pass

        if price is None:
            return None, None, None

        change = round(float(price) - float(prev), 2) if prev else 0
        change_percent = round((change / float(prev)) * 100, 2) if prev and prev != 0 else 0

        LTP_CACHE[symbol_plain] = {
            "price": round(float(price), 2),
            "change": change,
            "change_percent": change_percent,
            "timestamp": now,
        }
        return round(float(price), 2), change, change_percent
    except Exception:
        return None, None, None

def fetch_ltp_parallel(symbols):
    """Fetch multiple LTPs concurrently"""
    results = []
    def fetch(symbol):
        price, change, change_percent = _get_live_price_for_symbol(symbol)
        return {"stockname": symbol, "price": price, "change": change, "change_percent": change_percent}
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_sym = {executor.submit(fetch, sym): sym for sym in symbols}
        for future in concurrent.futures.as_completed(future_to_sym):
            results.append(future.result())
    return pd.DataFrame(results)

# ---------------- Utils ----------------
def get_sector_from_api(symbol):
    """Fetch sector using proper NSE ticker."""
    try:
        ticker_symbol = symbol.upper().strip()

        if not (
            ticker_symbol.endswith(".NS")
            or ticker_symbol.endswith(".BO")
        ):
            ticker_symbol += ".NS"

        info = yf.Ticker(ticker_symbol).info or {}

        sector = info.get("sector")

        if sector:
            return sector

        return "Unknown"

    except Exception:
        return "Unknown"


# ---------------- History Updater (for charts) ----------------
def _normalize_symbol(symbol: str) -> str:
    symbol = (symbol or "").strip().upper()
    return symbol.upper()


def upsert_stockhistory(userid: int, stockname: str, date_val, close_val: float):
    try:
        existing = Stockhistory.query.filter_by(
            userid=int(userid), stock_name=stockname, dates=pd.to_datetime(date_val).date()
        ).first()
        if existing:
            existing.close_price = float(close_val)
        else:
            db.session.add(Stockhistory(
                userid=int(userid), stock_name=stockname,
                dates=pd.to_datetime(date_val).date(), close_price=float(close_val)
            ))
    except Exception:
        db.session.rollback()
        raise


def update_user_portfolio_history(userid: int, months: int = 6) -> int:
    """Fetch recent price history for all user's portfolio symbols and upsert into Stockhistory.
    Returns number of rows upserted. Uses weekly data for last `months` months.
    """
    rows = Portfolio.query.filter_by(userid=userid).all()
    if not rows:
        return 0

    symbols = sorted({r.stockname for r in rows if r.stockname})
    # Delete old history for stocks no longer in portfolio
    Stockhistory.query.filter(
        Stockhistory.userid == int(userid),
        ~Stockhistory.stock_name.in_(symbols)
    ).delete(synchronize_session=False)

    db.session.commit()
    
    if not symbols:
        return 0

    since_date = (datetime.now().date() - timedelta(days=months * 30))
    upserts = 0

    for sym in symbols:
        try:
            yf_symbol = _normalize_symbol(sym)
            t = yf.Ticker(yf_symbol)
            hist = t.history(period=f"{months}mo", interval="1wk", auto_adjust=False)
            if hist is None or hist.empty:
                continue

            # Ensure we have a datetime index and a Close column
            if not isinstance(hist.index, pd.DatetimeIndex):
                hist = hist.reset_index()
                if "Date" in hist.columns:
                    hist.set_index("Date", inplace=True)
                hist.index = pd.to_datetime(hist.index)

            close_series = None
            if "Close" in hist.columns:
                close_series = hist["Close"]
            else:
                # handle MultiIndex or unexpected columns
                if isinstance(hist.columns, pd.MultiIndex):
                    hist.columns = ["__".join(map(str, c)) for c in hist.columns]
                cc = next((c for c in hist.columns if "Close" in str(c)), None)
                if cc:
                    close_series = hist[cc]

            if close_series is None:
                continue

            for ts, close in close_series.items():
                if pd.isna(close):
                    continue
                d = pd.to_datetime(ts).date()
                if d < since_date:
                    continue
                upsert_stockhistory(userid, sym, d, float(close))
                upserts += 1

            # optional cleanup of older rows
            try:
                Stockhistory.query.filter(
                    Stockhistory.userid == int(userid),
                    Stockhistory.stock_name == sym,
                    Stockhistory.dates < since_date,
                ).delete(synchronize_session=False)
            except Exception:
                pass

            db.session.commit()
        except Exception:
            db.session.rollback()
            # skip symbol on error, continue others
            continue

    return upserts

def gettingfromdb(userid):
    """Fetch holdings, enrich with live data & P&L, AND include the sector.

    Robust LTP fallback order:
    1) Live price via yfinance (cached)
    2) Most recent close from per-user Stockhistory
    3) Most recent close from global Stockdata
    4) User's average buy price
    """
    rows = Portfolio.query.filter_by(userid=userid).all()
    if not rows:
        return []

    symbols = [r.stockname for r in rows]

    # Step 1: try to fetch live prices in parallel
    ltp_results = {}

    def fetch_ltp(stockname):
        price, _, _ = _get_live_price_for_symbol(stockname)
        return stockname, price

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_stock = {executor.submit(fetch_ltp, s): s for s in symbols}
        for future in concurrent.futures.as_completed(future_to_stock):
            stock, price = future.result()
            ltp_results[stock] = price

    # Helper: latest close from per-user Stockhistory
    def latest_close_from_user_history(sym: str):
        try:
            rec = (
                Stockhistory.query
                .filter(Stockhistory.userid == int(userid), Stockhistory.stock_name == sym)
                .order_by(Stockhistory.dates.desc())
                .first()
            )
            return float(rec.close_price) if rec else None
        except Exception:
            return None

    # Helper: latest close from global Stockdata
    def latest_close_from_global(sym: str):
        try:
            rec = (
                Stockdata.query
                .filter(Stockdata.symbol==sym)
                .order_by(Stockdata.date.desc())
                .first()
            )
            return float(rec.close) if rec and rec.close is not None else None
        except Exception:
            return None

    processed = []
    for r in rows:
        sym = r.stockname
        # Step 1: live price
        ltp = ltp_results.get(sym)
        # Step 2: user history
        if ltp is None:
            ltp = latest_close_from_user_history(sym)
        # Step 3: global data
        if ltp is None:
            ltp = latest_close_from_global(sym)
        # Step 4: fallback to avg buy
        if ltp is None:
            ltp = float(r.averagebuyprice or 0)

        # Coerce numeric types safely
        try:
            ltp = float(ltp)
        except Exception:
            ltp = float(r.averagebuyprice or 0)

        total_quantity = int(r.totalquantity or 0)
        total_invested = float(r.totalinvested or 0)
        now_value = float(ltp) * total_quantity
        pnl = now_value - total_invested
        pct = (pnl / total_invested * 100) if total_invested > 0 else 0

        processed.append({
            "portfolioid": r.portfolioid,
            "stockname": sym,
            "companyname": r.companyname,
            "sector": r.sector or "Other",
            "totalquantity": total_quantity,
            "averagebuyprice": float(r.averagebuyprice or 0),
            "totalinvested": total_invested,
            "ltp": float(ltp),
            "profitorloss": float(pnl),
            "percentage": float(pct),
            "nowvalue": float(now_value),
        })
    return processed

def get_stock_entry(userid, stockname):
    return Portfolio.query.filter_by(userid=userid, stockname=stockname).first()

def userfromdb(userid):
    try:
        return Users.query.filter_by(userid=userid).one()
    except NoResultFound:
        return None

# ---------------- Sector Backfill ----------------
def backfill_sectors(userid: int | None = None) -> dict:
    """Fill missing/unknown sectors for existing portfolio holdings using yfinance.

    Returns a summary dict: {updated: <count>, total_checked: <count>}.
    """
    try:
        q = Portfolio.query
        if userid is not None:
            q = q.filter(Portfolio.userid == int(userid))
        rows = q.filter(
            (Portfolio.sector == None) |  # noqa: E711
            (Portfolio.sector == "") |
            (Portfolio.sector == "Other") |
            (Portfolio.sector == "Unknown") |
            (Portfolio.sector == "UNKNOWN")
        ).all()

        total = len(rows)
        updated = 0
        for r in rows:
            sec = get_sector_from_api(r.stockname)
            if sec and sec != "Other":
                r.sector = sec
                db.session.add(r)
                updated += 1
        if updated:
            db.session.commit()
        return {"updated": updated, "total_checked": total}
    except Exception as e:
        db.session.rollback()
        return {"updated": 0, "total_checked": 0, "error": str(e)}

# ---------------- Buy / Sell Logic (WITH FIXES) ----------------

def buy(userid, stockname, qty, price, companyname):
    user = userfromdb(userid)
    if not user: raise ValueError("User not found")

    total_cost = Decimal(qty) * Decimal(price)
    if Decimal(user.money) < total_cost: raise ValueError("Insufficient funds")

    fromdb = get_stock_entry(userid, stockname)
    if fromdb:
        fromdb.totalquantity += qty
        fromdb.totalinvested = Decimal(fromdb.totalinvested or 0) + total_cost
        fromdb.averagebuyprice = fromdb.totalinvested / fromdb.totalquantity
        portfolioid = fromdb.portfolioid
        if fromdb.sector in [None, "", "Other", "Unknown"]:
            refreshed_sector = get_sector_from_api(stockname)
            if refreshed_sector not in ["Unknown", "Other"]:
                fromdb.sector = refreshed_sector    
    else:
        stock_sector = get_sector_from_api(stockname)

        # Retry once if sector fetch failed
        if stock_sector in ["Unknown", "Other", None, ""]:
            time.sleep(1)
            stock_sector = get_sector_from_api(stockname)

        new_entry = Portfolio(
            userid=userid,
            stockname=stockname,
            companyname=companyname,
            totalquantity=qty,
            totalinvested=total_cost,
            averagebuyprice=Decimal(price),
            sector=stock_sector or "Unknown"
        )
        db.session.add(new_entry)
        db.session.flush()
        portfolioid = new_entry.portfolioid

    user.money = Decimal(user.money) - total_cost
    db.session.add(user)
    
    # Assuming fifo_buy is defined and works as intended
    # fifo_buy(userid, portfolioid, companyname, qty, Decimal(price), datetime.now())
    db.session.add(Transactionhistory(
        portfolioid=portfolioid, userid=userid, stockname=stockname,
        companyname=companyname, quantity=qty, price=price,
        transactiontype="buy", timestamp=datetime.now()
    ))
    db.session.commit()
    return {"status": "ok", "action": "buy", "qty": qty, "stock": stockname}

def sell(userid, stockname, companyname, qty, price):
    fromdb = get_stock_entry(userid, stockname)
    if not fromdb or qty > fromdb.totalquantity:
        raise ValueError("Not enough shares to sell")
    
    # Assuming fifo_sell is defined and returns the cost of sold shares
    # fifo_cost = fifo_sell(userid, fromdb.portfolioid, companyname, qty, Decimal(price))
    # Simplified cost calculation for now
    fifo_cost = Decimal(fromdb.averagebuyprice) * Decimal(qty)

    fromdb.totalquantity -= qty
    fromdb.totalinvested = Decimal(fromdb.totalinvested or 0) - fifo_cost
    
    if fromdb.totalquantity > 0:
        fromdb.averagebuyprice = fromdb.totalinvested / fromdb.totalquantity
    else:
        fromdb.averagebuyprice = Decimal(0)
        fromdb.totalinvested = Decimal(0)

    user = userfromdb(userid)
    user.money = Decimal(user.money) + (Decimal(qty) * Decimal(price))
    db.session.add(user)
    
    db.session.add(Transactionhistory(
        portfolioid=fromdb.portfolioid, userid=userid, stockname=stockname,
        companyname=companyname, quantity=qty, price=price,
        transactiontype="sell", timestamp=datetime.now()
    ))
    db.session.commit()
    return {"status": "ok", "action": "sell", "qty": qty, "stock": stockname}

# ---------------- Dashboard Metrics Calculation ------------------
def calculate_user_metrics(userid):
    user = Users.query.get(userid)
    if not user: return {}

    total_investment = sum(p.totalinvested for p in Portfolio.query.filter_by(userid=userid).all() if p.totalinvested)
    holdings = gettingfromdb(userid)
    current_value = sum(h['nowvalue'] for h in holdings)
    total_pnl = current_value - float(total_investment)
    
    profit_percent = (total_pnl / float(total_investment) * 100) if total_investment > 0 else 0
    profit_score = min(max(profit_percent, 0), 100) * 0.5

    total_trades = Transactionhistory.query.filter_by(userid=userid).count()
    trade_score = min(total_trades / 20, 1) * 30

    # This is the corrected line
    num_stocks = Portfolio.query.filter(Portfolio.userid == userid, Portfolio.totalquantity > 0).count()
    
    diversification_score = min(num_stocks / 10, 1) * 20

    total_score = profit_score + trade_score + diversification_score
    # Map level to an integer code for DB (column is Integer) and return a human-readable label
    if total_score < 40:
        level_code, level_label = 1, "Beginner"
    elif total_score < 70:
        level_code, level_label = 2, "Intermediate"
    else:
        level_code, level_label = 3, "Advanced"
    user.level = level_code

    today = datetime.today().date()
    streak = 0
    logins = Useractivity.query.filter_by(userid=userid, activity_type='login').order_by(Useractivity.activity_date.desc()).all()
    if logins:
        unique_login_dates = sorted(list(set(l.activity_date.date() for l in logins)), reverse=True)
        if unique_login_dates and unique_login_dates[0] == today:
            streak = 1
            for i in range(len(unique_login_dates) - 1):
                if unique_login_dates[i] - timedelta(days=1) == unique_login_dates[i+1]:
                    streak += 1
                else: break
    
    db.session.commit()
    return {"progress_score": round(total_score, 2), "level": level_label, "login_streak": streak}

# ---------------- Main Dashboard Data Aggregator ------------------
def get_dashboard_data(userid):
    user = userfromdb(userid)
    if not user: return {"error": "User not found"}

    wallet = float(user.money) if user.money else 0.0
    portfolio = gettingfromdb(userid)
    # If sectors look uninformative, try a quick backfill and re-fetch once.
    if portfolio and all((not h.get("sector")) or h.get("sector") == "Other" for h in portfolio):
        try:
            bf = backfill_sectors(userid)
            if bf.get("updated", 0) > 0:
                portfolio = gettingfromdb(userid)
        except Exception:
            pass
    metrics = calculate_user_metrics(userid)

    investment_split = [
        {"company": h["companyname"], "stockname": h["stockname"], "sector": h.get("sector") or "Other", "amount": h["nowvalue"]}
        for h in portfolio if h["nowvalue"] > 0
    ]

    portfolio_symbols = {
        str(h["stockname"]).replace(".NS", "").replace(".BO", "").upper()
        for h in portfolio
    }

    history = (
        Stockhistory.query
        .filter_by(userid=userid)
        .order_by(Stockhistory.dates.asc())
        .all()
    )

    history = [
        h for h in history
        if str(h.stock_name).replace(".NS", "").replace(".BO", "").upper()
        in portfolio_symbols
    ]
    print("HISTORY COUNT:", len(history))
    if not history:
        try:
            updated = update_user_portfolio_history(userid, months=6)
            print("Backfill updated:", updated)
            # Re-fetch after backfill
            history = (
                Stockhistory.query
                .filter_by(userid=userid)
                .order_by(Stockhistory.dates.asc())
                .all()
            )
            history = [
                h for h in history
                if str(h.stock_name).replace(".NS", "").replace(".BO", "").upper()
                in portfolio_symbols
            ]
            print("HISTORY COUNT AFTER BACKFILL:", len(history))
        except Exception as e:
            print("Backfill error:", e)
            
    portfolio_value_trend, profit_loss_trend = [], []
    if history:
        df = pd.DataFrame([
            {"date": pd.to_datetime(h.dates), "stock": h.stock_name, "close": float(h.close_price or 0)}
            for h in history
        ])
        if not df.empty:
            # Map each stock to user's current quantity (approximation without full lot history)
            qty_map = {
                str(h["stockname"]).replace(".NS", "").replace(".BO", "").upper():
                int(h["totalquantity"] or 0)
                for h in portfolio
            }
            df["qty"] = df["stock"].map(
                lambda s: qty_map.get(
                    str(s).replace(".NS", "").replace(".BO", "").upper(),
                    0
                )
            )
            df["value"] = df["close"] * df["qty"]
            print(df[["stock", "qty", "close", "value"]].head(20))

            # Compute end-of-month (last available close in month per stock), then sum values across stocks
            df_sorted = df.sort_values("date")
            df_sorted["month"] = df_sorted["date"].dt.to_period("M")
            last_per_stock_month = df_sorted.groupby(["month", "stock"], as_index=False).tail(1)
            monthly = last_per_stock_month.groupby("month", as_index=False)["value"].sum()
            monthly["date_label"] = monthly["month"].dt.strftime("%b")

            portfolio_value_trend = [
                {"date": row["date_label"], "value": float(row["value"])} for _, row in monthly.iterrows()
            ]
            base_val = float(monthly["value"].iloc[0]) if not monthly.empty else 0.0
            profit_loss_trend = []

            for _, row in monthly.iterrows():

                current_value = float(row["value"])

                if base_val > 0:
                    pct_change = ((current_value - base_val) / base_val) * 100
                else:
                    pct_change = 0

                profit_loss_trend.append({
                    "date": row["date_label"],
                    "profit_loss": round(pct_change, 2)
                })
    
    transactions = [{
        "type": t.transactiontype, "stockname": t.stockname, "price": float(t.price),
        "date": t.timestamp.strftime('%Y-%m-%d %H:%M') if t.timestamp else None
    } for t in Transactionhistory.query.filter_by(userid=userid).order_by(Transactionhistory.timestamp.desc()).limit(5)]

    return {
        "wallet": wallet, "portfolio": portfolio, "metrics": metrics,
        "investment_split": investment_split, "portfolio_value_trend": portfolio_value_trend,
        "profit_loss_trend": profit_loss_trend, "transactions": transactions
    }


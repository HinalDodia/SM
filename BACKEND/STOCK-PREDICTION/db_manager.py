import os
import sqlite3
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "stock_cache.db")


def get_connection():
    """Create a thread-safe connection to SQLite database."""
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    """Initialize database tables."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_prices (
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                PRIMARY KEY (ticker, date)
            )
        """)
        conn.commit()


init_db()


def save_stock_data(ticker: str, df: pd.DataFrame):
    """Safely insert or replace stock prices into SQLite."""
    if df.empty:
        return

    ticker = ticker.strip().upper()
    data_to_insert = []

    for _, row in df.iterrows():
        date_str = str(row["Date"])[:10]  # YYYY-MM-DD
        close = float(row["Close"])
        volume = float(row["Volume"]) if "Volume" in row and pd.notnull(row["Volume"]) else 0.0
        data_to_insert.append((ticker, date_str, close, volume))

    with get_connection() as conn:
        conn.executemany("""
            INSERT INTO stock_prices (ticker, date, close, volume)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ticker, date) DO UPDATE SET
                close=excluded.close,
                volume=excluded.volume
        """, data_to_insert)
        conn.commit()


def get_stock_data(ticker: str) -> pd.DataFrame:
    """Retrieve historical stock data for ticker from SQLite."""
    ticker = ticker.strip().upper()
    with get_connection() as conn:
        query = """
            SELECT date as Date, close as Close, volume as Volume
            FROM stock_prices
            WHERE ticker = ?
            ORDER BY Date ASC
        """
        df = pd.read_sql_query(query, conn, params=(ticker,))
    return df

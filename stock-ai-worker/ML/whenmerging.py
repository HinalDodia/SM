# recommend.py
import pandas as pd
import numpy as np
import pickle
from datetime import datetime
import requests


def normalize_stocknames(df, col="stockname"):
    df[col] = df[col].astype(str).str.replace(r"\.NS$", "", regex=True).str.upper().str.strip()
    return df

# ----------------------------
# Config
# ----------------------------
TRANSACTIONS_API = "http://localhost:5000/transactions"
LTP_API = "http://localhost:5000/ltp"               # replace with actual backend URL

# ----------------------------
# Load trained model + training columns
# ----------------------------
with open("invest/recml_xgb.pkl", "rb") as f:
    model = pickle.load(f)

with open("invest/training_columns.pkl", "rb") as f:
    TRAIN_COLS = pickle.load(f)


# ----------------------------
# Utility: add technical indicators
# ----------------------------
def add_technical_indicators(df):
    if "price" not in df.columns:
        raise ValueError("Price column missing in stock data.")
    df = df.sort_values("timestamp")
    df["ma5"] = df.groupby("stockname")["price"].transform(lambda x: x.rolling(5, min_periods=1).mean())
    df["ma10"] = df.groupby("stockname")["price"].transform(lambda x: x.rolling(10, min_periods=1).mean())
    df["ma20"] = df.groupby("stockname")["price"].transform(lambda x: x.rolling(20, min_periods=1).mean())
    df["volatility"] = df.groupby("stockname")["price"].transform(lambda x: x.rolling(10, min_periods=1).std())
    df["avg_return"] = df.groupby("stockname")["price"].transform(lambda x: x.pct_change().rolling(10, min_periods=1).mean())
    df.fillna(0, inplace=True)
    
    return df


# ----------------------------
# Fetch portfolio + stock master + prices
# ----------------------------

def fetch_transactions(userid: int) -> pd.DataFrame:
    resp = requests.get(f"{TRANSACTIONS_API}/{userid}")
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return pd.DataFrame(columns=["userid", "stockname", "quantity", "price", "type", "date"])
    # Force dataframe with explicit column order
    df = pd.DataFrame(data)
    df.columns = df.columns.str.lower()
    df = normalize_stocknames(df, "stockname")

    # numeric conversions
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["type"] = df["type"].str.lower()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    return df




def fetch_stock_universe(limit=200) -> pd.DataFrame:
    stocks_df = pd.read_csv("invest/stocks_df_ready.csv").head(limit)
    stocks_df.rename(
        columns={"SYMBOL": "stockname", "NAME OF COMPANY": "companyname"},
        inplace=True
    )
    stocks_df = normalize_stocknames(stocks_df, "stockname")
    return stocks_df[["stockname", "companyname"]] 


def fetch_ltp(symbols: list[str]) -> pd.DataFrame:
    resp = requests.post(LTP_API, json={"symbols": symbols})
    resp.raise_for_status()
    ltps = resp.json()  # { "SYMBOL": price, ... }
    df = pd.DataFrame(list(ltps.items()), columns=["stockname", "price"])
    df = normalize_stocknames(df, "stockname")

    return df


# ----------------------------
# Main recommendation function
# ----------------------------
def recommend_top_stocks(transactions_df, stocks_df, top_n=5):
    if transactions_df.empty:
        return pd.DataFrame(columns=["stockname", "companyname", "buy_prob", "price"])
    # Merge portfolio with master stock info
    data = stocks_df.copy()

    # Fix price column (prefer live price if available)
    if "price_x" in data.columns and "price_y" in data.columns:
        data["price"] = data["price_y"].fillna(data["price_x"])
    elif "price_x" in data.columns:
        data.rename(columns={"price_x": "price"}, inplace=True)
    elif "price_y" in data.columns:
        data.rename(columns={"price_y": "price"}, inplace=True)

    # Temporal features
    if "timestamp" not in data.columns:
        data["timestamp"] = pd.Timestamp.now()
    data["timestamp"] = pd.to_datetime(data["timestamp"])
    data["day_of_week"] = data["timestamp"].dt.dayofweek
    data["month"] = data["timestamp"].dt.month

    # User-level features
    user_agg = transactions_df.groupby("userid").agg(
        user_total_transactions=("stockname", "count"),
        user_avg_quantity=("quantity", "mean"),
        user_avg_value=("quantity", lambda x: np.mean(x * data.loc[x.index, "price"]))
    ).reset_index()
    user_features = user_agg.drop(columns="userid").iloc[0].to_dict()

# Add these as constant columns to all stocks
    for k, v in user_features.items():
        data[k] = v

    # Stock-level features
    stock_agg = transactions_df.groupby("stockname").agg(
        stock_total_transactions=("userid", "count"),
        stock_avg_quantity=("quantity", "mean")
    ).reset_index()
    data = data.merge(stock_agg, on="stockname", how="left")

    # Technical indicators
    data = add_technical_indicators(data)

    # Encode categorical
    categorical_cols = ["sector", "market_cap_bucket"]
    if any(col in stocks_df.columns for col in categorical_cols):
        data = pd.get_dummies(data, columns=[c for c in categorical_cols if c in stocks_df.columns])

    # Drop irrelevant
    drop_cols = ["transactionid", "userid", "portfolioid", "transactiontype", "timestamp"]
    X = data.drop(columns=drop_cols, errors="ignore")

    # Ensure numeric
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors="coerce")
    X.fillna(0, inplace=True)

    # Align with training cols
    for col in TRAIN_COLS:
        if col not in X.columns:
            X[col] = 0
    X = X[TRAIN_COLS]

    # Predict
    probs = model.predict_proba(X)[:, 1]
    data["buy_prob"] = probs

    # Filter: exclude stocks already in user’s portfolio
    portfolio_stocks = set(transactions_df["stockname"].unique())
    recs = data[~data["stockname"].isin(portfolio_stocks)]
    # Top N
    recs = recs.drop_duplicates(subset=["stockname"])

    top_recs = data.sort_values("buy_prob", ascending=False).head(top_n)

    # Final columns
    cols_to_return = [c for c in ["stockname", "companyname", "buy_prob", "price"] if c in top_recs.columns]
    return top_recs[cols_to_return]


# ----------------------------
# Demo runner
# ----------------------------
if __name__ == "__main__":
    userid = 1

    # Fetch data from portfolio service
    transactions_df = fetch_transactions(userid)
    stocks_df = fetch_stock_universe(limit=100)

    # Fetch live prices for those 100 stocks
    ltp_df = fetch_ltp(stocks_df["stockname"].tolist())
    stocks_df = stocks_df.merge(ltp_df, on="stockname", how="left")

    # Run recommender
    top5 = recommend_top_stocks(transactions_df, stocks_df, top_n=5)
    print("Top Recommendations:")
    print(top5)

import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import yfinance as yf

from model_manager import get_model, get_scaler, get_meta
from db_manager import get_stock_data, save_stock_data

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SEQ_LEN = 60
MC_DROPOUT_SAMPLES = 40
CONFIDENCE_SCALING = 10
FEATURE_COLS = ["Close", "Volume", "SMA_20", "RSI_14", "MACD"]


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate SMA_20, RSI_14, and MACD technical indicators."""
    df = df.copy()
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0.0)

    # 1. 20-day Simple Moving Average
    df["SMA_20"] = df["Close"].rolling(window=20, min_periods=1).mean()

    # 2. 14-day Relative Strength Index
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
    rs = gain / (loss + 1e-10)
    df["RSI_14"] = 100 - (100 / (1 + rs))
    df["RSI_14"] = df["RSI_14"].fillna(50.0)

    # 3. MACD (EMA12 - EMA26)
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD"] = df["MACD"].fillna(0.0)

    df.dropna(subset=["Close"], inplace=True)
    return df


def predict_price(ticker: str):
    ticker = ticker.strip().upper()
    if not ticker.endswith(".NS"):
        ticker += ".NS"

    try:
        model = get_model(ticker)
        scaler = get_scaler(ticker)
        meta = get_meta(ticker)

        if model is None:
            return {"success": False, "error": f"Model for {ticker} not loaded."}
        if scaler is None:
            return {"success": False, "error": f"Scaler for {ticker} not loaded."}
    except Exception as e:
        return {"success": False, "error": f"Failed to load model: {str(e)}"}

    # Fetch recent prices to keep cache up to date
    try:
        latest_df = yf.download(ticker, period="10d", progress=False)
        if not latest_df.empty:
            if isinstance(latest_df.columns, pd.MultiIndex):
                latest_df.columns = latest_df.columns.get_level_values(0)
            latest_df = (
                latest_df[["Close", "Volume"]]
                .reset_index()
                .rename(columns={"Datetime": "Date", "index": "Date"})
            )
            latest_df = latest_df[["Date", "Close", "Volume"]]
            save_stock_data(ticker, latest_df)
    except Exception as e:
        print(f"Warning: Failed to fetch latest yfinance data: {e}")

    # Load complete dataset from SQLite cache
    data_df = get_stock_data(ticker)

    # Fallback to CSV if DB is empty
    if data_df.empty:
        csv_file = os.path.join(DATA_DIR, f"data_{ticker}.csv")
        if os.path.exists(csv_file):
            data_df = pd.read_csv(csv_file)
            save_stock_data(ticker, data_df)
        else:
            return {"success": False, "error": f"No data found for {ticker}."}

    # Calculate indicators
    data_df = add_technical_indicators(data_df)
    if len(data_df) < SEQ_LEN:
        return {"success": False, "error": "Not enough historical data."}

    # Prepare Historical Chart Data (last 60 trading days)
    recent_history = data_df.tail(SEQ_LEN)
    historical_chart = [
        {
            "date": str(row["Date"])[:10],
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]) if pd.notnull(row["Volume"]) else 0,
        }
        for _, row in recent_history.iterrows()
    ]

    # Prepare features matrix for model
    num_features = len(FEATURE_COLS)
    
    # Ensure scaler feature count matches
    try:
        feature_matrix = data_df[FEATURE_COLS].values
        scaled_matrix = scaler.transform(feature_matrix)
    except Exception:
        # If scaler was trained on 1 feature (legacy univariate), fallback gracefully
        feature_matrix = data_df[["Close"]].values
        scaled_matrix = scaler.transform(feature_matrix)
        num_features = 1

    last_seq = scaled_matrix[-SEQ_LEN:].copy()

    # ── Multi-Day (7-Day) Forecast with MC Dropout ──
    forecast_chart = []
    current_seq = last_seq.reshape(1, SEQ_LEN, num_features)
    
    last_date_str = str(data_df["Date"].iloc[-1])[:10]
    try:
        curr_date = datetime.strptime(last_date_str, "%Y-%m-%d")
    except Exception:
        curr_date = datetime.now()

    next_day_predicted_price = 0.0
    next_day_low = 0.0
    next_day_high = 0.0
    next_day_confidence = 0.0

    for day_step in range(1, 8):
        # Move date forward (skipping weekends)
        curr_date += timedelta(days=1)
        while curr_date.weekday() in (5, 6):
            curr_date += timedelta(days=1)
        date_str = curr_date.strftime("%Y-%m-%d")

        batch_input = np.repeat(current_seq, MC_DROPOUT_SAMPLES, axis=0)
        mc_samples = model(batch_input, training=True).numpy()

        # Inverse transform scaled close predictions
        if num_features > 1:
            dummy_arr = np.zeros((len(mc_samples), num_features))
            dummy_arr[:, 0] = mc_samples.flatten()
            rescaled_samples = scaler.inverse_transform(dummy_arr)[:, 0]
        else:
            rescaled_samples = scaler.inverse_transform(mc_samples).flatten()

        step_pred = float(np.mean(rescaled_samples))
        std_price = float(np.std(rescaled_samples))
        step_low = float(np.percentile(rescaled_samples, 10))
        step_high = float(np.percentile(rescaled_samples, 90))

        cov = std_price / step_pred if step_pred else 0
        step_conf = max(0.0, min(100.0, 100 * (1 - cov * CONFIDENCE_SCALING)))

        if day_step == 1:
            next_day_predicted_price = step_pred
            next_day_low = step_low
            next_day_high = step_high
            next_day_confidence = step_conf

        forecast_chart.append({
            "day": day_step,
            "date": date_str,
            "predicted_price": round(step_pred, 2),
            "low": round(step_low, 2),
            "high": round(step_high, 2),
            "confidence": round(step_conf, 2),
        })

        # Roll sequence forward for day_step + 1
        if num_features > 1:
            # Scale new predicted Close price
            dummy_single = np.zeros((1, num_features))
            dummy_single[0, 0] = step_pred
            # Reuse previous indicators scaled values
            dummy_single[0, 1:] = current_seq[0, -1, 1:]
            scaled_next_point = scaler.transform(dummy_single)[0]
        else:
            dummy_single = np.array([[step_pred]])
            scaled_next_point = scaler.transform(dummy_single)[0]

        # Shift window left by 1 and insert new point at end
        new_window = np.vstack([current_seq[0, 1:], scaled_next_point.reshape(1, num_features)])
        current_seq = new_window.reshape(1, SEQ_LEN, num_features)

    current_price = float(data_df["Close"].iloc[-1])
    change = next_day_predicted_price - current_price
    percent_change = (change / current_price) * 100

    if next_day_predicted_price > current_price:
        trend = "UP"
    elif next_day_predicted_price < current_price:
        trend = "DOWN"
    else:
        trend = "SIDEWAYS"

    # Latest technical indicators for UI badge
    latest_rsi = float(data_df["RSI_14"].iloc[-1]) if "RSI_14" in data_df else 50.0
    rsi_status = "OVERBOUGHT" if latest_rsi > 70 else ("OVERSOLD" if latest_rsi < 30 else "NEUTRAL")

    return {
        "success": True,
        "ticker": ticker,
        "last_available_date": str(data_df["Date"].iloc[-1])[:10],
        "current_price": round(current_price, 2),
        "predicted_price": round(next_day_predicted_price, 2),
        "predicted_price_range": {
            "low": round(next_day_low, 2),
            "high": round(next_day_high, 2),
        },
        "confidence_score": round(next_day_confidence, 2),
        "predicted_change": round(float(change), 2),
        "predicted_change_percent": round(float(percent_change), 2),
        "trend": trend,
        "historical_chart": historical_chart,
        "forecast_chart": forecast_chart,
        "technical_indicators": {
            "rsi": round(latest_rsi, 2),
            "rsi_status": rsi_status,
            "sma_20": round(float(data_df["SMA_20"].iloc[-1]), 2) if "SMA_20" in data_df else None,
            "macd": round(float(data_df["MACD"].iloc[-1]), 2) if "MACD" in data_df else None,
        },
        "model_accuracy": meta.get("model_accuracy") if meta else None,
        "model_trained_at": meta.get("trained_at") if meta else None,
    }




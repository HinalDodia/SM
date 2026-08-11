import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"
import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_percentage_error
from keras.models import Sequential
from keras.layers import LSTM, Dense, Dropout
from keras.callbacks import EarlyStopping

from db_manager import save_stock_data


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate SMA_20, RSI_14, and MACD technical indicators."""
    df = df.copy()
    # 1. 20-day Simple Moving Average
    df["SMA_20"] = df["Close"].rolling(window=20).mean()

    # 2. 14-day Relative Strength Index
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-10)
    df["RSI_14"] = 100 - (100 / (1 + rs))

    # 3. MACD (EMA12 - EMA26)
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26

    df.dropna(inplace=True)
    return df


def train_model(ticker: str):
    ticker = ticker.strip().upper()

    if not ticker.endswith(".NS"):
        ticker += ".NS"

    MODEL_DIR = "models"
    SCALER_DIR = "scalers"
    DATA_DIR = "data"
    META_DIR = "meta"
    SEQ_LEN = 60
    MAX_EPOCHS = 50
    BATCH_SIZE = 32

    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(SCALER_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(META_DIR, exist_ok=True)

    MODEL_FILE = os.path.join(MODEL_DIR, f"model_{ticker}.keras")
    SCALER_FILE = os.path.join(SCALER_DIR, f"scaler_{ticker}.joblib")
    DATA_FILE = os.path.join(DATA_DIR, f"data_{ticker}.csv")
    META_FILE = os.path.join(META_DIR, f"meta_{ticker}.json")

    try:
        df = yf.download(ticker, period="8y", progress=False)
        if df.empty:
            raise ValueError("Could not download data for this ticker.")
        # Flatten MultiIndex columns produced by yfinance >= 0.2
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        save_df = df[["Close", "Volume"]].reset_index().rename(
            columns={"index": "Date", "Datetime": "Date"}
        )
        save_df = save_df[["Date", "Close", "Volume"]]
        
        # Save to SQLite database safely
        save_stock_data(ticker, save_df)
        save_df.to_csv(DATA_FILE, index=False)
    except Exception as e:
        print(f"Error downloading data: {e}")
        return False

    # Calculate indicators
    featured_df = add_technical_indicators(save_df)
    feature_cols = ["Close", "Volume", "SMA_20", "RSI_14", "MACD"]
    feature_data = featured_df[feature_cols].values

    if len(feature_data) <= SEQ_LEN:
        print(f"Not enough data for {ticker}")
        return False

    # Scale multivariate data (5 features)
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(feature_data)

    x, y = [], []
    for i in range(SEQ_LEN, len(scaled_data)):
        x.append(scaled_data[i - SEQ_LEN:i])
        y.append(scaled_data[i, 0])  # Predict Next Day Close Price (column 0)
    x, y = np.array(x), np.array(y)

    if len(x) < 100:
        print(f"Not enough sequences for {ticker} to train reliably")
        return False

    # Train / Validation / Test split (80% trainval [90% train, 10% val], 20% test)
    test_split = int(0.8 * len(x))
    x_trainval, y_trainval = x[:test_split], y[:test_split]
    x_test, y_test = x[test_split:], y[test_split:]

    val_split = int(0.9 * len(x_trainval))
    x_train, y_train = x_trainval[:val_split], y_trainval[:val_split]
    x_val, y_val = x_trainval[val_split:], y_trainval[val_split:]

    # Build Multivariate LSTM Model
    num_features = len(feature_cols)
    model = Sequential([
        LSTM(50, return_sequences=True, input_shape=(SEQ_LEN, num_features)),
        Dropout(0.2),
        LSTM(50, return_sequences=False),
        Dropout(0.2),
        Dense(25, activation="relu"),
        Dense(1)
    ])
    model.compile(optimizer="adam", loss="mean_squared_error")

    early_stop = EarlyStopping(
        monitor="val_loss",
        patience=5,
        restore_best_weights=True,
    )

    print(f"\nTraining {ticker} multivariate LSTM model...")
    history = model.fit(
        x_train, y_train,
        validation_data=(x_val, y_val),
        epochs=MAX_EPOCHS,
        batch_size=BATCH_SIZE,
        callbacks=[early_stop],
        verbose=1,
    )

    # Evaluate honest test MAPE
    test_predictions = model.predict(x_test, verbose=0)
    
    # Rescale Close price (column 0) using dummy array
    dummy_pred = np.zeros((len(test_predictions), num_features))
    dummy_pred[:, 0] = test_predictions.flatten()
    test_predictions_rescaled = scaler.inverse_transform(dummy_pred)[:, 0]

    dummy_y = np.zeros((len(y_test), num_features))
    dummy_y[:, 0] = y_test.flatten()
    y_test_rescaled = scaler.inverse_transform(dummy_y)[:, 0]

    mape = mean_absolute_percentage_error(y_test_rescaled, test_predictions_rescaled)
    real_accuracy = round((1 - mape) * 100, 2)

    print(f"{ticker} — test accuracy (MAPE-based): {real_accuracy}% "
          f"(evaluated on {len(x_test)} held-out sequences)")

    # Save trained artifacts
    model.save(MODEL_FILE)
    joblib.dump(scaler, SCALER_FILE)

    meta = {
        "ticker": ticker,
        "model_accuracy": real_accuracy,
        "test_mape": round(float(mape), 6),
        "test_set_size": len(x_test),
        "epochs_trained": len(history.history["loss"]),
        "features": feature_cols,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(META_FILE, "w") as f:
        json.dump(meta, f, indent=2)

    print("Multivariate model, scaler, and metadata saved to disk.")

    return {
        "ticker": ticker,
        "model": MODEL_FILE,
        "scaler": SCALER_FILE,
        "data": DATA_FILE,
        "meta": META_FILE,
    }


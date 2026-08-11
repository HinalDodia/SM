import os
import json
import joblib
import pandas as pd
from keras.models import load_model

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_DIR = os.path.join(BASE_DIR, "models")
SCALER_DIR = os.path.join(BASE_DIR, "scalers")
META_DIR = os.path.join(BASE_DIR, "meta")

MODELS = {}
SCALERS = {}
META = {}


def load_all_models():
    """Load all pre-trained LSTM models, scalers, and accuracy metadata
    into memory. Called once at server startup so predictions are instant."""

    stock_list = pd.read_csv(os.path.join(BASE_DIR, "stock_list.csv"))

    for ticker in stock_list["SYMBOL"]:

        ticker = ticker.strip().upper()

        if not ticker.endswith(".NS"):
            ticker += ".NS"

        model_path = os.path.join(MODEL_DIR, f"model_{ticker}.keras")
        scaler_path = os.path.join(SCALER_DIR, f"scaler_{ticker}.joblib")
        meta_path = os.path.join(META_DIR, f"meta_{ticker}.json")

        if os.path.exists(model_path):
            MODELS[ticker] = load_model(model_path)

        if os.path.exists(scaler_path):
            SCALERS[ticker] = joblib.load(scaler_path)

        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                META[ticker] = json.load(f)

    print(f"Loaded {len(MODELS)} models, {len(SCALERS)} scalers, {len(META)} metadata files.")


def get_model(ticker):
    """Return the in-memory model for ticker, loading from disk on demand if missing."""
    if ticker not in MODELS:
        model_path = os.path.join(MODEL_DIR, f"model_{ticker}.keras")
        if os.path.exists(model_path):
            MODELS[ticker] = load_model(model_path)
    return MODELS.get(ticker)


def get_scaler(ticker):
    """Return the in-memory scaler for ticker, loading from disk on demand if missing."""
    if ticker not in SCALERS:
        scaler_path = os.path.join(SCALER_DIR, f"scaler_{ticker}.joblib")
        if os.path.exists(scaler_path):
            SCALERS[ticker] = joblib.load(scaler_path)
    return SCALERS.get(ticker)


def get_meta(ticker):
    """Return the saved accuracy metadata for ticker (model_accuracy,
    test_mape, epochs_trained, trained_at), loading from disk on demand
    if missing. Returns None if no metadata was ever saved for this ticker
    (e.g. trained with an older version of train.py)."""
    if ticker not in META:
        meta_path = os.path.join(META_DIR, f"meta_{ticker}.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                META[ticker] = json.load(f)
    return META.get(ticker)
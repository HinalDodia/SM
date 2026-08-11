import sys
import pandas as pd
from train import train_model

# Fix Windows console encoding for Unicode output
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def main():
    df = pd.read_csv("stock_list.csv")

    for ticker in df["SYMBOL"]:
        ticker = ticker.strip().upper()

        if not ticker.endswith(".NS"):
            ticker = f"{ticker}.NS"

        print(f"\n{'=' * 50}")
        print(f"Training {ticker}")

        result = train_model(ticker)

        if result:
            print(f"[OK] {ticker} trained successfully.")
        else:
            print(f"[FAILED] {ticker} training failed.")

    print("\nAll stocks processed.")

if __name__ == "__main__":
    main()
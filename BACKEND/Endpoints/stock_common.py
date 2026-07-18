# stock_common.py
# Shared helper used by multiple stock endpoint files:
# stock_page.py, stock_chart.py, stock_headlines.py,
# stock_competitors.py, stock_dividend.py
#
# NOTE: stock_earnings.py and stock_short_interest.py have their OWN
# separate versions of get_yf_symbol() with different logic — those are
# kept local to those files on purpose (not using this shared one).

import os
import pandas as pd

# Module-level CSV load — importable by stock_dividend.py etc.
try:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CSV_PATH = os.path.join(BASE_DIR, "invest", "stock_list.csv")
    stock_df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)
except (FileNotFoundError, pd.errors.EmptyDataError):
    stock_df = pd.DataFrame(columns=["SYMBOL", "NAME OF COMPANY"])


def get_yf_symbol(symbol):
    symbol = symbol.upper()

    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        return symbol

    return f"{symbol}.NS"

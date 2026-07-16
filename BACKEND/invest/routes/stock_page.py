"""
/stock-page/<symbol>

Aggregates all key statistics, ratios, dividend info, and company
profile into a single JSON response for the stock detail page.
"""

import yfinance as yf
from datetime import date as date_type
from flask import Blueprint, jsonify
from flask_cors import cross_origin

from ..routes_utils import get_yf_symbol

stock_page_bp = Blueprint("stock_page_bp", __name__)


def _get_price_ranges(ticker):
    """Fetch today's, 50-day, and 52-week high/low price ranges."""
    hist = ticker.history(period="6mo")
    today_low  = float(hist["Low"].iloc[-1])  if not hist.empty else None
    today_high = float(hist["High"].iloc[-1]) if not hist.empty else None

    range50 = ticker.history(period="50d")
    range52 = ticker.history(period="1y")

    return {
        "today":   [today_low, today_high],
        "day_50":  [
            float(range50["Low"].min())  if not range50.empty else None,
            float(range50["High"].max()) if not range50.empty else None,
        ],
        "week_52": [
            float(range52["Low"].min())  if not range52.empty else None,
            float(range52["High"].max()) if not range52.empty else None,
        ],
    }


def _get_dividend_dates(ticker):
    """Return last two dividend dates and amounts from dividend history."""
    dividends = ticker.dividends

    if dividends is None or dividends.empty:
        return {k: None for k in [
            "record_date_1", "record_date_2",
            "ex_div_1", "ex_div_2",
            "div_payable_1", "div_payable_2",
            "div_amt_1", "div_amt_2",
        ]}

    last_div = dividends.tail(2)
    result = {k: None for k in [
        "record_date_1", "record_date_2",
        "ex_div_1", "ex_div_2",
        "div_payable_1", "div_payable_2",
        "div_amt_1", "div_amt_2",
    ]}

    if len(last_div) >= 1:
        date_str = str(last_div.index[-1].date())
        result["ex_div_1"] = result["record_date_1"] = result["div_payable_1"] = date_str
        result["div_amt_1"] = float(last_div.iloc[-1])

    if len(last_div) >= 2:
        date_str = str(last_div.index[-2].date())
        result["ex_div_2"] = result["record_date_2"] = result["div_payable_2"] = date_str
        result["div_amt_2"] = float(last_div.iloc[-2])

    return result


def _get_balance_sheet_metrics(ticker, info):
    """
    Fill in debt_eq, curr_ratio, quick_ratio, and book_val from the
    balance sheet when yfinance info does not provide them directly.
    """
    debt_eq    = info.get("debtToEquity")
    curr_ratio = info.get("currentRatio")
    quick_ratio = info.get("quickRatio")
    book_val   = info.get("bookValue")

    if debt_eq is None or curr_ratio is None or book_val is None:
        bs = ticker.balance_sheet
        if bs is not None and not bs.empty:
            col = bs.columns[0]

            if debt_eq is None:
                td = bs.loc["Total Debt", col]        if "Total Debt"           in bs.index else None
                te = bs.loc["Stockholders Equity", col] if "Stockholders Equity" in bs.index else None
                if td and te:
                    debt_eq = round((td / te) * 100, 2)

            if curr_ratio is None:
                tca = bs.loc["Total Current Assets", col] if "Total Current Assets" in bs.index else None
                tcl = bs.loc["Current Liabilities", col]  if "Current Liabilities"  in bs.index else None
                if tca and tcl:
                    curr_ratio = round(tca / tcl, 2)

                if quick_ratio is None and tca and tcl:
                    inv = bs.loc["Inventory", col] if "Inventory" in bs.index else 0
                    quick_ratio = round((tca - inv) / tcl, 2)

            if book_val is None:
                te = bs.loc["Stockholders Equity", col] if "Stockholders Equity" in bs.index else None
                shares = info.get("sharesOutstanding") or 1
                if te and shares > 1:
                    book_val = round(te / shares, 2)

    return debt_eq, curr_ratio, quick_ratio, book_val


def _get_cashflow(ticker, info):
    """Return operating cash flow, falling back to the cashflow statement."""
    cash_flow = info.get("operatingCashflow")
    if cash_flow is None:
        cfs = ticker.cashflow
        if cfs is not None and not cfs.empty:
            cf_col = cfs.columns[0]
            op_cf = cfs.loc["Operating Cash Flow", cf_col] if "Operating Cash Flow" in cfs.index else None
            if op_cf:
                cash_flow = float(op_cf)
    return cash_flow


def _safe_div(a, b):
    try:
        return round(a / b, 2) if b else None
    except Exception:
        return None


def _build_valuation_ratios(info, book_val, cash_flow):
    """
    Compute price/sales, price/cashflow, and price/book,
    using balance-sheet fallbacks when yfinance info is incomplete.
    """
    price_sales    = info.get("priceToSalesTrailing12Months")
    price_cashflow = info.get("priceToCashflow")
    price_book     = info.get("priceToBook")
    annual_sales   = info.get("totalRevenue")
    curr_price     = info.get("currentPrice") or info.get("previousClose")

    if price_book is None and book_val and curr_price:
        price_book = _safe_div(curr_price, book_val)

    if price_sales is None and annual_sales and curr_price:
        shares = info.get("sharesOutstanding") or 0
        if shares:
            price_sales = _safe_div(curr_price, annual_sales / shares)

    if price_cashflow is None and cash_flow and curr_price:
        shares = info.get("sharesOutstanding") or 0
        if shares:
            price_cashflow = _safe_div(curr_price, cash_flow / shares)

    return price_sales, price_cashflow, price_book, annual_sales


RATING_SCORE_MAP = {
    "strong_buy":  4,
    "buy":         3,
    "hold":        2,
    "sell":        1,
    "strong_sell": 0,
}


@stock_page_bp.route("/stock-page/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def stock_page(symbol):
    try:
        yf_sym = get_yf_symbol(symbol)
        ticker = yf.Ticker(yf_sym)
        info   = ticker.info or {}

        # Price ranges
        ranges = _get_price_ranges(ticker)

        # Dividend calendar
        div = _get_dividend_dates(ticker)

        # Balance sheet fallbacks
        debt_eq, curr_ratio, quick_ratio, book_val = _get_balance_sheet_metrics(ticker, info)

        # Cash flow fallback
        cash_flow = _get_cashflow(ticker, info)

        # Valuation ratios with fallbacks
        price_sales, price_cashflow, price_book, annual_sales = _build_valuation_ratios(
            info, book_val, cash_flow
        )

        # Upside to analyst target
        current_price = info.get("currentPrice")
        target_mean   = info.get("targetMeanPrice")
        upside = None
        if current_price and target_mean:
            upside = round(((target_mean - current_price) / current_price) * 100, 2)

        rating_score = RATING_SCORE_MAP.get(info.get("recommendationKey", ""), 2)

        return jsonify({
            "company_overview": {
                "name":        info.get("longName") or "Stock Data Unavailable",
                "symbol":      symbol,
                "description": info.get("longBusinessSummary") or (
                    f"Fetched {len(info)} fields from yfinance" if info else "No data from yfinance"
                ),
                "website":     info.get("website"),
            },

            "key_stats": {
                "today_range":    ranges["today"],
                "50day_range":    ranges["day_50"],
                "52week_range":   ranges["week_52"],
                "volume":         info.get("volume"),
                "avg_volume":     info.get("averageVolume"),
                "market_cap":     info.get("marketCap"),
                "pe_ratio":       info.get("trailingPE"),
                "dividend_yield": info.get("dividendYield"),
                "price_target":   info.get("targetMeanPrice"),
                "consensus_rating": info.get("recommendationKey"),
            },

            "company_calendar": {
                "today":              str(date_type.today()),
                "last_earnings":      str(info.get("lastFiscalYearEnd")),
                "ex_dividend":        str(info.get("exDividendDate")) if info.get("exDividendDate") else div["ex_div_1"],
                "record_date_1":      div["record_date_1"],
                "record_date_2":      div["record_date_2"],
                "ex_dividend_2":      div["ex_div_2"],
                "dividend_payable":   div["div_payable_1"],
                "dividend_payable_2": div["div_payable_2"],
                "div_amt_1":          div["div_amt_1"],
                "div_amt_2":          div["div_amt_2"],
                "fiscal_year_end":    info.get("lastFiscalYearEnd"),
            },

            "industry_profile": {
                "exchange":         info.get("exchange"),
                "sector":           info.get("sector"),
                "industry":         info.get("industry"),
                "sub_industry":     info.get("industry"),
                "symbol":           symbol,
                "previous_symbol":  info.get("priorSymbol", "N/A"),
                "cik":              info.get("cik"),
                "website":          info.get("website"),
                "phone":            info.get("phone"),
                "fax":              info.get("fax", "N/A"),
                "employees":        info.get("fullTimeEmployees"),
                "year_founded":     info.get("founded", "N/A"),
            },

            "price_target_rating": {
                "avg_target":              info.get("targetMeanPrice"),
                "high_target":             info.get("targetHighPrice"),
                "low_target":              info.get("targetLowPrice"),
                "potential_upside_percent": upside,
                "consensus_rating":        info.get("recommendationKey"),
                "rating_score":            rating_score,
                "research_coverage":       info.get("numberOfAnalystOpinions"),
            },

            "profitability": {
                "eps":           info.get("trailingEps"),
                "trailing_pe":   info.get("trailingPE"),
                "forward_pe":    info.get("forwardPE"),
                "peg_ratio":     info.get("pegRatio"),
                "net_income":    info.get("netIncomeToCommon"),
                "net_margin":    info.get("profitMargins"),
                "pretax_margin": info.get("profitMargins"),
                "roe":           info.get("returnOnEquity"),
                "roa":           info.get("returnOnAssets"),
            },

            "debt": {
                "debt_equity":  debt_eq,
                "current_ratio": curr_ratio,
                "quick_ratio":  quick_ratio,
            },

            "sales_book": {
                "annual_sales":   annual_sales,
                "price_sales":    price_sales,
                "cashflow":       cash_flow,
                "price_cashflow": price_cashflow,
                "book_value":     book_val,
                "price_book":     price_book,
            },

            "misc": {
                "shares_outstanding": info.get("sharesOutstanding"),
                "float_shares":       info.get("floatShares"),
                "marketcap":          info.get("marketCap"),
                "optionable":         True,
                "beta":               info.get("beta"),
            },
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)})

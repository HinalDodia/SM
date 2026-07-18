from flask import Blueprint, jsonify
from flask_cors import cross_origin
import pandas as pd
import yfinance as yf
from datetime import datetime
import traceback
from .stock_common import get_yf_symbol

stock_financials_bp = Blueprint("stock_financials_bp", __name__)

@stock_financials_bp.route("/financials/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def financials_page(symbol):

    try:

        

        # ---------------------------------------------------
        # HELPERS
        # ---------------------------------------------------

        def safe_float(val):

            try:

                if val is None:
                    return None

                if pd.isna(val):
                    return None

                return float(val)

            except:
                return None

        def safe_get(df, row, col):

            try:

                if row in df.index:
                    return safe_float(df.loc[row, col])

                return None

            except:
                return None

        # ---------------------------------------------------
        # FORMATTERS
        # ---------------------------------------------------

        def format_cr(value):

            val = safe_float(value)

            if val is None:
                return None

            return round(val / 10000000, 2)

        def format_currency_cr(value):

            val = format_cr(value)

            if val is None:
                return None

            return f"₹{val:,.0f} Cr"

        def format_large_currency(value):

            val = safe_float(value)

            if val is None:
                return None

            if val >= 1_000_000_000_000:
                return f"₹{round(val / 1_000_000_000_000, 2)}T"

            if val >= 1_000_000_000:
                return f"₹{round(val / 1_000_000_000, 2)}B"

            return f"₹{round(val / 1_000_000, 2)}M"

        # ---------------------------------------------------
        # GROWTH
        # ---------------------------------------------------

        def calculate_growth(curr, prev):

            try:

                if curr is None or prev is None:
                    return None

                if prev == 0:
                    return None

                return round(
                    ((curr - prev) / abs(prev)) * 100,
                    2
                )

            except:
                return None

        # ---------------------------------------------------
        # QUARTER LABEL
        # ---------------------------------------------------

        def quarter_label(date):

            try:

                dt = pd.to_datetime(date)

                q = (dt.month - 1) // 3 + 1

                return f"Q{q} {dt.year}"

            except:
                return None

        # ---------------------------------------------------
        # SYMBOL NORMALIZATION
        # ---------------------------------------------------

        symbol = symbol.upper().strip()

        special_map = {
            "M&M": "M&M.NS",
            "BAJAJ-AUTO": "BAJAJ-AUTO.NS"
        }

        if symbol in special_map:
            yf_symbol = special_map[symbol]

        elif not symbol.endswith(".NS"):
            yf_symbol = f"{symbol}.NS"

        else:
            yf_symbol = symbol

        # ---------------------------------------------------
        # INIT
        # ---------------------------------------------------

        ticker = yf.Ticker(yf_symbol)

        info = ticker.info or {}

        # ---------------------------------------------------
        # STATEMENTS
        # ---------------------------------------------------

        income = ticker.income_stmt
        quarterly_income = ticker.quarterly_income_stmt

        cashflow = ticker.cashflow
        quarterly_cashflow = ticker.quarterly_cashflow

        balance = ticker.balance_sheet
        quarterly_balance = ticker.quarterly_balance_sheet

        # ---------------------------------------------------
        # COMPANY
        # ---------------------------------------------------

        company_name = (
            info.get("longName")
            or info.get("shortName")
            or symbol
        )

        # ---------------------------------------------------
        # BUILD INCOME STATEMENT
        # ---------------------------------------------------

        def build_income_statement(df, quarterly=False):

            result = []

            if df is None or df.empty:
                return result

            cols = list(reversed(df.columns[:8]))

            prev_revenue = None
            prev_net_income = None

            for col in cols:

                revenue = safe_get(
                    df,
                    "Total Revenue",
                    col
                )

                gross_profit = safe_get(
                    df,
                    "Gross Profit",
                    col
                )

                operating_income = safe_get(
                    df,
                    "Operating Income",
                    col
                )

                pretax_income = safe_get(
                    df,
                    "Pretax Income",
                    col
                )

                net_income = safe_get(
                    df,
                    "Net Income",
                    col
                )

                diluted_eps = safe_get(
                    df,
                    "Diluted EPS",
                    col
                )

                row = {

                    "year":
                        str(col.year),

                    "period_end":
                        str(col.date()),

                    "quarter":
                        quarter_label(col)
                        if quarterly
                        else None,

                    "revenue":
                        format_cr(revenue),

                    "revenue_display":
                        format_currency_cr(revenue),

                    "gross_profit":
                        format_cr(gross_profit),

                    "gross_profit_display":
                        format_currency_cr(gross_profit),

                    "operating_income":
                        format_cr(operating_income),

                    "operating_income_display":
                        format_currency_cr(
                            operating_income
                        ),

                    "pretax_income":
                        format_cr(pretax_income),

                    "pretax_income_display":
                        format_currency_cr(
                            pretax_income
                        ),

                    "net_income":
                        format_cr(net_income),

                    "net_income_display":
                        format_currency_cr(net_income),

                    "eps":
                        diluted_eps,

                    # Sequential QoQ / YoY growth
                    "revenue_growth":
                        calculate_growth(
                            revenue,
                            prev_revenue
                        ),

                    "net_income_growth":
                        calculate_growth(
                            net_income,
                            prev_net_income
                        ),

                    "growth_type":
                        (
                            "qoq"
                            if quarterly
                            else "yoy"
                        )
                }

                result.append(row)

                prev_revenue = revenue
                prev_net_income = net_income

            result = [
                x for x in result
                if x["revenue"] is not None
            ]

            return result

        # ---------------------------------------------------
        # BUILD CASHFLOW
        # ---------------------------------------------------

        def build_cashflow_statement(df, quarterly=False):

            result = []

            if df is None or df.empty:
                return result

            cols = list(reversed(df.columns[:8]))

            for col in cols:

                operating_cf = safe_get(
                    df,
                    "Operating Cash Flow",
                    col
                )

                free_cf = safe_get(
                    df,
                    "Free Cash Flow",
                    col
                )

                capex = safe_get(
                    df,
                    "Capital Expenditure",
                    col
                )

                investing_cf = safe_get(
                    df,
                    "Investing Cash Flow",
                    col
                )

                financing_cf = safe_get(
                    df,
                    "Financing Cash Flow",
                    col
                )

                row = {

                    "year":
                        str(col.year),

                    "period_end":
                        str(col.date()),

                    "quarter":
                        quarter_label(col)
                        if quarterly
                        else None,

                    "operating_cashflow":
                        format_cr(operating_cf),

                    "operating_cashflow_display":
                        format_currency_cr(
                            operating_cf
                        ),

                    "free_cashflow":
                        format_cr(free_cf),

                    "free_cashflow_display":
                        format_currency_cr(
                            free_cf
                        ),

                    "capital_expenditure":
                        format_cr(capex),

                    "capital_expenditure_display":
                        format_currency_cr(capex),

                    "investing_cashflow":
                        format_cr(investing_cf),

                    "financing_cashflow":
                        format_cr(financing_cf)
                }

                result.append(row)

            result = [
                x for x in result
                if x["operating_cashflow"] is not None
            ]

            return result

        # ---------------------------------------------------
        # BUILD BALANCE SHEET
        # ---------------------------------------------------

        def build_balance_sheet(df, quarterly=False):

            result = []

            if df is None or df.empty:
                return result

            cols = list(reversed(df.columns[:8]))

            for col in cols:

                assets = safe_get(
                    df,
                    "Total Assets",
                    col
                )

                liabilities = safe_get(
                    df,
                    "Total Liabilities Net Minority Interest",
                    col
                )

                equity = safe_get(
                    df,
                    "Stockholders Equity",
                    col
                )

                debt = safe_get(
                    df,
                    "Total Debt",
                    col
                )

                cash = safe_get(
                    df,
                    "Cash And Cash Equivalents",
                    col
                )

                current_assets = safe_get(
                    df,
                    "Current Assets",
                    col
                )

                current_liabilities = safe_get(
                    df,
                    "Current Liabilities",
                    col
                )

                row = {

                    "year":
                        str(col.year),

                    "period_end":
                        str(col.date()),

                    "quarter":
                        quarter_label(col)
                        if quarterly
                        else None,

                    "total_assets":
                        format_cr(assets),

                    "total_assets_display":
                        format_currency_cr(assets),

                    "total_liabilities":
                        format_cr(liabilities),

                    "total_liabilities_display":
                        format_currency_cr(
                            liabilities
                        ),

                    "total_equity":
                        format_cr(equity),

                    "total_equity_display":
                        format_currency_cr(equity),

                    "total_debt":
                        format_cr(debt),

                    "total_debt_display":
                        format_currency_cr(debt),

                    "cash":
                        format_cr(cash),

                    "cash_display":
                        format_currency_cr(cash),

                    "current_assets":
                        format_cr(current_assets),

                    "current_liabilities":
                        format_cr(current_liabilities)
                }

                result.append(row)

            result = [
                x for x in result
                if x["total_assets"] is not None
            ]

            return result

        # ---------------------------------------------------
        # ANNUAL
        # ---------------------------------------------------

        income_statement = build_income_statement(
            income,
            quarterly=False
        )

        cashflow_statement = build_cashflow_statement(
            cashflow,
            quarterly=False
        )

        balance_sheet = build_balance_sheet(
            balance,
            quarterly=False
        )

        # ---------------------------------------------------
        # QUARTERLY
        # ---------------------------------------------------

        quarterly_income_statement = (
            build_income_statement(
                quarterly_income,
                quarterly=True
            )
        )

        quarterly_cashflow_statement = (
            build_cashflow_statement(
                quarterly_cashflow,
                quarterly=True
            )
        )

        quarterly_balance_sheet = (
            build_balance_sheet(
                quarterly_balance,
                quarterly=True
            )
        )

        # ---------------------------------------------------
        # RATIOS
        # ---------------------------------------------------

        dividend_yield = safe_float(
            info.get("dividendYield")
        )

        dividend_yield_percent = None

        if dividend_yield is not None:

            # Yahoo sometimes returns:
            # 0.0509 OR 5.09

            if dividend_yield <= 1:
                dividend_yield_percent = round(
                    dividend_yield * 100,
                    2
                )
            else:
                dividend_yield_percent = round(
                    dividend_yield,
                    2
                )

        ratios = {

            "market_cap":
                format_large_currency(
                    info.get("marketCap")
                ),

            "pe_ratio":
                safe_float(
                    info.get("trailingPE")
                ),

            "forward_pe":
                safe_float(
                    info.get("forwardPE")
                ),

            "price_to_sales":
                safe_float(
                    info.get(
                        "priceToSalesTrailing12Months"
                    )
                ),

            "price_to_book":
                safe_float(
                    info.get("priceToBook")
                ),

            "gross_margin":
                round(
                    (info.get("grossMargins") or 0) * 100,
                    2
                ),

            "operating_margin":
                round(
                    (info.get("operatingMargins") or 0) * 100,
                    2
                ),

            "profit_margin":
                round(
                    (info.get("profitMargins") or 0) * 100,
                    2
                ),

            "roe":
                round(
                    (info.get("returnOnEquity") or 0) * 100,
                    2
                ),

            "roa":
                round(
                    (info.get("returnOnAssets") or 0) * 100,
                    2
                ),

            "current_ratio":
                safe_float(
                    info.get("currentRatio")
                ),

            "debt_to_equity":
                safe_float(
                    info.get("debtToEquity")
                ),

            "dividend_yield":
                dividend_yield,

            "dividend_yield_percent":
                dividend_yield_percent,

            "dividend_yield_display":
                (
                    f"{dividend_yield_percent}%"
                    if dividend_yield_percent is not None
                    else None
                ),

            "beta":
                safe_float(
                    info.get("beta")
                )
        }

        # ---------------------------------------------------
        # CHARTS
        # ---------------------------------------------------

        revenue_chart = []

        income_chart = []

        for row in income_statement:

            revenue_chart.append({

                "year":
                    row["year"],

                "revenue":
                    row["revenue"],

                "net_income":
                    row["net_income"]
            })

            income_chart.append({

                "year":
                    row["year"],

                "gross_profit":
                    row["gross_profit"],

                "operating_income":
                    row["operating_income"],

                "net_income":
                    row["net_income"]
            })

        # ---------------------------------------------------
        # AI SUMMARY
        # ---------------------------------------------------

        latest = (
            income_statement[-1]
            if income_statement
            else {}
        )

        ai_summary = [

            f"{company_name} generated revenue of {latest.get('revenue_display')} in the latest fiscal year.",

            f"Net income stood at {latest.get('net_income_display')} with operating income of {latest.get('operating_income_display')}.",

            f"Operating margin is currently {ratios.get('operating_margin')}% while ROE stands at {ratios.get('roe')}%.",

            f"The company maintains a current ratio of {ratios.get('current_ratio')} and debt-to-equity ratio of {ratios.get('debt_to_equity')}."
        ]

        # ---------------------------------------------------
        # FAQS
        # ---------------------------------------------------

        faqs = [

            {
                "question":
                    f"What was {company_name}'s latest annual revenue?",

                "answer":
                    f"{company_name} reported annual revenue of {latest.get('revenue_display')} in the latest fiscal year."
            },

            {
                "question":
                    f"What is {company_name}'s operating margin?",

                "answer":
                    f"{company_name} currently has an operating margin of {ratios.get('operating_margin')}%."
            },

            {
                "question":
                    f"How profitable is {company_name}?",

                "answer":
                    f"The company reported net income of {latest.get('net_income_display')} with ROE of {ratios.get('roe')}%."
            }
        ]

        # ---------------------------------------------------
        # TABLE CONFIG
        # ---------------------------------------------------

        table_config = {

            "currency": "INR",

            "unit": "Cr",

            "annual_periods":
                len(income_statement),

            "quarterly_periods":
                len(quarterly_income_statement)
        }

        # ---------------------------------------------------
        # FINAL RESPONSE
        # ---------------------------------------------------

        return jsonify({

            "success": True,

            "symbol":
                symbol.replace(".NS", ""),

            "company_name":
                company_name,

            "table_config":
                table_config,

            # annual
            "income_statement":
                income_statement,

            "cashflow_statement":
                cashflow_statement,

            "balance_sheet":
                balance_sheet,

            # quarterly
            "quarterly_income_statement":
                quarterly_income_statement,

            "quarterly_cashflow_statement":
                quarterly_cashflow_statement,

            "quarterly_balance_sheet":
                quarterly_balance_sheet,

            # ratios
            "ratios":
                ratios,

            # charts
            "revenue_chart":
                revenue_chart,

            "income_chart":
                income_chart,

            # insights
            "ai_summary":
                ai_summary,

            "faqs":
                faqs
        })

    except Exception as e:

        import traceback

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

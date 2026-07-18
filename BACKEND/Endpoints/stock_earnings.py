from flask import Blueprint, jsonify, g
from flask_cors import cross_origin
import pandas as pd
import yfinance as yf
from datetime import datetime
import traceback

stock_earnings_bp = Blueprint("stock_earnings_bp", __name__)

@stock_earnings_bp.route("/earnings/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def earnings_page(symbol):
    try:
       

        # ---------------------------------------------------
        # SYMBOL NORMALIZATION
        # ---------------------------------------------------

        def get_yf_symbol(sym):

            sym = str(sym).upper().strip()

            special_map = {
                "M&M": "M&M.NS",
                "BAJAJ-AUTO": "BAJAJ-AUTO.NS",
                "UNITDSPR": "MCDOWELL-N.NS"
            }

            if sym in special_map:
                return special_map[sym]

            if not sym.endswith(".NS"):
                return f"{sym}.NS"

            return sym

        # ---------------------------------------------------
        # INIT
        # ---------------------------------------------------

        ticker = yf.Ticker(get_yf_symbol(symbol))

        info = ticker.info or {}

        try:
            earnings_dates = ticker.get_earnings_dates(limit=12)
        except Exception:
            earnings_dates = None

        q_income = getattr(
            ticker,
            "quarterly_income_stmt",
            None
        )

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

        def get_quarter_label(date_val):

            try:

                date_val = pd.to_datetime(date_val)

                q = (date_val.month - 1) // 3 + 1

                return f"Q{q} {date_val.year}"

            except:
                return None

        def map_analyst_quarter_label(label):

            mapping = {
                "0q": "Current Quarter",
                "+1q": "Next Quarter",
                "0y": "Current Year",
                "+1y": "Next Year"
            }

            return mapping.get(
                str(label).strip().lower(),
                str(label)
            )

        def get_currency_symbol(curr):

            return {
                "USD": "$",
                "INR": "₹",
                "EUR": "€",
                "GBP": "£"
            }.get(
                str(curr).upper(),
                "₹"
            )

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

        def format_market_cap(value):

            val = safe_float(value)

            if val is None:
                return None

            if val >= 1_000_000_000_000:
                return f"₹{round(val/1_000_000_000_000,2)}T"

            if val >= 1_000_000_000:
                return f"₹{round(val/1_000_000_000,2)}B"

            return f"₹{round(val/1_000_000,2)}M"

        def clean_company_name(name):

            if not name:
                return None

            replacements = {
                "SERV": "Services",
                "SVCS": "Services",
                "TECH": "Technology",
                "INFOTECH": "Infotech",
                "LT": "Ltd",
                "LTD": "Ltd"
            }

            words = name.title().split()

            cleaned = []

            for w in words:

                cleaned.append(
                    replacements.get(
                        w.upper(),
                        w
                    )
                )

            return " ".join(cleaned)

        # ---------------------------------------------------
        # REVENUE EXTRACTION
        # ---------------------------------------------------

        def extract_revenue(df, col):

            if df is None or df.empty:
                return None

            priority = [
                "Total Revenue",
                "Revenue",
                "Revenue From Operations",
                "Operating Revenue",
                "OperatingRevenue",
                "Net Sales",
                "Sales"
            ]

            # exact matches
            for key in priority:

                if key in df.index:

                    val = safe_float(
                        df.loc[key, col]
                    )

                    if val is not None:
                        return val

            # fuzzy revenue
            for idx in df.index:

                idx_lower = str(idx).lower()

                if "revenue" in idx_lower:

                    val = safe_float(
                        df.loc[idx, col]
                    )

                    if val is not None:
                        return val

            # fuzzy sales
            for idx in df.index:

                idx_lower = str(idx).lower()

                if "sales" in idx_lower:

                    val = safe_float(
                        df.loc[idx, col]
                    )

                    if val is not None:
                        return val

            return None

        # ---------------------------------------------------
        # CLOSEST REVENUE
        # ---------------------------------------------------

        def get_closest_revenue(
            earnings_date,
            q_income
        ):

            if q_income is None or q_income.empty:
                return None

            try:

                ed = pd.to_datetime(
                    earnings_date
                ).tz_localize(None)

                cols = []

                for col in q_income.columns:

                    try:

                        col_dt = pd.to_datetime(
                            col
                        ).tz_localize(None)

                        cols.append((col_dt, col))

                    except:
                        continue

                cols.sort()

                selected_col = None

                for dt, col in cols:

                    if dt <= ed:
                        selected_col = col
                    else:
                        break

                if selected_col is None:
                    return None

                return extract_revenue(
                    q_income,
                    selected_col
                )

            except:
                return None

        # ---------------------------------------------------
        # FILL MISSING QUARTERS
        # ---------------------------------------------------

        def fill_missing_quarters(data):

            if not data:
                return data

            filled = []

            for i in range(len(data) - 1):

                current = data[i]
                nxt = data[i + 1]

                filled.append(current)

                try:

                    cq = int(current["quarter"][1])
                    cy = int(current["quarter"][-4:])

                    nq = int(nxt["quarter"][1])
                    ny = int(nxt["quarter"][-4:])

                    diff = (ny - cy) * 4 + (nq - cq)

                    if diff > 1:

                        for j in range(1, diff):

                            q = cq + j
                            y = cy

                            if q > 4:
                                q -= 4
                                y += 1

                            filled.append({
                                "quarter": f"Q{q} {y}",
                                "date": None,
                                "revenue": None,
                                "revenue_display": None
                            })

                except:
                    pass

            filled.append(data[-1])

            return filled

        # ---------------------------------------------------
        # LATEST EARNINGS
        # ---------------------------------------------------

        latest = None

        if (
            earnings_dates is not None
            and not earnings_dates.empty
        ):

            reported = earnings_dates[
                earnings_dates["Reported EPS"].notna()
            ]

            latest = (
                reported.iloc[0]
                if not reported.empty
                else earnings_dates.iloc[0]
            )

        # ---------------------------------------------------
        # EPS
        # ---------------------------------------------------

        actual_eps = (
            safe_float(
                latest.get("Reported EPS")
            )
            if latest is not None
            else None
        )

        est_eps = (
            safe_float(
                latest.get("EPS Estimate")
            )
            if latest is not None
            else None
        )

        beat = None
        beat_percent = None

        if (
            actual_eps is not None
            and est_eps is not None
            and est_eps != 0
        ):

            beat = round(
                actual_eps - est_eps,
                2
            )

            beat_percent = round(
                (beat / abs(est_eps)) * 100,
                2
            )

        # ---------------------------------------------------
        # LATEST REVENUE
        # ---------------------------------------------------

        latest_revenue = None

        if (
            q_income is not None
            and not q_income.empty
        ):

            sorted_cols = sorted(
                list(q_income.columns),
                key=lambda x: pd.to_datetime(x),
                reverse=True
            )

            for col in sorted_cols:

                latest_revenue = extract_revenue(
                    q_income,
                    col
                )

                if latest_revenue:
                    break

        # ---------------------------------------------------
        # PRICE
        # ---------------------------------------------------

        current_price = safe_float(
            info.get("currentPrice")
        )

        previous_close = safe_float(
            info.get("previousClose")
        )

        change = None
        change_percent = None

        if (
            current_price is not None
            and previous_close is not None
        ):

            change = round(
                current_price - previous_close,
                2
            )

            if previous_close != 0:

                change_percent = round(
                    (change / previous_close) * 100,
                    2
                )

        # ---------------------------------------------------
        # SUMMARY
        # ---------------------------------------------------

        company_name = clean_company_name(
            info.get("shortName")
        )

        summary = {

            "company_name": company_name,

            "symbol": symbol.upper(),

            "exchange": "NSE",

            "currency": info.get(
                "currency",
                "INR"
            ),

            "current_price": current_price,

            "current_price_display":
                f"₹{current_price:,.2f}"
                if current_price is not None
                else None,

            "price_change": change,

            "price_change_percent":
                change_percent,

            "price_direction":
                "up"
                if change is not None and change >= 0
                else "down",

            "latest_earnings_date":
                str(
                    pd.to_datetime(
                        latest.name
                    ).date()
                )
                if latest is not None
                else None,

            "quarter":
                get_quarter_label(
                    latest.name
                )
                if latest is not None
                else None,

            "consensus_eps":
                est_eps,

            "actual_eps":
                actual_eps,

            "beat":
                beat,

            "beat_percent":
                beat_percent,

            "beat_direction":
                (
                    "beat"
                    if beat is not None and beat >= 0
                    else "miss"
                ),

            "actual_revenue":
                format_cr(
                    latest_revenue
                ),

            "actual_revenue_display":
                format_currency_cr(
                    latest_revenue
                ),

            "market_cap":
                safe_float(
                    info.get("marketCap")
                ),

            "market_cap_display":
                format_market_cap(
                    info.get("marketCap")
                ),

            "sector":
                info.get("sector"),

            "industry":
                info.get("industry"),

            "website":
                info.get("website"),

            "logo_url":
                info.get("logo_url")
        }

        # ---------------------------------------------------
        # SUMMARY TEXT
        # ---------------------------------------------------

        cs = get_currency_symbol(
            summary["currency"]
        )

        if (
            actual_eps is not None
            and est_eps is not None
        ):

            direction = (
                "beating"
                if beat >= 0
                else "missing"
            )

            summary["summary_text"] = (
                f"{company_name} reported EPS "
                f"of {cs}{actual_eps}, "
                f"{direction} analyst estimates "
                f"by {cs}{abs(beat)} "
                f"({round(beat_percent,2)}%) "
                f"for {summary['quarter']}."
            )

        # ---------------------------------------------------
        # EPS CHART
        # ---------------------------------------------------

        eps_chart = []

        if (
            earnings_dates is not None
            and not earnings_dates.empty
        ):

            df = earnings_dates.head(8)

            for idx, row in reversed(
                list(df.iterrows())
            ):

                idx_dt = pd.to_datetime(idx)

                eps_chart.append({

                    "date":
                        str(idx_dt.date()),

                    "quarter":
                        get_quarter_label(idx_dt),

                    "estimate_eps":
                        safe_float(
                            row.get(
                                "EPS Estimate"
                            )
                        ),

                    "actual_eps":
                        safe_float(
                            row.get(
                                "Reported EPS"
                            )
                        )
                })

        # ---------------------------------------------------
        # REVENUE CHART
        # ---------------------------------------------------

        revenue_chart = []

        if (
            q_income is not None
            and not q_income.empty
        ):

            sorted_cols = sorted(
                list(q_income.columns),
                key=lambda x: pd.to_datetime(x)
            )[-8:]

            for col in sorted_cols:

                col_dt = pd.to_datetime(col)

                revenue_val = extract_revenue(
                    q_income,
                    col
                )

                revenue_chart.append({

                    "date":
                        str(col_dt.date()),

                    "quarter":
                        get_quarter_label(col_dt),

                    "revenue":
                        format_cr(revenue_val),

                    "revenue_display":
                        format_currency_cr(
                            revenue_val
                        )
                })

            revenue_chart = fill_missing_quarters(
                revenue_chart
            )

        # ---------------------------------------------------
        # EARNINGS HISTORY TABLE
        # ---------------------------------------------------

        earnings_history_table = []

        if (
            earnings_dates is not None
            and not earnings_dates.empty
        ):

            df = earnings_dates.head(12)

            for idx, row in df.iterrows():

                idx_dt = pd.to_datetime(idx)

                est = safe_float(
                    row.get("EPS Estimate")
                )

                act = safe_float(
                    row.get("Reported EPS")
                )

                beat_val = None

                if (
                    est is not None
                    and act is not None
                ):

                    beat_val = round(
                        act - est,
                        2
                    )

                revenue = safe_float(
                    row.get(
                        "Reported Revenue"
                    )
                )

                if revenue is None:

                    revenue = get_closest_revenue(
                        idx_dt,
                        q_income
                    )

                earnings_history_table.append({

                    "date":
                        str(idx_dt.date()),

                    "quarter":
                        get_quarter_label(idx_dt),

                    "consensus_eps":
                        est,

                    "reported_eps":
                        act,

                    "beat":
                        beat_val,

                    "beat_direction":
                        (
                            "beat"
                            if beat_val is not None and beat_val >= 0
                            else "miss"
                        ),

                    "surprise_percent":
                        safe_float(
                            row.get(
                                "Surprise(%)"
                            )
                        ),

                    "actual_revenue":
                        format_cr(revenue),

                    "actual_revenue_display":
                        format_currency_cr(
                            revenue
                        )
                })

        # ---------------------------------------------------
        # ANALYST ESTIMATES
        # ---------------------------------------------------

        analyst_estimates_table = []

        earnings_forecasts = None

        try:

            if hasattr(
                ticker,
                "earnings_estimate"
            ):

                earnings_forecasts = (
                    ticker.earnings_estimate
                )

            elif hasattr(
                ticker,
                "earnings_forecasts"
            ):

                earnings_forecasts = (
                    ticker.earnings_forecasts
                )

        except:
            pass

        if (
            earnings_forecasts is not None
            and not earnings_forecasts.empty
        ):

            for idx, row in earnings_forecasts.iterrows():

                def get_field(r, keys):

                    for k in keys:

                        if k in r:
                            return safe_float(
                                r.get(k)
                            )

                    return None

                num_analysts = get_field(
                    row,
                    [
                        "No. of Analysts",
                        "numberOfAnalysts",
                        "No. of analysts"
                    ]
                )

                analyst_estimates_table.append({

                    "quarter":
                        map_analyst_quarter_label(
                            idx
                        ),

                    "low_eps":
                        get_field(
                            row,
                            [
                                "Low Estimate",
                                "low"
                            ]
                        ),

                    "high_eps":
                        get_field(
                            row,
                            [
                                "High Estimate",
                                "high"
                            ]
                        ),

                    "avg_eps":
                        get_field(
                            row,
                            [
                                "Avg Estimate",
                                "avg"
                            ]
                        ),

                    "num_analysts":
                        int(num_analysts)
                        if num_analysts is not None
                        else None
                })

        # ---------------------------------------------------
        # RESOURCES
        # ---------------------------------------------------

        resources = [
            {
                "type": "report",
                "label": "Quarterly Report",
                "url": None
            },
            {
                "type": "transcript",
                "label": "Conference Call",
                "url": None
            },
            {
                "type": "press",
                "label": "Press Release",
                "url": None
            },
            {
                "type": "filing",
                "label": "Exchange Filing",
                "url": None
            }
        ]

        # ---------------------------------------------------
        # FINAL RESPONSE
        # ---------------------------------------------------

        return jsonify({

            "success": True,

            "summary":
                summary,

            "resources":
                resources,

            "eps_estimate_vs_actual_chart":
                eps_chart,

            "revenue_chart":
                revenue_chart,

            "earnings_history_table":
                earnings_history_table,

            "analyst_estimates_table":
                analyst_estimates_table
        })

    except Exception as e:

        import traceback

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
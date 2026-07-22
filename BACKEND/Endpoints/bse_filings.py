import os
from flask import Blueprint, request, jsonify, Response, redirect as flask_redirect
from flask_cors import cross_origin
import requests, re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed


bse_filings_bp = Blueprint("bse_filings_bp", __name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BSE_BASE    = "https://api.bseindia.com/BseIndiaAPI/api"
BSE_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.bseindia.com/",
    "Origin":          "https://www.bseindia.com",
}

BSE_RESULT_CAT = "Result"

# BSE PDF URL patterns (tried in order — Live first, then archive paths)
BSE_PDF_PATTERNS = [
    "https://www.bseindia.com/xml-data/corpfiling/AttachLive/{attach}",
    "https://www.bseindia.com/xml-data/corpfiling/AttachHis/{attach}",
    "https://www.bseindia.com/xml-data/corpfiling/Attachhis/{attach}",
]

# Hand-rolled map for symbols whose BSE scrip code is well-known
BSE_SCRIP_MAP: dict[str, str] = {
    "TCS":        "532540",
    "INFY":       "500209",
    "RELIANCE":   "500325",
    "HDFCBANK":   "500180",
    "ICICIBANK":  "532174",
    "WIPRO":      "507685",
    "HINDUNILVR": "500696",
    "ITC":        "500875",
    "SBIN":       "500112",
    "AXISBANK":   "532215",
    "KOTAKBANK":  "500247",
    "BAJFINANCE": "500034",
    "TATAMOTORS": "500570",
    "MARUTI":     "532500",
    "SUNPHARMA":  "524715",
    "TITAN":      "500114",
    "NESTLEIND":  "500790",
    "TECHM":      "532755",
    "HCLTECH":    "532281",
    "LTIM":       "540005",
    "ADANIPORTS": "532921",
    "POWERGRID":  "532898",
    "NTPC":       "532555",
    "ONGC":       "500312",
    "COALINDIA":  "533278",
    "ULTRACEMCO": "532538",
    "ASIANPAINT": "500820",
    "BAJAJFINSV": "532978",
    "DIVISLAB":   "532488",
    "DRREDDY":    "500124",
    "EICHERMOT":  "505200",
    "GRASIM":     "500300",
    "APOLLOHOSP": "508869",
    "CIPLA":      "500087",
    "BRITANNIA":  "500825",
    "HEROMOTOCO": "500182",
    "M&M":        "500520",
    "TATACONSUM": "500800",
    "JSWSTEEL":   "500228",
    "HINDALCO":   "500440",
}


def load_company_list(csv_path: str = None) -> dict:
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), "stock_list.csv")
    companies = {}
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            import csv
            reader = csv.DictReader(f)
            for row in reader:
                sym = (row.get("SYMBOL") or "").strip().upper()
                if sym:
                    companies[sym] = {
                        "name":     (row.get("NAME OF COMPANY") or "").strip(),
                        "sector":   (row.get("SECTOR") or "").strip(),
                        "industry": (row.get("INDUSTRY") or "").strip(),
                    }
    except FileNotFoundError:
        pass
    return companies


COMPANY_LIST = load_company_list()

# ---------------------------------------------------------------------------
# Category mapping — normalises BSE's raw subcategory strings
# ---------------------------------------------------------------------------

_CATEGORY_MAP: list[tuple[list[str], str]] = [
    (["financial result", "quarterly result", "half year", "annual result",
      "standalone result", "consolidated result", "unaudited result",
      "audited result", "board meeting", "outcome of board"], "Results"),
    (["dividend", "interim dividend", "final dividend"], "Dividend"),
    (["agm", "annual general", "postal ballot", "egm",
      "extraordinary general"], "AGM"),
    (["insider", "trading window", "insider trading"], "Insider"),
    (["acquisition", "merger", "amalgamation", "takeover", "buyback",
      "open offer"], "Acquisition"),
    (["press release", "media release", "media statement"], "Press Release"),
    (["analyst", "investor meet", "investor presentation"], "Analyst / Investor Meet"),
    (["compliance", "reg 33", "reg 34", "sebi", "listing obligation",
      "lodr"], "Compliance"),
]


def map_category(raw: str) -> str:
    low = raw.lower()
    for keywords, label in _CATEGORY_MAP:
        if any(kw in low for kw in keywords):
            return label
    return "General"


# ---------------------------------------------------------------------------
# Quarterly result detection
# ---------------------------------------------------------------------------

_RESULT_SUBCATEGORY_WHITELIST = [
    "financial results",
    "quarterly results",
    "quarterly financial results",
    "half yearly results",
    "half yearly financial results",
    "annual results",
    "annual result",
    "standalone result",
    "consolidated result",
    "outcome of board meeting",
]

_HARD_EXCLUDE_CATEGORIES = [
    "investor presentation",
    "press release",
    "media release",
    "analyst / investor meet",
    "analyst/investor meet",
    "earnings call transcript",
    "agm",
    "postal ballot",
    "closure of trading window",
]

_HARD_EXCLUDE_HEADLINES = [
    "press release",
    "newspaper",
    "transcript",
    "concall",
    "audio recording",
    "media release",
    "media statement",
]


def is_quarterly_result(raw_category: str, headline: str) -> bool:
    h = headline.lower().strip()
    sub = raw_category.lower().strip()

    # Step 1 — exclude by CATEGORY first (most reliable, BSE's own taxonomy)
    if any(kw in sub for kw in _HARD_EXCLUDE_CATEGORIES):
        return False

    # Step 2 — exclude by headline
    if any(kw in h for kw in _HARD_EXCLUDE_HEADLINES):
        return False

    # Step 3 — accept only if it's actually the results document
    if any(wl in sub for wl in _RESULT_SUBCATEGORY_WHITELIST):
        return True

    return False


# ---------------------------------------------------------------------------
# Quarter detection  (Q1 = Apr-Jun, Q2 = Jul-Sep, Q3 = Oct-Dec, Q4 = Jan-Mar)
# ---------------------------------------------------------------------------

_QTR_PATTERNS = [
    (re.compile(r"\bQ([1-4])\b",                        re.I), lambda m: f"Q{m.group(1)}"),
    (re.compile(r"\b(first|1st)\s+quarter\b",           re.I), lambda m: "Q1"),
    (re.compile(r"\b(second|2nd)\s+quarter\b",          re.I), lambda m: "Q2"),
    (re.compile(r"\b(third|3rd)\s+quarter\b",           re.I), lambda m: "Q3"),
    (re.compile(r"\b(fourth|4th|last)\s+quarter\b",     re.I), lambda m: "Q4"),
    (re.compile(r"\b(apr|may|jun)\b",                   re.I), lambda m: "Q1"),
    (re.compile(r"\b(jul|aug|sep)\b",                   re.I), lambda m: "Q2"),
    (re.compile(r"\b(oct|nov|dec)\b",                   re.I), lambda m: "Q3"),
    (re.compile(r"\b(jan|feb|mar)\b",                   re.I), lambda m: "Q4"),
]

_MONTH_QTR = {
    1: "Q4", 2: "Q4", 3: "Q4",
    4: "Q1", 5: "Q1", 6: "Q1",
    7: "Q2", 8: "Q2", 9: "Q2",
    10: "Q3", 11: "Q3", 12: "Q3",
}


def detect_quarter(headline: str, date_str: str) -> str | None:
    text = headline or ""
    for pat, fn in _QTR_PATTERNS:
        m = pat.search(text)
        if m:
            return fn(m)
    # fallback: derive from filing date
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(date_str[:len(fmt)], fmt)
            return _MONTH_QTR.get(dt.month)
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_pdf_url(attach: str) -> str | None:
    if not attach:
        return None
    return f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{attach}"


def get_bse_scrip(symbol: str) -> str | None:
    symbol = symbol.upper().strip()
    if symbol.isdigit():
        return symbol
    if symbol in BSE_SCRIP_MAP:
        return BSE_SCRIP_MAP[symbol]
    try:
        resp = requests.get(
            f"{BSE_BASE}/fetchCompanyNameForSymbol/w?Type=E&Scode={symbol}",
            headers=BSE_HEADERS, timeout=6,
        )
        table = resp.json().get("Table", [])
        if table:
            return str(table[0].get("SECURITY_CODE", ""))
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bse_filings_bp.route("/bse-filings/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def bse_filings(symbol):
    """
    Query params:
        from_date     YYYY-MM-DD  (default: 1 year ago)
        to_date       YYYY-MM-DD  (default: today)
        category      display-name filter, e.g. "Board", "Dividend"
        results_only  true | false  — genuine Q1-Q4 PDFs only
        limit         integer (optional)
    """
    today    = datetime.now()
    year_ago = today - timedelta(days=365)

    from_date_str   = request.args.get("from_date", year_ago.strftime("%Y-%m-%d"))
    to_date_str     = request.args.get("to_date",   today.strftime("%Y-%m-%d"))
    category_filter = request.args.get("category",  "").strip()
    results_only    = request.args.get("results_only", "false").lower() == "true"

    limit = request.args.get("limit")
    if limit:
        try:
            limit = int(limit)
        except ValueError:
            return jsonify({"error": "limit must be an integer"}), 400
    else:
        limit = None

    try:
        from_dt = datetime.strptime(from_date_str, "%Y-%m-%d")
        to_dt   = datetime.strptime(to_date_str,   "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    scrip_code = get_bse_scrip(symbol)
    if not scrip_code:
        return jsonify({
            "error": f"Unknown symbol '{symbol}'. Add it to BSE_SCRIP_MAP or stock_list.csv."
        }), 404

    company_info = COMPANY_LIST.get(symbol.upper(), {})

    str_cat = BSE_RESULT_CAT if results_only else "-1"

    # Split into 90-day chunks to avoid BSE pagination limits
    chunks = []
    chunk_start = from_dt
    while chunk_start <= to_dt:
        chunk_end = min(chunk_start + timedelta(days=90), to_dt)
        chunks.append((chunk_start, chunk_end))
        chunk_start = chunk_end + timedelta(days=1)

    def fetch_chunk(c_start, c_end):
        url = (
            f"{BSE_BASE}/AnnSubCategoryGetData/w"
            f"?strCat={str_cat}"
            f"&strPrevDate={c_start.strftime('%Y%m%d')}"
            f"&strScrip={scrip_code}"
            f"&strSearch=P"
            f"&strToDate={c_end.strftime('%Y%m%d')}"
            f"&strType=C"
            f"&subcategory=-1"
        )
        try:
            resp = requests.get(url, headers=BSE_HEADERS, timeout=12)
            resp.raise_for_status()
            return resp.json().get("Table") or []
        except Exception:
            return []

    all_rows = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(fetch_chunk, s, e) for s, e in chunks]
        for future in as_completed(futures, timeout=30):
            try:
                all_rows.extend(future.result())
            except Exception:
                pass

    filings = []

    for item in all_rows:
        raw_category = item.get("SUBCATNAME") or item.get("CATEGORYNAME") or ""
        headline     = item.get("HEADLINE") or item.get("NEWSSUB") or "BSE Announcement"
        mapped_cat   = map_category(raw_category)

        # results_only: strict quarterly filter
        if results_only and not is_quarterly_result(raw_category, headline):
            continue

        # Category display-name filter (client-side after fetching)
        if category_filter and mapped_cat.lower() != category_filter.lower():
            continue

        date_raw     = item.get("DissemDT") or item.get("News_submission_dt") or ""
        attach       = (item.get("ATTACHMENTNAME") or "").strip()
        pdf_url_val  = build_pdf_url(attach)
        # Route must match the registered /stock-bse-filings/<symbol>/download
        download_url = (
            f"/stock-bse-filings/{symbol.upper()}/download?file={attach}"
            if attach else None
        )

        is_result = is_quarterly_result(raw_category, headline)
        quarter   = detect_quarter(headline, date_raw) if is_result else None

        filings.append({
            "date":         date_raw,
            "filer":        item.get("SLONGNAME") or company_info.get("name") or symbol.upper(),
            "scrip_code":   scrip_code,
            "category":     mapped_cat,
            "category_raw": raw_category,
            "description":  headline,
            "pdf_url":      pdf_url_val,
            "download_url": download_url,
            "is_result":    is_result,
            "quarter":      quarter,
        })

    # Sort newest first
    filings.sort(key=lambda x: x["date"], reverse=True)

    if limit:
        filings = filings[:limit]

    return jsonify({
        "symbol":       symbol.upper(),
        "name":         company_info.get("name", ""),
        "sector":       company_info.get("sector", ""),
        "from_date":    from_date_str,
        "to_date":      to_date_str,
        "results_only": results_only,
        "count":        len(filings),
        "filings":      filings,
    })


@bse_filings_bp.route("/bse-filings/<symbol>/download", methods=["GET"])
@cross_origin(supports_credentials=True)
def download_filing_pdf(symbol):
    attach  = request.args.get("file", "").strip()
    pdf_url = request.args.get("url",  "").strip()

    if not attach and not pdf_url:
        return jsonify({"error": "Missing 'file' or 'url' query parameter"}), 400

    allowed = ("bseindia.com", "nseindia.com")

    if attach:
        candidates = [p.format(attach=attach) for p in BSE_PDF_PATTERNS]
    else:
        if not any(d in pdf_url for d in allowed):
            return jsonify({"error": "Only BSE/NSE URLs are permitted"}), 403
        candidates = [pdf_url]
        # Also try archive paths for older filings
        if "AttachLive" in pdf_url:
            fn = pdf_url.split("/")[-1]
            candidates.append(f"https://www.bseindia.com/xml-data/corpfiling/AttachHis/{fn}")
            candidates.append(f"https://www.bseindia.com/xml-data/corpfiling/Attachhis/{fn}")

    last_error = None

    for url in candidates:
        if not any(d in url for d in allowed):
            continue
        try:
            r = requests.get(url, headers=BSE_HEADERS, timeout=20, stream=True)

            if r.status_code == 404:
                last_error = f"404 at {url}"
                continue

            r.raise_for_status()

            content_type = r.headers.get("Content-Type", "")
            if "pdf" not in content_type.lower():
                last_error = f"Non-PDF content '{content_type}' at {url}"
                continue

            filename = url.split("/")[-1] or "filing.pdf"
            if not filename.lower().endswith(".pdf"):
                filename += ".pdf"

            # disposition=attachment → save-as download; default → inline view
            disposition_mode = request.args.get("disposition", "inline")
            content_disp = (
                f'attachment; filename="{filename}"'
                if disposition_mode == "attachment"
                else f'inline; filename="{filename}"'
            )

            origin = request.headers.get("Origin", "")
            resp_headers = {
                "Content-Type":                     "application/pdf",
                "Content-Disposition":              content_disp,
                "Cache-Control":                    "no-cache",
                "Access-Control-Allow-Origin":      origin or "*",
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Expose-Headers":    "Content-Disposition",
            }

            return Response(
                r.iter_content(chunk_size=8192),
                status=200,
                headers=resp_headers,
            )

        except requests.exceptions.RequestException as e:
            last_error = str(e)
            continue

    if attach:
        return flask_redirect(
            f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{attach}",
            code=302,
        )

    return Response(
        f"PDF not available. BSE error: {last_error}",
        status=404,
        mimetype="text/plain",
    )


@bse_filings_bp.route("/bse-company/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def bse_company(symbol):
    symbol     = symbol.upper().strip()
    scrip_code = get_bse_scrip(symbol)
    if not scrip_code:
        return jsonify({"error": f"Unknown symbol: {symbol}"}), 404

    info   = COMPANY_LIST.get(symbol, {})
    result = {
        "symbol":     symbol,
        "scrip_code": scrip_code,
        "name":       info.get("name", ""),
        "sector":     info.get("sector", ""),
        "industry":   info.get("industry", ""),
        "isin":       "",
    }

    try:
        resp = requests.get(
            f"{BSE_BASE}/CompanyReach/w?scripcode={scrip_code}",
            headers=BSE_HEADERS, timeout=6,
        )
        row = (resp.json().get("Table") or [{}])[0]
        result["isin"] = row.get("ISIN_CODE", "")
        if not result["name"]:
            result["name"] = row.get("LONGNAME", "")
    except Exception:
        pass

    return jsonify(result)
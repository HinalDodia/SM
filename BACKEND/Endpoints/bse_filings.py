import os, csv, time
from flask import Blueprint, request, jsonify, Response, g, redirect as flask_redirect
from flask_cors import cross_origin
import requests, re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed


bse_filings_bp = Blueprint("bse_filings_bp", __name__)


BSE_BASE = "https://api.bseindia.com/BseIndiaAPI/api"
 
BSE_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
    "Referer":         "https://www.bseindia.com/",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}
 
# ---------------------------------------------------------------------------
# PDF URL patterns — tried in order for every download
# ---------------------------------------------------------------------------
 
BSE_PDF_PATTERNS = [
    "https://www.bseindia.com/xml-data/corpfiling/AttachLive/{attach}",
    "https://www.bseindia.com/xml-data/corpfiling/AttachHis/{attach}",
    "https://www.bseindia.com/xml-data/corpfiling/Attachhis/{attach}",
]
 
# BSE's EXACT strCat string for financial results (singular, not "Results")
BSE_RESULT_CAT = "Result"
 
# ---------------------------------------------------------------------------
# Company list loader
# ---------------------------------------------------------------------------
 
def load_company_list(csv_path: str = None) -> dict:
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), "..", "invest", "stock_list.csv")
    companies = {}
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                symbol = row.get("SYMBOL", "").strip().upper()
                if not symbol:
                    continue
                industry = row.get("INDUSTRY", "").strip()
                if industry == "#FIELD!":
                    industry = ""
                companies[symbol] = {
                    "name":     row.get("NAME OF COMPANY", "").strip(),
                    "sector":   row.get("SECTOR", "").strip(),
                    "industry": industry,
                    "bse_code": None,
                }
    except FileNotFoundError:
        pass
    return companies
 
 
# ---------------------------------------------------------------------------
# NSE symbol → BSE scrip code map
# ---------------------------------------------------------------------------
 
BSE_SCRIP_MAP = {
    "RELIANCE":   "500325",
    "TCS":        "532540",
    "INFY":       "500209",
    "HDFCBANK":   "500180",
    "ICICIBANK":  "532174",
    "SBIN":       "500112",
    "AXISBANK":   "532215",
    "KOTAKBANK":  "500247",
    "BAJFINANCE": "500034",
    "BAJAJFINSV": "532978",
    "LT":         "500510",
    "ITC":        "500875",
    "HINDUNILVR": "500696",
    "NESTLEIND":  "500790",
    "BRITANNIA":  "500825",
    "TITAN":      "500114",
    "MARUTI":     "532500",
    "EICHERMOT":  "505200",
    "HEROMOTOCO": "500182",
    "TATASTEEL":  "500470",
    "JSWSTEEL":   "500228",
    "ULTRACEMCO": "532538",
    "POWERGRID":  "532898",
    "NTPC":       "532555",
    "ONGC":       "500312",
    "SUNPHARMA":  "524715",
    "DRREDDY":    "500124",
    "CIPLA":      "500087",
    "DIVISLAB":   "532488",
    "APOLLOHOSP": "508869",
    "HCLTECH":    "532281",
    "TECHM":      "532755",
    "WIPRO":      "507685",
    "ADANIENT":   "512599",
    "ADANIPORTS": "532921",
    "COALINDIA":  "533278",
    "INDUSINDBK": "532187",
    "PIDILITIND": "500331",
    "ASIANPAINT": "500820",
    "GRASIM":     "500300",
}
 
# Load once at startup and attach BSE codes
COMPANY_LIST = load_company_list()
for _sym, _code in BSE_SCRIP_MAP.items():
    if _sym in COMPANY_LIST:
        COMPANY_LIST[_sym]["bse_code"] = _code
 
 
# ---------------------------------------------------------------------------
# Category mapping
# ---------------------------------------------------------------------------
 
CATEGORY_MAP = {
    "financial result":              "Results",
    "result":                        "Results",
    "quarterly result":              "Results",
    "earnings call transcript":      "Results",
    "board meeting":                 "Board",
    "outcome of board":              "Board",
    "board":                         "Board",
    "dividend":                      "Dividend",
    "date of payment of dividend":   "Dividend",
    "record date":                   "Dividend",
    "agm":                           "AGM",
    "egm":                           "AGM",
    "annual general meeting":        "AGM",
    "extraordinary general":         "AGM",
    "insider":                       "Insider",
    "sast":                          "Insider",
    "shareholding":                  "Insider",
    "beneficial ownership":          "Insider",
    "trading window":                "Insider",
    "pit regulation":                "Insider",
    "acquisition":                   "Acquisition",
    "merger":                        "Acquisition",
    "buyback":                       "Acquisition",
    "incorporation":                 "Acquisition",
    "subsidiary":                    "Acquisition",
    "amalgamation":                  "Acquisition",
    "press release":                 "Press Release",
    "media release":                 "Press Release",
    "analyst":                       "Analyst / Investor Meet",
    "investor meet":                 "Analyst / Investor Meet",
    "reg.24":                        "Compliance",
    "secretarial compliance":        "Compliance",
    "lodr":                          "Compliance",
    "regulation 30":                 "Compliance",
    "newspaper publication":         "Compliance",
    "newspaper":                     "Compliance",
}
 
 
def map_category(raw: str) -> str:
    if not raw:
        return "General"
    lower = raw.lower()
    for key, val in CATEGORY_MAP.items():
        if key in lower:
            return val
    return raw.strip()[:40]
 
 
# ---------------------------------------------------------------------------
# Result filtering — whitelist approach
# ---------------------------------------------------------------------------
 
# Substrings of BSE's SUBCATNAME that confirm a genuine financial result
_RESULT_SUBCATEGORY_WHITELIST = [
    "financial result",
    "unaudited result",
    "audited result",
    "quarterly result",
    "half yearly result",
    "half-yearly result",
    "annual result",
    "standalone result",
    "consolidated result",
]
 
# Headline keywords that also confirm a result (fallback if subcategory is vague)
_CONFIRM_RESULT_KEYWORDS = [
    "financial result",
    "unaudited result",
    "audited result",
    "quarterly result",
    "half yearly result",
    "half-yearly result",
    "standalone result",
    "consolidated result",
    "results for the quarter",
    "results for the year",
    "results for the half",
]
 
# These headline keywords ALWAYS disqualify — even inside the Results category
_HARD_EXCLUDE_HEADLINES = [
    "press release",
    "newspaper",
    "investor presentation",
    "earnings call",
    "transcript",
    "concall",
    "audio recording",
]
 
 
def is_quarterly_result(raw_category: str, headline: str) -> bool:
    """
    Whitelist-first approach:
      1. Hard-exclude by headline (press releases, transcripts, etc.)
      2. Accept if SUBCATNAME contains a whitelist phrase
      3. Accept if headline contains a confirm keyword
      4. Reject everything else
    """
    h   = headline.lower().strip()
    sub = raw_category.lower().strip()
 
    # Step 1 — hard exclude
    if any(kw in h for kw in _HARD_EXCLUDE_HEADLINES):
        return False
 
    # Step 2 — whitelist subcategory
    if any(wl in sub for wl in _RESULT_SUBCATEGORY_WHITELIST):
        return True
 
    # Step 3 — headline confirm
    if any(kw in h for kw in _CONFIRM_RESULT_KEYWORDS):
        return True
 
    return False
 
 
def detect_quarter(headline: str, date_raw: str) -> str | None:
    """
    Detect Q1/Q2/Q3/Q4 from headline, fallback to filing month.
    Indian FY: Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar
    """
    h = headline.lower()
 
    if "q1" in h or "june" in h or "apr-jun" in h or "april-june" in h or "first quarter" in h:
        return "Q1"
    if "q2" in h or "september" in h or "jul-sep" in h or "july-september" in h or "second quarter" in h:
        return "Q2"
    if "q3" in h or "december" in h or "oct-dec" in h or "october-december" in h or "third quarter" in h:
        return "Q3"
    if "q4" in h or "march" in h or "jan-mar" in h or "january-march" in h or "fourth quarter" in h:
        return "Q4"
    if "annual" in h or "full year" in h or "full-year" in h:
        return "Q4"
 
    # Fallback by filing month
    if date_raw:
        try:
            month = int(date_raw[5:7]) if "-" in date_raw else int(date_raw[4:6])
            if month in (7, 8):   return "Q1"
            if month in (10, 11): return "Q2"
            if month in (1, 2):   return "Q3"
            if month in (4, 5):   return "Q4"
        except (ValueError, IndexError):
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
 
@bse_filings_bp.route("/companies", methods=["GET"])
@cross_origin(supports_credentials=True)
def list_companies():
    if not COMPANY_LIST:
        return jsonify({"error": "stock_list.csv not found in backend folder"}), 500
 
    companies = [
        {
            "symbol":   sym,
            "name":     info["name"],
            "sector":   info["sector"],
            "industry": info["industry"],
            "bse_code": info["bse_code"],
        }
        for sym, info in sorted(COMPANY_LIST.items(), key=lambda x: x[1]["name"])
    ]
    return jsonify({"count": len(companies), "companies": companies})
 
 
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
 
    # ------------------------------------------------------------------
    # strCat for BSE API:
    #   results_only=true  →  "Result"  (BSE's exact singular string)
    #   everything else    →  "-1"      (all categories)
    #
    # IMPORTANT: Do NOT pass our display category names (e.g. "Board") as
    # strCat — BSE uses different internal strings. We filter by mapped
    # category client-side after fetching.
    # ------------------------------------------------------------------
    str_cat = BSE_RESULT_CAT if results_only else "-1"
 
    # Split into 90-day chunks
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
 
    # Concurrent fetch
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
 
        # results_only: whitelist filter
        if results_only and not is_quarterly_result(raw_category, headline):
            continue
 
        # Optional display-name category filter
        if category_filter and mapped_cat.lower() != category_filter.lower():
            continue
 
        date_raw     = item.get("DissemDT") or item.get("News_submission_dt") or ""
        attach       = (item.get("ATTACHMENTNAME") or "").strip()
        pdf_url_val  = build_pdf_url(attach)
        download_url = (
            f"/bse-filings/{symbol.upper()}/download?file={attach}"
            if attach else None
        )
 
        is_result = is_quarterly_result(raw_category, headline)
        quarter   = detect_quarter(headline, date_raw) if is_result else None
 
        filings.append({
            "date":         date_raw,
            "filer":        item.get("SLONGNAME") or company_info.get("name") or symbol.upper(),
            "scrip_code":   scrip_code,
            "symbol":       symbol.upper(),
            "category":     mapped_cat,
            "category_raw": raw_category,
            "description":  headline,
            "quarter":      quarter,
            "pdf_url":      pdf_url_val,
            "download_url": download_url,
            "has_pdf":      bool(attach),
        })
 
    filings.sort(key=lambda x: (x["date"] or "", x["description"] or "", x["pdf_url"] or ""), reverse=True)
 
    if limit:
        filings = filings[:limit]
 
    return jsonify({
        "symbol":       symbol.upper(),
        "name":         company_info.get("name", ""),
        "sector":       company_info.get("sector", ""),
        "industry":     company_info.get("industry", ""),
        "scrip_code":   scrip_code,
        "from_date":    from_date_str,
        "to_date":      to_date_str,
        "category":     category_filter or "all",
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
 
        if "AttachHist" in pdf_url:
            candidates.append(pdf_url.replace("AttachHist", "AttachHis"))
            candidates.append(pdf_url.replace("AttachHist", "Attachhis"))
        elif "AttachLive" in pdf_url:
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
 
            return Response(
                r.iter_content(chunk_size=8192),
                status=200,
                headers={
                    "Content-Type":        "application/pdf",
                    "Content-Disposition": f'inline; filename="{filename}"',
                    "Cache-Control":       "no-cache",
                },
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
 
 
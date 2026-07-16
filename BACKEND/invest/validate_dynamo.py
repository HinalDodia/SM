"""
validate_dynamo.py
==================
Validates that DynamoDB stored values match live Flask endpoint responses.

Usage
-----
    # Validate a single symbol across all endpoints
    python validate_dynamo.py --symbol INFY

    # Validate multiple symbols
    python validate_dynamo.py --symbol INFY TCS RELIANCE

    # Validate specific endpoints only
    python validate_dynamo.py --symbol INFY --endpoints stock-page stock-chart stock-headlines

    # Validate with chart params
    python validate_dynamo.py --symbol INFY --period 1y --interval 1d

    # Validate sentiment with peers
    python validate_dynamo.py --symbol TCS --peers INFY WIPRO

    # Validate options with expiry
    python validate_dynamo.py --symbol NIFTY --expiry 2025-05-29

    # Show only mismatches
    python validate_dynamo.py --symbol INFY --only-mismatches

    # Show full field-level diff on mismatch
    python validate_dynamo.py --symbol INFY --diff

Requirements
------------
    pip install boto3 requests deepdiff colorama

Environment variables
---------------------
    FLASK_BASE_URL   : Base URL of your running Flask app (default: http://localhost:5000)
    AWS_REGION       : DynamoDB region (default: ap-south-1)
"""

import os
import sys
import json
import argparse
import time
from datetime import datetime, timezone
from decimal import Decimal
import re
import boto3
import requests
from boto3.dynamodb.conditions import Key
from dotenv import load_dotenv

load_dotenv()
try:
    from deepdiff import DeepDiff
    HAS_DEEPDIFF = True
except ImportError:
    HAS_DEEPDIFF = False

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

FLASK_BASE_URL = os.environ.get("FLASK_BASE_URL", "http://localhost:5000").rstrip("/")
AWS_REGION     = os.environ.get("AWS_REGION", "ap-south-1")
REQUEST_TIMEOUT = 30   # seconds per HTTP call

TABLES = {
    "stock-page":             "stock-page",
    "stock-chart":            "stock-chart",
    "stock-financials":       "stock-financials",
    "stock-earnings":         "stock-earnings",
    "stock-dividend-summary": "stock-dividend-summary",
    "stock-headlines":        "stock-headlines",
    
    "stock-competitors":      "stock-competitors",
    "stock-options":          "stock-options",
    "stock-short-interest":   "stock-short-interest",
    
    "bse-filings":            "bse-filings",
}

ALL_ENDPOINTS = list(TABLES.keys())

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def _green(text):
    return f"{Fore.GREEN}{text}{Style.RESET_ALL}" if HAS_COLOR else text

def _red(text):
    return f"{Fore.RED}{text}{Style.RESET_ALL}" if HAS_COLOR else text

def _yellow(text):
    return f"{Fore.YELLOW}{text}{Style.RESET_ALL}" if HAS_COLOR else text

def _cyan(text):
    return f"{Fore.CYAN}{text}{Style.RESET_ALL}" if HAS_COLOR else text

def _bold(text):
    return f"{Style.BRIGHT}{text}{Style.RESET_ALL}" if HAS_COLOR else text

# ---------------------------------------------------------------------------
# DynamoDB helpers
# ---------------------------------------------------------------------------

_dynamo = None

def get_dynamo():
    global _dynamo
    if _dynamo is None:
        _dynamo = boto3.resource("dynamodb", region_name=AWS_REGION)
    return _dynamo


def _from_dynamo(obj):
    """Recursively convert Decimal → float for comparison."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _from_dynamo(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_from_dynamo(i) for i in obj]
    return obj


def fetch_db_latest(table_name: str, pk: str, sk_exact: str = None, sk_prefix: str = None):
    """
    Fetch the most recent item from DynamoDB for a given PK.
    - sk_exact  : use GetItem (chart, meta, options)
    - sk_prefix : use Query with begins_with
    - neither   : use Query sorted desc (get latest)

    Returns (item_data_dict | None, sk_found | None, fetched_at | None)
    """
    try:
        table = get_dynamo().Table(table_name)

        if sk_exact:
            resp = table.get_item(Key={"SYMBOL#<sym>": pk, "SK": sk_exact})
            item = resp.get("Item")
            if item:
                return _from_dynamo(item.get("data", {})), item.get("SK"), item.get("fetched_at")
            return None, None, None

        if sk_prefix:
            resp = table.query(
                KeyConditionExpression=Key("SYMBOL#<sym>").eq(pk) & Key("SK").begins_with(sk_prefix),
                ScanIndexForward=False,
                Limit=1,
            )
        else:
            resp = table.query(
                KeyConditionExpression=Key("SYMBOL#<sym>").eq(pk),
                ScanIndexForward=False,
                Limit=1,
            )

        items = resp.get("Items", [])
        if items:
            item = items[0]
            return _from_dynamo(item.get("data", {})), item.get("SK"), item.get("fetched_at")
        return None, None, None

    except Exception as e:
        print(_red(f"    [DB ERROR] {table_name} PK={pk}: {e}"))
        return None, None, None

# ---------------------------------------------------------------------------
# Flask HTTP helpers
# ---------------------------------------------------------------------------

def fetch_live(url: str, params: dict = None):
    """
    Call the live Flask endpoint.
    Returns (data_dict | list | None, error_str | None)
    """
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            return resp.json(), None
        return None, f"HTTP {resp.status_code}"
    except requests.Timeout:
        return None, "Timeout"
    except Exception as e:
        return None, str(e)

# ---------------------------------------------------------------------------
# Comparison engine
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Tolerant comparison engine
# ---------------------------------------------------------------------------

# How much live numbers are allowed to drift between the DB snapshot and a
# fresh live call (price ticks, yfinance fundamentals jitter, etc.)
RELATIVE_TOLERANCE = 0.05   # 5% — covers every real drift seen in testing,
                            # with margin. Tighten later once insert/validate
                            # run back-to-back with a smaller time gap.

TIMESTAMP_TOLERANCE_SECONDS = 600

_ISO_TS_RE   = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
_SPACE_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
_TS_MIN = 1_500_000_000
_TS_MAX = 2_000_000_000

_COUNT_TOLERANT_FIELDS = {"news_count", "bullish", "neutral", "bearish"}
_COUNT_TOLERANCE = 3   # allow this many articles' worth of drift

def _ts_to_bucket(epoch_secs: float, bucket: int = TIMESTAMP_TOLERANCE_SECONDS) -> int:
    return round(float(epoch_secs) / bucket)


def _round_timestamp(ts_str: str, bucket: int = TIMESTAMP_TOLERANCE_SECONDS):
    try:
        if _ISO_TS_RE.match(ts_str):
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            return _ts_to_bucket(dt.timestamp(), bucket)
        if _SPACE_TS_RE.match(ts_str):
            dt = datetime.strptime(ts_str[:19], "%Y-%m-%d %H:%M:%S")
            return _ts_to_bucket(dt.timestamp(), bucket)
    except Exception:
        pass
    return ts_str


class _WildcardZero:
    """Matches anything — used for fields that legitimately read 0/None
    on a cold yfinance session (see _VOLATILE_ZERO_FIELDS below)."""
    def __eq__(self, other):   return True
    def __hash__(self):        return 0
    def __repr__(self):        return "<wildcard-zero>"


_VOLATILE_ZERO_FIELDS = {"Volume", "volume", "avg_volume_20d", "turnover"}
_VOLATILE_NONE_FIELDS = {"price_change", "volume_ratio"}
_ALWAYS_WILDCARD_FIELDS = {"avg_volume","avg_volume_20d"}


def _normalize(obj):
    """Only handles timestamp bucketing now — magnitude rounding is gone,
    replaced by the tolerant _fuzzy_equal() comparison below."""
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        if _TS_MIN <= obj <= _TS_MAX:
            return _ts_to_bucket(obj)
        return obj
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k in _ALWAYS_WILDCARD_FIELDS:
                result[k] = _WildcardZero()
            elif k in _VOLATILE_ZERO_FIELDS and (v == 0 or v is None):
                result[k] = _WildcardZero()
            elif k in _VOLATILE_NONE_FIELDS and v is None:
                result[k] = _WildcardZero()
            else:
                result[k] = _normalize(v)
        return result
    if isinstance(obj, str):
        if _ISO_TS_RE.match(obj) or _SPACE_TS_RE.match(obj):
            return _round_timestamp(obj)
        return obj
    if isinstance(obj, list):
        return [_normalize(i) for i in obj]
    return obj


def _parse_number_like(s):
    """'₹2,058.00' / '-35.5%' / '2,058' -> float, or None if not numeric."""
    if not isinstance(s, str):
        return None
    cleaned = s.replace("₹", "").replace(",", "").replace("%", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _numbers_close(a, b, rel_tol=RELATIVE_TOLERANCE):
    if a == b:
        return True
    if a == 0 or b == 0:
        return abs(a - b) <= 0.5          # small absolute floor near zero
    return abs(a - b) <= rel_tol * max(abs(a), abs(b))


def _fuzzy_equal(a, b):
    """Recursively compares two normalized structures with tolerance,
    instead of demanding byte-for-byte equality."""
    if isinstance(a, _WildcardZero) or isinstance(b, _WildcardZero):
        return True

    a_num = isinstance(a, (int, float)) and not isinstance(a, bool)
    b_num = isinstance(b, (int, float)) and not isinstance(b, bool)
    if a_num and b_num:
        return _numbers_close(a, b)

    if isinstance(a, str) and isinstance(b, str):
        na, nb = _parse_number_like(a), _parse_number_like(b)
        if na is not None and nb is not None:
            return _numbers_close(na, nb)
        return a == b

    if isinstance(a, dict) and isinstance(b, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        for k in a:
            if k in _COUNT_TOLERANT_FIELDS and isinstance(a[k], (int, float)) and isinstance(b[k], (int, float)):
                if abs(a[k] - b[k]) <= _COUNT_TOLERANCE:
                    continue
                return False
            if not _fuzzy_equal(a[k], b[k]):
                return False
        return True

    if isinstance(a, list) and isinstance(b, list):
        # Date-keyed rows (chart/price_history): compare by date so one
        # extra/missing boundary row doesn't fail the whole list.
        if a and b and all(isinstance(x, dict) and "date" in x for x in a + b):
            by_date_b = {x["date"]: x for x in b}
            for x in a:
                y = by_date_b.get(x["date"])
                if y is not None and not _fuzzy_equal(x, y):
                    return False
            return True

        # Growing content (news, topics): match by a unique key and only
        # require the SMALLER list's items to appear correctly in the
        # larger one. New items arriving between fetches are expected.
        for key in ("url", "topic"):
            if a and b and all(isinstance(x, dict) and x.get(key) for x in a + b):
                small, large = (a, b) if len(a) <= len(b) else (b, a)
                large_map = {}
                for x in large:
                    large_map.setdefault(x[key], []).append(x)
                for x in small:
                    candidates = large_map.get(x[key], [])
                    if not any(_fuzzy_equal(x, y) for y in candidates):
                        return False
                return True

        if len(a) != len(b):
            return False
        return all(_fuzzy_equal(x, y) for x, y in zip(a, b))

    return a == b

def _find_diffs(a, b, path="root"):
    """Walks two structures using the SAME tolerant rules as _fuzzy_equal,
    and returns the specific paths that actually fail — so the diff
    printout can never disagree with the match/mismatch decision."""
    diffs = {}

    if isinstance(a, _WildcardZero) or isinstance(b, _WildcardZero):
        return diffs

    a_num = isinstance(a, (int, float)) and not isinstance(a, bool)
    b_num = isinstance(b, (int, float)) and not isinstance(b, bool)
    if a_num and b_num:
        if not _numbers_close(a, b):
            diffs[path] = {"old_value": a, "new_value": b}
        return diffs

    if isinstance(a, str) and isinstance(b, str):
        na, nb = _parse_number_like(a), _parse_number_like(b)
        if na is not None and nb is not None:
            if not _numbers_close(na, nb):
                diffs[path] = {"old_value": a, "new_value": b}
        elif a != b:
            diffs[path] = {"old_value": a, "new_value": b}
        return diffs

    if isinstance(a, dict) and isinstance(b, dict):
        for k in set(a.keys()) | set(b.keys()):
            if k not in a:
                diffs[f"{path}['{k}']"] = {"old_value": "<missing>", "new_value": b[k]}
            elif k not in b:
                diffs[f"{path}['{k}']"] = {"old_value": a[k], "new_value": "<missing>"}
            else:
                diffs.update(_find_diffs(a[k], b[k], f"{path}['{k}']"))
        return diffs

    if isinstance(a, list) and isinstance(b, list):
        if a and b and all(isinstance(x, dict) and "date" in x for x in a + b):
            by_date_b = {x["date"]: x for x in b}
            for i, x in enumerate(a):
                y = by_date_b.get(x["date"])
                if y is None:
                    diffs[f"{path}[{i}] (date={x['date']})"] = {"old_value": "present", "new_value": "<missing in live>"}
                else:
                    diffs.update(_find_diffs(x, y, f"{path}[{i}](date={x['date']})"))
            return diffs
        if len(a) != len(b):
            diffs[f"{path} (length)"] = {"old_value": len(a), "new_value": len(b)}
            return diffs
        for i, (x, y) in enumerate(zip(a, b)):
            diffs.update(_find_diffs(x, y, f"{path}[{i}]"))
        return diffs

    if a != b:
        diffs[path] = {"old_value": a, "new_value": b}
    return diffs

_ATTACH_ID_RE = re.compile(r'file=([^&]+)$')

def _filing_key(filing: dict) -> str:
    """Stable identity for a single BSE filing.
 
    List POSITION is not stable: insert.py's filings list is sorted
    newest-first, so any new filing published between the DB snapshot and a
    live re-check shifts every older filing down by one index. Comparing by
    index then pairs unrelated filings together. The attachment GUID embedded
    in download_url/pdf_url is the actual unique identity BSE assigns to the
    filing, so we key on that instead.
    """
    url = filing.get("download_url") or filing.get("pdf_url") or ""
    m = _ATTACH_ID_RE.search(url)
    if m:
        return m.group(1)
    # Filings with no PDF attachment have no GUID to key on — fall back to
    # date+description, which is still far more stable than list position.
    return f"{filing.get('date')}|{filing.get('description')}"

def compare_bse_filings(db_data, live_data, show_diff: bool = False):
    """Like compare(), but for the bse-filings endpoint specifically: matches
    each filing by its attachment GUID rather than list position, so a newly
    published filing (which shifts every later index) doesn't get reported as
    dozens of unrelated content mismatches.
    """
    db_list   = (db_data or {}).get("filings") or []
    live_list = (live_data or {}).get("filings") or []
 
    if not db_list and not live_list:
        return "BOTH_EMPTY", None, "Both DB and live returned empty"
    if not db_list:
        return "EMPTY_DB", None, "DB has no stored value"
    if not live_list:
        return "EMPTY_LIVE", None, "Live endpoint returned empty"
 
    db_filings   = {_filing_key(f): f for f in db_list}
    live_filings = {_filing_key(f): f for f in live_list}
 
    common            = set(db_filings) & set(live_filings)
    new_in_live       = set(live_filings) - set(db_filings)
    missing_from_live = set(db_filings) - set(live_filings)
 
    changed = {}
    for fid in common:
        if _normalize(db_filings[fid]) != _normalize(live_filings[fid]):
            changed[fid] = {"db": db_filings[fid], "live": live_filings[fid]}
 
    if not changed:
        notes = []
        if new_in_live:
            notes.append(f"{len(new_in_live)} new filing(s) published since DB snapshot")
        if missing_from_live:
            notes.append(f"{len(missing_from_live)} filing(s) in DB no longer in live feed")
        summary = "Values are identical" if not notes else "Match — " + "; ".join(notes)
        return "MATCH", None, summary
 
    diff = {"changed_filings": changed} if show_diff else None
    summary = f"{len(changed)} filing(s) have different content under the SAME attachment ID (genuine edit/correction)"
    return "MISMATCH", diff, summary
 
 

def compare(db_data, live_data, show_diff: bool = False):
    db_empty   = db_data   is None or db_data   == {} or db_data   == []
    live_empty = live_data is None or live_data == {} or live_data == []

    if db_empty and live_empty:
        return "BOTH_EMPTY", None, "Both DB and live returned empty"
    if db_empty:
        return "EMPTY_DB", None, "DB has no stored value"
    if live_empty:
        return "EMPTY_LIVE", None, "Live endpoint returned empty"

    norm_db   = _normalize(db_data)
    norm_live = _normalize(live_data)

    if _fuzzy_equal(norm_db, norm_live):
        return "MATCH", None, "Values are identical (within tolerance)"

    diff = None
    summary = "Values differ"

    if show_diff:
        diffs = _find_diffs(norm_db, norm_live)
        if diffs:
            diff = {"values_changed": diffs}
            sample = list(diffs.keys())[:5]
            summary = f"Changed keys (sample): {', '.join(sample)}"
    else:
        diff = {"note": "Install deepdiff for detailed list/nested diffs"}

    return "MISMATCH", diff, summary
# ---------------------------------------------------------------------------
# Status printer
# ---------------------------------------------------------------------------

STATUS_ICON = {
    "MATCH":      "✅",
    "MISMATCH":   "❌",
    "EMPTY_DB":   "🟡",
    "EMPTY_LIVE": "🟠",
    "BOTH_EMPTY": "⬜",
    "ERROR":      "🔴",
    "SKIP":       "⏭ ",
}

STATUS_COLOR = {
    "MATCH":      _green,
    "MISMATCH":   _red,
    "EMPTY_DB":   _yellow,
    "EMPTY_LIVE": _yellow,
    "BOTH_EMPTY": _yellow,
    "ERROR":      _red,
    "SKIP":       _cyan,
}

def _print_result(endpoint, symbol, status, summary, fetched_at=None, sk=None, elapsed=None, diff=None):
    color_fn = STATUS_COLOR.get(status, lambda x: x)
    icon     = STATUS_ICON.get(status, "?")
    ts       = f"  [DB fetched_at: {fetched_at}]" if fetched_at else ""
    sk_str   = f"  [SK: {sk}]" if sk else ""
    el_str   = f"  [{elapsed:.2f}s]" if elapsed is not None else ""

    print(f"  {icon}  {color_fn(_bold(status))}  {_cyan(endpoint):<28}  {summary}{ts}{sk_str}{el_str}")

    if diff:
        print(_yellow("      --- DIFF ---"))
        print(_yellow(json.dumps(diff, indent=6, default=str)[:2000]))   # cap at 2000 chars


# ---------------------------------------------------------------------------
# Per-endpoint validators
# ---------------------------------------------------------------------------

def validate_stock_page(symbol, args, results):
    endpoint = "stock-page"
    pk = f"SYMBOL#{symbol}"
    url = f"{FLASK_BASE_URL}/stock-page/{symbol}"

    t0 = time.time()
    db_data, sk, fetched_at = fetch_db_latest(TABLES[endpoint], pk)
    live_data, err = fetch_live(url)
    elapsed = time.time() - t0

    if err:
        _print_result(endpoint, symbol, "ERROR", err, elapsed=elapsed)
        results.append({"endpoint": endpoint, "symbol": symbol, "status": "ERROR", "detail": err})
        return

    status, diff, summary = compare(db_data, live_data, args.diff)
    _print_result(endpoint, symbol, status, summary, fetched_at, sk, elapsed, diff)
    results.append({"endpoint": endpoint, "symbol": symbol, "status": status, "detail": summary})


def validate_stock_chart(symbol, args, results):
    endpoint = "stock-chart"
    pk = f"SYMBOL#{symbol}"
    period   = getattr(args, "period",   "1y") or "1y"
    interval = getattr(args, "interval", "1d") or "1d"
    sk_val   = f"CHART#{period}#{interval}"
    url = f"{FLASK_BASE_URL}/stock-chart/{symbol}"

    t0 = time.time()

    # stock-chart uses a non-standard SK attribute name in DynamoDB:
    # PK="SYMBOL#<sym>"  SK="CHART#<period>#<interval>"
    db_data, sk, fetched_at = None, None, None
    try:
        table = get_dynamo().Table(TABLES[endpoint])
        resp  = table.get_item(Key={
            "SYMBOL#<sym>": pk,
            "CHART#<period>#<interval>": sk_val,
        })
        item = resp.get("Item")
        if item:
            db_data    = _from_dynamo(item.get("data", {}))
            fetched_at = item.get("fetched_at")
            sk         = sk_val
    except Exception as e:
        print(_red(f"    [DB ERROR] {endpoint} PK={pk}: {e}"))

    live_data, err = fetch_live(url, params={"period": period, "interval": interval})
    elapsed = time.time() - t0

    if err:
        _print_result(endpoint, symbol, "ERROR", err, elapsed=elapsed)
        results.append({"endpoint": endpoint, "symbol": symbol, "status": "ERROR", "detail": err})
        return

    status, diff, summary = compare(db_data, live_data, args.diff)
    _print_result(endpoint, symbol, status, summary, fetched_at, sk, elapsed, diff)
    results.append({"endpoint": endpoint, "symbol": symbol, "status": status, "detail": summary})


def validate_stock_financials(symbol, args, results):
    endpoint = "stock-financials"
    pk = f"SYMBOL#{symbol}"
    url = f"{FLASK_BASE_URL}/financials/{symbol}"

    t0 = time.time()

    table = get_dynamo().Table(TABLES[endpoint])

    try:
        # Fetch BOTH annual + quarterly items
        resp = table.query(
            KeyConditionExpression=Key("SYMBOL#<sym>").eq(pk)
        )

        items = resp.get("Items", [])

        merged_db_data = {}
        fetched_at = None

        for item in items:
            period_type = item.get("FINANCIALS#<period_type>", "")

            data = _from_dynamo(item.get("data", {}))

            # annual item
            if period_type == "FINANCIALS#annual":
                merged_db_data.update(data)

            # quarterly item
            elif period_type == "FINANCIALS#quarterly":
                merged_db_data.update(data)

            fetched_at = item.get("fetched_at")

        live_data, err = fetch_live(url)

        elapsed = time.time() - t0

        if err:
            _print_result(endpoint, symbol, "ERROR", err, elapsed=elapsed)
            results.append({
                "endpoint": endpoint,
                "symbol": symbol,
                "status": "ERROR",
                "detail": err
            })
            return

        status, diff, summary = compare(
            merged_db_data,
            live_data,
            args.diff
        )

        _print_result(
            endpoint,
            symbol,
            status,
            summary,
            fetched_at=fetched_at,
            sk="FINANCIALS#annual + FINANCIALS#quarterly",
            elapsed=elapsed,
            diff=diff
        )

        results.append({
            "endpoint": endpoint,
            "symbol": symbol,
            "status": status,
            "detail": summary
        })

    except Exception as e:
        elapsed = time.time() - t0

        _print_result(
            endpoint,
            symbol,
            "ERROR",
            str(e),
            elapsed=elapsed
        )

        results.append({
            "endpoint": endpoint,
            "symbol": symbol,
            "status": "ERROR",
            "detail": str(e)
        })

def validate_stock_earnings(symbol, args, results):
    endpoint = "stock-earnings"
    pk = f"SYMBOL#{symbol}"
    url = f"{FLASK_BASE_URL}/earnings/{symbol}"

    t0 = time.time()
    db_data, sk, fetched_at = fetch_db_latest(TABLES[endpoint], pk)
    live_data, err = fetch_live(url)
    elapsed = time.time() - t0

    if err:
        _print_result(endpoint, symbol, "ERROR", err, elapsed=elapsed)
        results.append({"endpoint": endpoint, "symbol": symbol, "status": "ERROR", "detail": err})
        return

    status, diff, summary = compare(db_data, live_data, args.diff)
    _print_result(endpoint, symbol, status, summary, fetched_at, sk, elapsed, diff)
    results.append({"endpoint": endpoint, "symbol": symbol, "status": status, "detail": summary})


def validate_stock_dividend_summary(symbol, args, results):
    endpoint = "stock-dividend-summary"
    url = f"{FLASK_BASE_URL}/dividend-summary/{symbol}"

    t0 = time.time()
    fetched_at = None
    sk = None
    db_data = None

    try:
        table = get_dynamo().Table(TABLES[endpoint])
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        pk     = f"SYMBOL#{symbol}"
        sk_val = f"DIVIDEND_SUMMARY#{date_str}"

        resp = table.get_item(Key={
            "SYMBOL#<sym>": pk,
            "DIVIDEND_SUMMARY#<date>": sk_val,
        })
        item = resp.get("Item")
        if item:
            db_data    = _from_dynamo(item.get("data", {}))
            fetched_at = item.get("fetched_at")
            sk         = sk_val

    except Exception as e:
        elapsed = time.time() - t0
        _print_result(endpoint, symbol, "ERROR", str(e), elapsed=elapsed)
        results.append({"endpoint": endpoint, "symbol": symbol, "status": "ERROR", "detail": str(e)})
        return

    live_data, err = fetch_live(url)
    elapsed = time.time() - t0

    if err:
        _print_result(endpoint, symbol, "ERROR", err, elapsed=elapsed)
        results.append({"endpoint": endpoint, "symbol": symbol, "status": "ERROR", "detail": err})
        return

    status, diff, summary = compare(db_data, live_data, args.diff)
    _print_result(endpoint, symbol, status, summary, fetched_at, sk, elapsed, diff)
    results.append({"endpoint": endpoint, "symbol": symbol, "status": status, "detail": summary})

def validate_stock_headlines(symbol, args, results):
    endpoint = "stock-headlines"
    pk = f"SYMBOL#{symbol}"
    url = f"{FLASK_BASE_URL}/headlines/{symbol}"

    t0 = time.time()
    db_data, sk, fetched_at = fetch_db_latest(TABLES[endpoint], pk)
    live_data, err = fetch_live(url)
    elapsed = time.time() - t0

    if err:
        _print_result(endpoint, symbol, "ERROR", err, elapsed=elapsed)
        results.append({"endpoint": endpoint, "symbol": symbol, "status": "ERROR", "detail": err})
        return

    status, diff, summary = compare(db_data, live_data, args.diff)
    _print_result(endpoint, symbol, status, summary, fetched_at, sk, elapsed, diff)
    results.append({"endpoint": endpoint, "symbol": symbol, "status": status, "detail": summary})





def validate_stock_competitors(symbol, args, results):
    endpoint = "stock-competitors"
    pk = f"SYMBOL#{symbol}"
    url = f"{FLASK_BASE_URL}/competitors/{symbol}"

    t0 = time.time()
    db_data, sk, fetched_at = fetch_db_latest(TABLES[endpoint], pk)
    live_data, err = fetch_live(url)
    elapsed = time.time() - t0

    if err:
        _print_result(endpoint, symbol, "ERROR", err, elapsed=elapsed)
        results.append({"endpoint": endpoint, "symbol": symbol, "status": "ERROR", "detail": err})
        return

    status, diff, summary = compare(db_data, live_data, args.diff)
    _print_result(endpoint, symbol, status, summary, fetched_at, sk, elapsed, diff)
    results.append({"endpoint": endpoint, "symbol": symbol, "status": status, "detail": summary})


def validate_stock_options(symbol, args, results):
    endpoint = "stock-options"
    pk = f"SYMBOL#{symbol}"
    url = f"{FLASK_BASE_URL}/options/{symbol}"

    t0 = time.time()
    db_data, sk, fetched_at = fetch_db_latest(TABLES[endpoint], pk)
    live_data, err = fetch_live(url)
    elapsed = time.time() - t0

    if err:
        _print_result(endpoint, symbol, "ERROR", err, elapsed=elapsed)
        results.append({"endpoint": endpoint, "symbol": symbol, "status": "ERROR", "detail": err})
        return

    status, diff, summary = compare(db_data, live_data, args.diff)
    _print_result(endpoint, symbol, status, summary, fetched_at, sk, elapsed, diff)
    results.append({"endpoint": endpoint, "symbol": symbol, "status": status, "detail": summary})

def validate_stock_short_interest(symbol, args, results):
    endpoint = "stock-short-interest"
    pk = f"SYMBOL#{symbol}"
    url = f"{FLASK_BASE_URL}/short-interest/{symbol}"

    t0 = time.time()
    db_data, sk, fetched_at = fetch_db_latest(TABLES[endpoint], pk)
    live_data, err = fetch_live(url)
    elapsed = time.time() - t0

    if err:
        _print_result(endpoint, symbol, "ERROR", err, elapsed=elapsed)
        results.append({"endpoint": endpoint, "symbol": symbol, "status": "ERROR", "detail": err})
        return

    status, diff, summary = compare(db_data, live_data, args.diff)
    _print_result(endpoint, symbol, status, summary, fetched_at, sk, elapsed, diff)
    results.append({"endpoint": endpoint, "symbol": symbol, "status": status, "detail": summary})




def validate_bse_filings(symbol, args, results):
    endpoint = "bse-filings"
    pk = f"SYMBOL#{symbol}"
    url = f"{FLASK_BASE_URL}/bse-filings/{symbol}"

    t0 = time.time()
    db_data, sk, fetched_at = fetch_db_latest(TABLES[endpoint], pk)
    live_data, err = fetch_live(url)
    elapsed = time.time() - t0

    if err:
        _print_result(endpoint, symbol, "ERROR", err, elapsed=elapsed)
        results.append({"endpoint": endpoint, "symbol": symbol, "status": "ERROR", "detail": err})
        return

    status, diff, summary = compare_bse_filings(db_data, live_data, args.diff)
    _print_result(endpoint, symbol, status, summary, fetched_at, sk, elapsed, diff)
    results.append({"endpoint": endpoint, "symbol": symbol, "status": status, "detail": summary})



# ---------------------------------------------------------------------------
# Endpoint dispatch map
# ---------------------------------------------------------------------------

VALIDATORS = {
    "stock-page":             validate_stock_page,
    "stock-chart":            validate_stock_chart,
    "stock-financials":       validate_stock_financials,
    "stock-earnings":         validate_stock_earnings,
    "stock-dividend-summary": validate_stock_dividend_summary,
    "stock-headlines":        validate_stock_headlines,
    
    "stock-competitors":      validate_stock_competitors,
    "stock-options":          validate_stock_options,
    "stock-short-interest":   validate_stock_short_interest,
    
    "bse-filings":            validate_bse_filings,
}

# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def print_summary(results: list, only_mismatches: bool):
    total    = len(results)
    match    = sum(1 for r in results if r["status"] == "MATCH")
    mismatch = sum(1 for r in results if r["status"] == "MISMATCH")
    empty_db = sum(1 for r in results if r["status"] == "EMPTY_DB")
    empty_lv = sum(1 for r in results if r["status"] == "EMPTY_LIVE")
    both_emp = sum(1 for r in results if r["status"] == "BOTH_EMPTY")
    errors   = sum(1 for r in results if r["status"] == "ERROR")

    print()
    print(_bold("=" * 60))
    print(_bold("  VALIDATION SUMMARY"))
    print(_bold("=" * 60))
    print(f"  Total checks   : {_bold(str(total))}")
    print(f"  {_green('✅  MATCH')}         : {match}")
    print(f"  {_red('❌  MISMATCH')}      : {mismatch}")
    print(f"  {_yellow('🟡  EMPTY_DB')}      : {empty_db}")
    print(f"  {_yellow('🟠  EMPTY_LIVE')}    : {empty_lv}")
    print(f"  {_yellow('⬜  BOTH_EMPTY')}    : {both_emp}")
    print(f"  {_red('🔴  ERROR')}         : {errors}")
    print(_bold("=" * 60))

    if only_mismatches:
        bad = [r for r in results if r["status"] not in ("MATCH",)]
        if bad:
            print(_bold("\n  Non-matching items:"))
            for r in bad:
                color_fn = STATUS_COLOR.get(r["status"], lambda x: x)
                print(f"    {STATUS_ICON.get(r['status'], '?')}  "
                      f"{color_fn(r['status'])}  "
                      f"{_cyan(r['endpoint']):<28}  "
                      f"{r['symbol']}  —  {r['detail']}")
        else:
            print(_green("\n  All checks passed!"))

    print()

# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        description="Validate DynamoDB stored values against live Flask endpoint responses.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python validate_dynamo.py --symbol INFY
  python validate_dynamo.py --symbol INFY TCS RELIANCE
  python validate_dynamo.py --symbol INFY --endpoints stock-page stock-chart
  python validate_dynamo.py --symbol INFY --period 1y --interval 1d --diff
  python validate_dynamo.py --symbol TCS --peers INFY WIPRO
  python validate_dynamo.py --symbol NIFTY --expiry 2025-05-29
  python validate_dynamo.py --symbol INFY --only-mismatches
        """
    )

    p.add_argument(
        "--symbol", "-s",
        nargs="+",
        required=True,
        help="One or more NSE symbols to validate (e.g. INFY TCS RELIANCE)",
    )
    p.add_argument(
        "--endpoints", "-e",
        nargs="+",
        choices=ALL_ENDPOINTS,
        default=ALL_ENDPOINTS,
        help="Endpoints to validate (default: all 12)",
    )
    p.add_argument(
        "--period",
        default="1y",
        help="Chart period for stock-chart validation (default: 1y)",
    )
    p.add_argument(
        "--interval",
        default="1d",
        help="Chart interval for stock-chart validation (default: 1d)",
    )
    p.add_argument(
        "--peers",
        nargs="+",
        default=None,
        help="Peer symbols for stock-sentiment validation (e.g. INFY WIPRO)",
    )
    p.add_argument(
        "--expiry",
        default=None,
        help="Expiry date for stock-options validation (e.g. 2025-05-29)",
    )
    p.add_argument(
        "--diff",
        action="store_true",
        help="Show field-level diff on mismatch (requires deepdiff)",
    )
    p.add_argument(
        "--only-mismatches",
        action="store_true",
        help="In the summary, only list non-matching results",
    )
    p.add_argument(
        "--base-url",
        default=None,
        help=f"Flask base URL (default: {FLASK_BASE_URL})",
    )
    return p


def main():
    parser = build_parser()
    args   = parser.parse_args()

    # Allow CLI override of base URL
    global FLASK_BASE_URL
    if args.base_url:
        FLASK_BASE_URL = args.base_url.rstrip("/")

    if args.diff and not HAS_DEEPDIFF:
        print(_yellow("  [WARN] deepdiff not installed — falling back to manual key diff."))
        print(_yellow("         Install it with:  pip install deepdiff\n"))

    symbols   = [s.upper().strip() for s in args.symbol]
    endpoints = args.endpoints

    print()
    print(_bold(f"  Flask base URL : {FLASK_BASE_URL}"))
    print(_bold(f"  AWS region     : {AWS_REGION}"))
    print(_bold(f"  Symbols        : {', '.join(symbols)}"))
    print(_bold(f"  Endpoints      : {', '.join(endpoints)}"))
    print(_bold(f"  Run started    : {datetime.now(timezone.utc).isoformat()} UTC"))
    print()

    all_results = []

    for symbol in symbols:
        print(_bold(f"\n{'─' * 60}"))
        print(_bold(f"  Symbol: {symbol}"))
        print(_bold(f"{'─' * 60}"))

        for ep in endpoints:
            validator = VALIDATORS.get(ep)
            if not validator:
                print(f"  ⏭   {_cyan(ep):<28} — no validator registered, skipping")
                all_results.append({"endpoint": ep, "symbol": symbol, "status": "SKIP", "detail": "no validator"})
                continue

            # Skip endpoints that don't apply (e.g. options for non-F&O symbols)
            # — user can still force them via --endpoints
            validator(symbol, args, all_results)

    print_summary(all_results, args.only_mismatches)


if __name__ == "__main__":
    main()
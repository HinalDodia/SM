"""
Shared helper utilities used across multiple route modules.

These functions were previously duplicated inside earnings_page() and
financials_page(). Extracting them here ensures a single source of truth
and makes both routes easier to read.
"""

import pandas as pd


def safe_float(val):
    """Return float(val), or None if val is None or NaN."""
    try:
        if val is None:
            return None
        if pd.isna(val):
            return None
        return float(val)
    except Exception:
        return None


def format_cr(value):
    """Convert a raw INR value to Crores (1 Cr = 10,000,000)."""
    val = safe_float(value)
    if val is None:
        return None
    return round(val / 10_000_000, 2)


def format_currency_cr(value):
    """Return a human-readable Crore string, e.g. '₹1,234 Cr'."""
    val = format_cr(value)
    if val is None:
        return None
    return f"₹{val:,.0f} Cr"


def quarter_label(date):
    """
    Return a quarter label like 'Q2 2025' from a date-like value.
    Returns None if the date cannot be parsed.
    """
    try:
        dt = pd.to_datetime(date)
        q = (dt.month - 1) // 3 + 1
        return f"Q{q} {dt.year}"
    except Exception:
        return None

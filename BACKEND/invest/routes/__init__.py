"""
Routes package.

Exposes all sub-blueprints so the application factory can import and
register them with a single import statement.
"""

from .stock_chart          import stock_chart_bp
from .stock_page           import stock_page_bp
from .stock_headlines      import stock_headlines_bp
from .stock_competitors    import stock_competitors_bp
from .stock_dividend_summary import stock_dividend_bp
from .stock_earnings       import stock_earnings_bp
from .stock_financials     import stock_financials_bp
from .bse_filings          import bse_filings_bp
from .short_interest       import stock_short_interest_bp

__all__ = [
    "stock_chart_bp",
    "stock_page_bp",
    "stock_headlines_bp",
    "stock_competitors_bp",
    "stock_dividend_bp",
    "stock_earnings_bp",
    "stock_financials_bp",
    "bse_filings_bp",
    "stock_short_interest_bp",
]

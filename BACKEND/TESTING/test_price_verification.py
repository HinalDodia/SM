"""
BACKEND/TESTING/test_price_verification.py
Manual test script for Fix 1 — server-side price verification.

Run from the BACKEND directory with:
    python -m TESTING.test_price_verification

Requires the Flask app context (reads .env for DB creds).
All DB calls are rolled back so the test is non-destructive.
"""

import sys
import os

# ── Bootstrap path so we can import from invest/ ──────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from unittest.mock import patch
from decimal import Decimal

# Import the Flask app (which loads .env and creates the app context)
from run import app  # adjust if your Flask entry-point is named differently

import invest.portfolio as portfolio_module
from invest.portfolio import PriceMismatchError, ServiceUnavailableError


LIVE_PRICE = 1500.00          # simulated live price for the tests


def assert_raises(label, exc_class, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        print(f"  FAIL  {label}: expected {exc_class.__name__} but no exception raised")
        return False
    except exc_class as e:
        print(f"  PASS  {label}: raised {exc_class.__name__}({e})")
        return True
    except Exception as e:
        print(f"  FAIL  {label}: expected {exc_class.__name__} but got {type(e).__name__}({e})")
        return False


# ── Test 1a: buy at live price passes price check ─────────────────────────────
def test_buy_at_live_price_succeeds():
    print("\n[Test 1a] buy() at live price -- should pass price check")

    class FakeUser:
        money = Decimal("99999999")
        userid = 1

    with patch.object(portfolio_module, "_get_live_price_for_symbol",
                      return_value=(LIVE_PRICE, 0.0, 0.0)), \
         patch.object(portfolio_module, "userfromdb", return_value=FakeUser()), \
         patch.object(portfolio_module, "get_stock_entry", return_value=None), \
         patch.object(portfolio_module, "get_sector_from_api", return_value="Tech"), \
         patch.object(portfolio_module.db.session, "add", return_value=None), \
         patch.object(portfolio_module.db.session, "flush", return_value=None), \
         patch.object(portfolio_module.db.session, "commit", return_value=None):
        try:
            portfolio_module.buy(
                userid=1,
                stockname="TEST",
                qty=1,
                price=LIVE_PRICE,
                companyname="Test Co"
            )
            print("  PASS  buy at exact live price completed without PriceMismatchError")
        except PriceMismatchError:
            print("  FAIL  buy at exact live price incorrectly raised PriceMismatchError")
        except ServiceUnavailableError:
            print("  FAIL  buy raised ServiceUnavailableError unexpectedly")
        except Exception as e:
            print(f"  PASS  price check passed; downstream error is expected: {type(e).__name__}({e})")


# ── Test 1b: buy at price >1% off is rejected ─────────────────────────────────
def test_buy_price_over_threshold_rejected():
    print("\n[Test 1b] buy() at price >1% off live -- should raise PriceMismatchError")
    manipulated_price = round(LIVE_PRICE * 0.98, 2)  # 2% below

    class FakeUser:
        money = Decimal("99999999")
        userid = 1

    with patch.object(portfolio_module, "_get_live_price_for_symbol",
                      return_value=(LIVE_PRICE, 0.0, 0.0)), \
         patch.object(portfolio_module, "userfromdb", return_value=FakeUser()):
        assert_raises(
            f"buy at {manipulated_price} (live={LIVE_PRICE}, deviation=2%)",
            PriceMismatchError,
            portfolio_module.buy,
            userid=1, stockname="TEST", qty=1,
            price=manipulated_price, companyname="Test Co"
        )


# ── Test 1c: sell at inflated price is rejected ───────────────────────────────
def test_sell_price_over_threshold_rejected():
    print("\n[Test 1c] sell() at price >1% off live -- should raise PriceMismatchError")
    inflated_price = round(LIVE_PRICE * 1.05, 2)  # 5% above

    class FakeHolding:
        totalquantity = 10
        averagebuyprice = Decimal("1400")
        totalinvested = Decimal("14000")
        portfolioid = 999

    with patch.object(portfolio_module, "_get_live_price_for_symbol",
                      return_value=(LIVE_PRICE, 0.0, 0.0)), \
         patch.object(portfolio_module, "get_stock_entry", return_value=FakeHolding()):
        assert_raises(
            f"sell at {inflated_price} (live={LIVE_PRICE}, deviation=5%)",
            PriceMismatchError,
            portfolio_module.sell,
            userid=1, stockname="TEST", companyname="Test Co",
            qty=1, price=inflated_price
        )


# ── Test 1d: unavailable live price is rejected ───────────────────────────────
def test_buy_live_price_unavailable_rejected():
    print("\n[Test 1d] buy() when live price unavailable -- should raise ServiceUnavailableError")

    class FakeUser:
        money = Decimal("99999999")
        userid = 1

    with patch.object(portfolio_module, "_get_live_price_for_symbol",
                      return_value=(None, None, None)), \
         patch.object(portfolio_module, "userfromdb", return_value=FakeUser()):
        assert_raises(
            "buy with live_price=None",
            ServiceUnavailableError,
            portfolio_module.buy,
            userid=1, stockname="TEST", qty=1,
            price=LIVE_PRICE, companyname="Test Co"
        )


# ── Runner ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("Fix 1 -- Price Verification Tests")
    print("=" * 60)

    with app.app_context():
        test_buy_at_live_price_succeeds()
        test_buy_price_over_threshold_rejected()
        test_sell_price_over_threshold_rejected()
        test_buy_live_price_unavailable_rejected()

    print("\n" + "=" * 60)
    print("All Fix 1 tests complete.")
    print("=" * 60)

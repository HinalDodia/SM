"""
BACKEND/TESTING/test_live_caching_latency.py
Live caching measurement test for Section 3 (NO MOCKS).
Measures Call 1 (fresh/uncached) vs Call 2 (same-day DB cache hit).
"""

import sys
import os
import time

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from run import app
import invest.auth as auth_module
from invest.models import db, UserProfile, Users, Recommendation, Stock

def run_caching_test():
    print("=" * 70)
    print("Section 3 Live Test: Same-Day Recommendations Caching (NO MOCKS)")
    print("=" * 70)

    with app.app_context():
        db.create_all()

        # Find or create a test user
        user = Users.query.first()
        if not user:
            user = Users(name="Caching Test User", email="caching_test@example.com", money=100000)
            db.session.add(user)
            db.session.commit()

        user_id = user.userid
        token = auth_module._issue_jwt(user_id)

        # Ensure user profile exists
        profile = UserProfile.query.filter_by(userid=user_id).first()
        if not profile:
            profile = UserProfile(
                userid=user_id,
                risk_tolerance="moderate",
                investment_goal="growth",
                time_horizon="medium_term",
                capital_available=100000.0,
                max_per_trade_pct=10.0,
                experience_level="intermediate"
            )
            db.session.add(profile)
            db.session.commit()

        # Clear existing recommendations for today so Call 1 computes fresh
        Recommendation.query.filter_by(userid=user_id).delete()
        db.session.commit()

        client = app.test_client()

        # Call 1: First request of the day (Fresh computation)
        print("\n[Call 1] First Request of the Day (Fresh Computation)...")
        start1 = time.perf_counter()
        res1 = client.get(
            f"/analyzer/recommendations/{user_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        end1 = time.perf_counter()
        lat1 = end1 - start1

        print(f"  Call 1 Status Code : {res1.status_code}")
        print(f"  Call 1 Latency     : {lat1:.4f} seconds")
        data1 = res1.get_json() or {}
        print(f"  Call 1 Items Count : {len(data1.get('recommendations', []))}")

        # Call 2: Second request of the day (DB Cache hit)
        print("\n[Call 2] Second Request of the Day (Same-Day DB Cache Hit)...")
        start2 = time.perf_counter()
        res2 = client.get(
            f"/analyzer/recommendations/{user_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        end2 = time.perf_counter()
        lat2 = end2 - start2

        print(f"  Call 2 Status Code : {res2.status_code}")
        print(f"  Call 2 Latency     : {lat2:.4f} seconds")
        data2 = res2.get_json() or {}
        print(f"  Call 2 Items Count : {len(data2.get('recommendations', []))}")

        speedup = lat1 / lat2 if lat2 > 0 else 0
        print(f"\n--- LATENCY COMPARISON SUMMARY ---")
        print(f"Call 1 (Fresh Calculation) : {lat1:.4f} s")
        print(f"Call 2 (Same-Day DB Cache)  : {lat2:.4f} s")
        print(f"Cache Speedup Factor       : {speedup:.2f}x faster")
        print("=" * 70)

if __name__ == "__main__":
    run_caching_test()

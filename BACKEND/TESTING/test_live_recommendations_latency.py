"""
BACKEND/TESTING/test_live_recommendations_latency.py
Live latency measurement test for Section 2 (NO MOCKS).
Hits the real backend and database end-to-end.
"""

import sys
import os
import time

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from run import app
import invest.auth as auth_module
from invest.models import db, UserProfile, Users, Stock

def run_live_test():
    print("=" * 70)
    print("Section 2 Live Test: GET /analyzer/recommendations/<userid> Latency (NO MOCKS)")
    print("=" * 70)

    has_anthropic_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    print(f"ANTHROPIC_API_KEY Present: {has_anthropic_key}")

    with app.app_context():
        db.create_all()

        user = Users.query.first()
        if not user:
            user = Users(name="Live Test User", email="live_test@example.com", money=100000)
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

        client = app.test_client()

        print(f"\nSending live GET /analyzer/recommendations/{user_id} request...")
        start_time = time.perf_counter()
        response = client.get(
            f"/analyzer/recommendations/{user_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        end_time = time.perf_counter()
        elapsed_seconds = end_time - start_time

        print(f"\n--- LIVE RESPONSE RESULTS ---")
        print(f"Wall-clock Latency : {elapsed_seconds:.4f} seconds")
        print(f"HTTP Status Code   : {response.status_code}")
        
        data = response.get_json() or {}
        recs = data.get("recommendations", [])
        print(f"Recommendations Count: {len(recs)}")

        if recs:
            print("Sample Recommendation Item:")
            print(f"  Symbol           : {recs[0].get('symbol')}")
            print(f"  Action           : {recs[0].get('action')}")
            print(f"  Score            : {recs[0].get('score')}")
            print(f"  Suggested Amount : {recs[0].get('suggested_amount')}")
            print(f"  Explanation      : {recs[0].get('explanation')}")
            print(f"  Reasons          : {recs[0].get('reasons')}")

        print("\n" + "=" * 70)

if __name__ == "__main__":
    run_live_test()

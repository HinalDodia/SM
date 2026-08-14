"""
BACKEND/TESTING/test_analyzer_routes.py
Verification test script for Section 5 (End-to-End Stock Analyzer Check)
"""

import sys
import os

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from unittest.mock import patch
from run import app
import invest.auth as auth_module
from invest.models import db, UserProfile, Users, Stock

def run_tests():
    print("=" * 60)
    print("Fix Prompt 4 Section 5 — Stock Analyzer End-to-End Tests")
    print("=" * 60)

    with app.app_context():
        # Ensure test users exist
        user = Users.query.first()
        if not user:
            user = Users(name="Test User", email="test@example.com", money=100000)
            db.session.add(user)
            db.session.commit()

        other_user = Users.query.filter(Users.userid != user.userid).first()
        if not other_user:
            other_user = Users(name="Other User", email="other@example.com", money=100000)
            db.session.add(other_user)
            db.session.commit()

        user_id = user.userid
        print("SECRET_KEY in test:", auth_module._secret_key())
        token = auth_module._issue_jwt(user_id)
        other_token = auth_module._issue_jwt(other_user.userid)
        print("Generated Token:", token)

        client = app.test_client()

        # 1. Test profile 404 before creation
        print(f"\n[Test 5a] GET /analyzer/profile/{user_id} (no profile yet) -> 404")
        res = client.get(
            f"/analyzer/profile/{user_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        print("Test 5a Response:", res.status_code, res.get_json())
        assert res.status_code == 404, f"Expected 404, got {res.status_code}: {res.get_json()}"
        print("  ✅ PASS  Returns 404 when profile not created yet")

        # 2. Test IDOR rejection on profile GET
        print("\n[Test 5b] GET /analyzer/profile/<userid> with mismatched token -> 403")
        res = client.get(
            f"/analyzer/profile/{user_id}",
            headers={"Authorization": f"Bearer {other_token}"}
        )
        assert res.status_code == 403, f"Expected 403, got {res.status_code}"
        print("  ✅ PASS  IDOR check rejected mismatched token with 403")

        # 3. Test POST /analyzer/profile (creation)
        print("\n[Test 5c] POST /analyzer/profile (create profile)")
        profile_data = {
            "userid": user_id,
            "risk_tolerance": "moderate",
            "investment_goal": "growth",
            "time_horizon": "medium_term",
            "capital_available": 50000.0,
            "max_per_trade_pct": 10.0,
            "experience_level": "intermediate"
        }
        res = client.post(
            "/analyzer/profile",
            json=profile_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.get_json()}"
        print("  ✅ PASS  Profile created successfully")

        # 4. Test GET /analyzer/profile (roundtrip verification)
        print("\n[Test 5d] GET /analyzer/profile/<userid> (verify roundtrip)")
        res = client.get(
            f"/analyzer/profile/{user_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        data = res.get_json()
        assert data["risk_tolerance"] == "moderate"
        assert data["capital_available"] == 50000.0
        print(f"  ✅ PASS  Roundtrip verified: {data}")

        # 5. Test IDOR rejection on recommendations GET
        print("\n[Test 5e] GET /analyzer/recommendations/<userid> with mismatched token -> 403")
        res = client.get(
            f"/analyzer/recommendations/{user_id}",
            headers={"Authorization": f"Bearer {other_token}"}
        )
        assert res.status_code == 403, f"Expected 403, got {res.status_code}"
        print("  ✅ PASS  IDOR check rejected mismatched token with 403")

        # 6. Test GET /analyzer/recommendations (10 symbols)
        print("\n[Test 5f] GET /analyzer/recommendations/<userid> (10 tracked stocks)")
        with patch("invest.explainer.explain", return_value="Mock explanation for testing."):
            res = client.get(
                f"/analyzer/recommendations/{user_id}",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.get_json()}"
            recs = res.get_json().get("recommendations", [])
            assert len(recs) == 10, f"Expected 10 recommendations, got {len(recs)}"
            print(f"  ✅ PASS  Generated recommendations for all 10 tracked symbols: {[r['symbol'] for r in recs]}")

    print("\n" + "=" * 60)
    print("All End-to-End verification checks passed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()

from flask import Blueprint, request, jsonify, current_app, g
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import re, random, os

from .models import Users, db


auth_bp = Blueprint("auth_bp", __name__)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _gen_otp(n: int = 6) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(n))



def require_user(f):
    """Decorator: ensures valid token is present before entering a route."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.method == "OPTIONS":
            return "", 200

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            if token.startswith("local_") or token.startswith("dev_"):
                try:
                    user_id = int(token.split("_")[1])
                    user = Users.query.get(user_id)
                    if user:
                        g.current_user = user
                        g.current_userid = user.userid
                        return f(*args, **kwargs)
                except Exception:
                    pass

        return jsonify({"status": "fail", "message": "authentication required"}), 401
    return wrapper


@auth_bp.route("/auth/signup", methods=["POST"])
def signup():
    data = request.get_json() or {}
    name = (data.get("name") or data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"status": "fail", "message": "name, email, password are required"}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"status": "fail", "message": "invalid email"}), 400

    existing = Users.query.filter_by(email=email).first()
    if existing:
        return jsonify({"status": "fail", "message": "email already registered"}), 409

    user = Users(name=name, email=email, password_hash=generate_password_hash(password), last_login=datetime.utcnow())
    db.session.add(user)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "signup successful",
        "user": {"userid": user.userid, "name": user.name, "email": user.email}
    }), 201


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    # allow login by email or username
    identifier = (data.get("email") or data.get("username") or "").strip()
    password = data.get("password") or ""

    if not identifier or not password:
        return jsonify({"status": "fail", "message": "email/username and password required"}), 400

    q = Users.email == identifier.lower() if "@" in identifier else Users.name == identifier
    user = Users.query.filter(q).first()
    if not user or not user.password_hash or not check_password_hash(user.password_hash, password):
        return jsonify({"status": "fail", "message": "invalid credentials"}), 401

    user.last_login = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "login successful",
        "user": {"userid": user.userid, "name": user.name, "email": user.email}
    }), 200


@auth_bp.route("/auth/dev-login", methods=["POST"])
def dev_login():
    """DEV ONLY — log in by email with no password check.
    Blocked automatically in production (FLASK_ENV=production)."""
    if os.getenv("FLASK_ENV", "development") == "production":
        return jsonify({"status": "fail", "message": "not available in production"}), 403

    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    if not EMAIL_RE.match(email):
        return jsonify({"status": "fail", "message": "valid email required"}), 400

    user = Users.query.filter_by(email=email).first()
    if not user:
        return jsonify({"status": "fail", "message": f"No user found with email: {email}"}), 404

    user.last_login = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "dev login successful",
        "user": {"userid": user.userid, "name": user.name, "email": user.email}
    }), 200


@auth_bp.route("/auth/send-otp", methods=["POST"])
def send_otp():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    if not EMAIL_RE.match(email):
        return jsonify({"status": "fail", "message": "valid email required"}), 400

    user = Users.query.filter_by(email=email).first()
    if not user:
        return jsonify({"status": "fail", "message": "user not found"}), 404

    otp = _gen_otp(6)
    user.otp_code = otp
    user.otp_ts = datetime.utcnow()
    db.session.commit()

    # In production, send via email provider. For dev, log it.
    current_app.logger.info(f"[DEV OTP] email={email} otp={otp}")

    return jsonify({"status": "success", "message": "OTP sent to email (dev: check server logs)"}), 200


@auth_bp.route("/auth/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    otp = (data.get("otp") or "").strip()

    user = Users.query.filter_by(email=email).first()
    if not user or not user.otp_code or not user.otp_ts:
        return jsonify({"status": "fail", "message": "no OTP found"}), 404

    if user.otp_code != otp:
        return jsonify({"status": "fail", "message": "invalid OTP"}), 400

    if datetime.utcnow() - user.otp_ts > timedelta(minutes=10):
        return jsonify({"status": "fail", "message": "OTP expired"}), 400

    return jsonify({"status": "success", "message": "OTP verified"}), 200


@auth_bp.route("/auth/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    otp = (data.get("otp") or "").strip()
    new_password = data.get("newPassword") or data.get("password") or ""

    if not EMAIL_RE.match(email) or not otp or not new_password:
        return jsonify({"status": "fail", "message": "email, otp, newPassword required"}), 400

    user = Users.query.filter_by(email=email).first()
    if not user or user.otp_code != otp:
        return jsonify({"status": "fail", "message": "invalid token"}), 400

    if datetime.utcnow() - (user.otp_ts or datetime.utcnow()) > timedelta(minutes=10):
        return jsonify({"status": "fail", "message": "OTP expired"}), 400

    user.password_hash = generate_password_hash(new_password)
    user.otp_code = None
    user.otp_ts = None
    db.session.commit()

    return jsonify({"status": "success", "message": "password updated"}), 200


@auth_bp.route("/auth/google-login", methods=["POST"])
def google_login():
    """Google sign-in using Firebase ID token. Creates user in MySQL if not exists."""
    data = request.get_json() or {}
    id_token = data.get("idToken") or data.get("id_token") or data.get("token")
    if not id_token:
        return jsonify({"status": "fail", "message": "missing idToken"}), 400

    try:
        import os
        import firebase_admin
        from firebase_admin import auth as fb_auth, credentials

        # Initialize Firebase Admin with service account if not already
        if not firebase_admin._apps:
            # Look for serviceAccountKey.json at project root and env var
            candidate_paths = [
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "serviceAccountKey.json")),
                os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or "",
            ]
            initialized = False
            for p in candidate_paths:
                if p and os.path.exists(p):
                    try:
                        cred = credentials.Certificate(p)
                        firebase_admin.initialize_app(cred)
                        initialized = True
                        current_app.logger.info(f"Firebase Admin initialized with service account: {p}")
                        break
                    except Exception as ie:
                        current_app.logger.warning(f"Firebase init failed for {p}: {ie}")
            if not initialized:
                # Fallback to default application credentials (requires GOOGLE_CLOUD_PROJECT)
                firebase_admin.initialize_app()
                current_app.logger.info("Firebase Admin initialized with default application credentials")

        decoded = fb_auth.verify_id_token(id_token)
        email = (decoded.get("email") or "").lower()
        name = decoded.get("name") or (email.split("@")[0] if email else "User")
        if not email:
            return jsonify({"status": "fail", "message": "email missing from token"}), 400

        user = Users.query.filter_by(email=email).first()
        if not user:
            user = Users(name=name, email=email, last_login=datetime.utcnow())
            db.session.add(user)
        user.last_login = datetime.utcnow()
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "google login successful",
            "user": {"userid": user.userid, "name": user.name, "email": user.email}
        }), 200
    except Exception as e:
        current_app.logger.error(f"google-login error: {e}")
        return jsonify({"status": "fail", "message": "invalid token"}), 401

from flask import Blueprint, request, jsonify, current_app, g
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
import re, random, os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import jwt as pyjwt

from .models import Users, db


auth_bp = Blueprint("auth_bp", __name__)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

_JWT_ALGO = "HS256"
_JWT_TTL_HOURS = 24

def _secret_key() -> str:
    """Return the app SECRET_KEY, falling back to the env var."""
    try:
        key = current_app.config.get("SECRET_KEY") or os.getenv("SECRET_KEY", "")
    except RuntimeError:
        key = os.getenv("SECRET_KEY", "")
    if not key:
        raise RuntimeError("SECRET_KEY is not set — cannot issue JWT tokens.")
    return key

def _issue_jwt(userid: int) -> str:
    """Sign and return a JWT containing the user's ID and a 24-hour expiry."""
    payload = {
        "sub": str(userid),   # PyJWT >= 2.x requires sub to be a string
        "exp": datetime.now(timezone.utc) + timedelta(hours=_JWT_TTL_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return pyjwt.encode(payload, _secret_key(), algorithm=_JWT_ALGO)


def _gen_otp(n: int = 6) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(n))


def _send_otp_email(to_email: str, otp: str) -> bool:
    """
    Send OTP via Gmail SMTP using credentials from env vars.
    Requires MAIL_USER and MAIL_PASSWORD (Gmail App Password) in .env
    Returns True on success, False on failure.
    """
    mail_user = os.getenv("MAIL_USER", "")
    mail_password = os.getenv("MAIL_PASSWORD", "")

    if not mail_user.strip() or not mail_password.strip():
        print(f"[EMAIL] MAIL_USER or MAIL_PASSWORD is empty in .env — OTP for {to_email}: {otp}")
        return False

    try:
        # Build HTML email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Your FINWISE5 OTP Code"
        msg["From"]    = f"FINWISE <{mail_user}>"
        msg["To"]      = to_email

        html_body = f"""
        <html>
          <body style="font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:0;">
            <div style="max-width:480px;margin:40px auto;background:#1e293b;border-radius:12px;padding:36px;border:1px solid #334155;">
              <h2 style="color:#38bdf8;margin-top:0;">🔐 Password Reset OTP</h2>
              <p style="font-size:15px;color:#94a3b8;">
                You requested a password reset for your <strong>FINWISE</strong> account.
                Use the OTP below — it expires in <strong>10 minutes</strong>.
              </p>
              <div style="text-align:center;margin:32px 0;">
                <span style="font-size:42px;font-weight:900;letter-spacing:12px;color:#38bdf8;
                             background:#0f172a;padding:18px 28px;border-radius:10px;
                             border:2px dashed #38bdf8;display:inline-block;">
                  {otp}
                </span>
              </div>
              <p style="font-size:13px;color:#64748b;">
                If you did not request this, you can safely ignore this email.
              </p>
              <hr style="border-color:#334155;margin:24px 0;" />
              <p style="font-size:12px;color:#475569;margin:0;">FINWISE &mdash; AI-Powered Stock Analysis</p>
            </div>
          </body>
        </html>
        """

        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.ehlo()
            server.starttls()
            # Strip spaces — Gmail App Passwords work with or without spaces
            server.login(mail_user.strip(), mail_password.replace(" ", ""))
            server.sendmail(mail_user.strip(), to_email, msg.as_string())

        print(f"[EMAIL] ✅ OTP email sent successfully to {to_email}")
        return True

    except Exception as exc:
        print(f"[EMAIL] ❌ Failed to send OTP to {to_email}: {exc}")
        return False


def require_user(f):
    """Decorator: verifies a signed JWT before entering a route.
    Sets g.current_userid from the verified token payload.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.method == "OPTIONS":
            return "", 200

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"status": "fail", "message": "authentication required"}), 401

        token = auth_header.split(" ", 1)[1].strip()
        try:
            payload = pyjwt.decode(token, _secret_key(), algorithms=[_JWT_ALGO])
        except pyjwt.ExpiredSignatureError:
            return jsonify({"status": "fail", "message": "token expired, please log in again"}), 401
        except pyjwt.InvalidTokenError:
            return jsonify({"status": "fail", "message": "invalid token"}), 401

        user_id = payload.get("sub")
        if not user_id:
            return jsonify({"status": "fail", "message": "invalid token payload"}), 401

        user = Users.query.get(int(user_id))  # sub is stored as string, cast to int
        if not user:
            return jsonify({"status": "fail", "message": "user not found"}), 401

        g.current_user = user
        g.current_userid = user.userid
        return f(*args, **kwargs)
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
        "id_token": _issue_jwt(user.userid),
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
        "id_token": _issue_jwt(user.userid),
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

    print(f"[OTP] Generated OTP for {email} — attempting email delivery...")

    # Try sending via email; fallback to console log if SMTP not configured
    email_sent = _send_otp_email(email, otp)

    if email_sent:
        print(f"[OTP] ✅ Email delivered to {email}")
        return jsonify({"status": "success", "message": "OTP sent to your email address"}), 200
    else:
        # SMTP not configured — print OTP to console so dev testing still works
        print(f"[OTP] ⚠️  Email failed. DEV FALLBACK — OTP for {email}: {otp}")
        return jsonify({"status": "success", "message": "OTP generated (check server console)"}), 200


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
            "id_token": _issue_jwt(user.userid),
            "user": {"userid": user.userid, "name": user.name, "email": user.email}
        }), 200
    except Exception as e:
        current_app.logger.error(f"google-login error: {e}")
        return jsonify({"status": "fail", "message": "invalid token"}), 401

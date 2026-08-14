import os

# pyrefly: ignore [missing-import]  
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from dotenv import load_dotenv

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)

    # ---- Logging setup — make INFO/DEBUG visible in terminal ----
    import logging
    import sys
    _fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
        datefmt="%H:%M:%S"
    )
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setLevel(logging.DEBUG)
    _handler.setFormatter(_fmt)

    # Apply to app.logger
    app.logger.setLevel(logging.DEBUG)
    if not app.logger.handlers:
        app.logger.addHandler(_handler)
    app.logger.propagate = False  # prevent duplicate output

    # Apply to root logger so print-less libs also show
    _root = logging.getLogger()
    _root.setLevel(logging.DEBUG)
    if not any(isinstance(h, logging.StreamHandler) for h in _root.handlers):
        _root.addHandler(_handler)

    # ---- Load .env first so all env vars are available for CORS config etc. ----
    _here = os.path.dirname(os.path.abspath(__file__))
    ENV_PATH = os.path.join(_here, "..", ".env")  # BACKEND/.env
    load_dotenv(ENV_PATH)

    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("SECRET_KEY is missing from environment variables (.env) — cannot start application.")
    app.config["SECRET_KEY"] = secret_key

    @app.route('/favicon.ico')
    def favicon():
        return '', 204

    # ------------------------------------------------------------------
    # Database Configuration
    # ------------------------------------------------------------------
    # Two configurations are kept here side-by-side.
    # Switch between them by commenting / uncommenting the right block
    # in .env  (see DATABASE_MIGRATION_GUIDE.md for full instructions).
    # ------------------------------------------------------------------

    # ---- AWS RDS Configuration (COMMENTED OUT — do NOT delete) ----
    # To restore RDS: uncomment this block and comment out the local block below.
    #
    # db_host     = os.getenv("DB_HOST")      # RDS endpoint
    # db_port     = os.getenv("DB_PORT", "3306")
    # db_name     = os.getenv("DB_NAME")      # investment
    # db_user     = os.getenv("DB_USER")      # admin
    # db_password = os.getenv("DB_PASSWORD")  # RDS password
    # database_url = (
    #     f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    # )
    # # SSL settings required for AWS RDS
    # ssl_ca = os.getenv("DB_SSL_CA", "/etc/ssl/certs/ca-bundle.crt")
    # engine_options = {
    #     "connect_args": {
    #         "ssl": {
    #             "ca": ssl_ca,
    #         }
    #     },
    #     "pool_pre_ping": True,
    #     "pool_recycle": 300,
    # }

    # ---- Local MySQL Configuration (ACTIVE) ----
    # To switch back to RDS: comment out this block and uncomment the RDS block above.
    db_host     = os.getenv("DB_HOST", "localhost")
    db_port     = os.getenv("DB_PORT", "3306")
    db_name     = os.getenv("DB_NAME", "investment")
    db_user     = os.getenv("DB_USER", "root")
    db_password = os.getenv("DB_PASSWORD", "")
    # Build URL from individual vars; fall back to DATABASE_URL if vars are missing
    if db_host and db_name and db_user:
        import urllib.parse
        encoded_password = urllib.parse.quote(db_password, safe="")
        database_url = (
            f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"
        )
    else:
        database_url = os.getenv("DATABASE_URL")
    # No SSL for local MySQL
    engine_options = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    # ------------------------------------------------------------------

    if not database_url:
        raise RuntimeError("DATABASE_URL is missing — .env not loaded")

    #
    # ---- Database Config ----
    #
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options

    db.init_app(app)

    # ---- CORS allowed origins ----
    # Add FRONTEND_URL to your production .env to whitelist your deployed domain.
    _frontend_url = os.getenv("FRONTEND_URL", "").rstrip("/")
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    if _frontend_url and _frontend_url not in allowed_origins:
        allowed_origins.append(_frontend_url)

    # Configure flask-cors with the final origin list
    CORS(app, resources={r"/*": {"origins": allowed_origins}}, supports_credentials=True)

    # ---- Blueprints & Caching ----
    from .routes import routes_bp, cache
    cache.init_app(app)

    from .dashboard import dashboard_bp
    from .auth import auth_bp

    print("DEBUG: Registering routes_bp...")
    app.register_blueprint(routes_bp)

    print("DEBUG: Registering dashboard_bp...")
    app.register_blueprint(dashboard_bp)

    print("DEBUG: Registering auth_bp...")
    app.register_blueprint(auth_bp)

    print("DEBUG: All blueprints registered!")

    # ---- Ensure all MySQL tables (user_profiles, recommendations, etc.) exist ----
    with app.app_context():
        from . import models  # noqa: F401
        db.create_all()
    #
    #    # ---- CORS on every response ----
    #
    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        if origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = \
                "GET, POST, PUT, DELETE, OPTIONS"
            response.headers.setdefault(
                "Access-Control-Allow-Headers",
                "Content-Type, Authorization, X-User-Id",
            )
        return response

    #
    # ---- Global Error Handler ----
    #
    @app.errorhandler(Exception)
    def handle_exception(e):
        import traceback
        traceback.print_exc()

        resp = jsonify({"error": str(e)})
        resp.status_code = 500

        origin = request.headers.get("Origin")
        if origin in allowed_origins:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Credentials"] = "true"

        return resp

    return app

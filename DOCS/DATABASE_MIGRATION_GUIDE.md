# Database Migration Guide

## Current Setup
- Database: Local MySQL
- Host: `localhost`
- Port: `3306`
- Database Name: `investment`
- Username: `root`

---

## Files Modified
| File | What Changed |
|------|-------------|
| `BACKEND/.env` | Added individual `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_USE_SSL` vars for local MySQL. AWS RDS block preserved as commented-out backup. |
| `BACKEND/invest/__init__.py` | Builds `DATABASE_URL` from individual `DB_*` vars; added `SQLALCHEMY_ENGINE_OPTIONS` with `pool_pre_ping` and `pool_recycle`; full AWS RDS block (including SSL `connect_args`) kept as commented-out code. |

---

## Local → AWS RDS

- **Uncomment** the `# ---- AWS RDS ----` block in both `.env` and `invest/__init__.py`
- **Comment out** the `# ---- Local MySQL ----` block in both files
- **Replace `DB_HOST`:** `investment-db.c3k8wc4ci776.ap-south-1.rds.amazonaws.com`
- **Replace `DB_PORT`:** `3306`
- **Replace `DB_NAME`:** `investment`
- **Replace `DB_USER`:** `admin`
- **Replace `DB_PASSWORD`:** _(RDS admin password)_
- **Enable SSL:** set `DB_USE_SSL=true`; set `DB_SSL_CA` to the path of the AWS RDS CA bundle
- **Restore RDS `DATABASE_URL`:** `mysql+pymysql://admin:<password>@<rds-endpoint>:3306/investment`
- **Restore engine options:** uncomment the `connect_args` → `ssl` block in `__init__.py`

---

## AWS RDS → Local

- Comment out the `# ---- AWS RDS ----` block in `.env` and `__init__.py`
- Uncomment the `# ---- Local MySQL ----` block in both files
- Set `DB_HOST=localhost`
- Set `DB_PORT=3306`
- Set `DB_NAME=investment`
- Set `DB_USER=root`
- Set `DB_PASSWORD=` _(your local root password, can be empty)_
- Set `DB_USE_SSL=false`
- Ensure the `SQLALCHEMY_ENGINE_OPTIONS` block in `__init__.py` does **not** include `connect_args`/`ssl`

---

## Environment Variables

| Variable | Description | Local Value | RDS Value |
|----------|-------------|-------------|-----------|
| `DB_HOST` | Database host | `localhost` | RDS endpoint |
| `DB_PORT` | Database port | `3306` | `3306` |
| `DB_NAME` | Database name | `investment` | `investment` |
| `DB_USER` | Database user | `root` | `admin` |
| `DB_PASSWORD` | Database password | _(local root password)_ | RDS admin password |
| `DB_USE_SSL` | Enable SSL | `false` | `true` |
| `DB_SSL_CA` | Path to SSL CA cert | _(not set)_ | `/etc/ssl/certs/ca-bundle.crt` |
| `DATABASE_URL` | Full connection string (fallback) | auto-built from vars above | auto-built from vars above |

> **Note:** `DATABASE_URL` is now auto-constructed from the individual `DB_*` vars in `__init__.py`. The literal `DATABASE_URL` in `.env` serves as a human-readable reference and fallback only.

---

## Verification

- [ ] Backend starts successfully (`python run.py` — no `RuntimeError` on startup)
- [ ] Database connection successful (check server logs for no `OperationalError`)
- [ ] CRUD operations working (create/read user, buy/sell stock, watchlist)
- [ ] Authentication working (`/auth/signup`, `/auth/login`, `/auth/dev-login`)
- [ ] Portfolio routes respond correctly (`/portfolio/*`)
- [ ] Dashboard routes respond correctly (`/dashboard/*`)

---

## Notes

- Both AWS RDS and Local MySQL configurations are permanently kept in code — **never delete either block**.
- Use comments to switch between Local and AWS — a one-block toggle in `.env` + `__init__.py`.
- The `insert.py` script uses DynamoDB (AWS) independently of the MySQL config — no changes needed there.
- `pool_pre_ping=True` and `pool_recycle=300` are active for both environments to handle idle connection drops.
- If your local root password contains special characters, URL-encode them (e.g., `@` → `%40`) **or** leave `DB_PASSWORD` in `.env` and let `__init__.py` encode it automatically via `urllib.parse.quote`.

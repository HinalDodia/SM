"""
migrate_analyzer_fields.py
==========================
One-shot migration: adds the §0 columns to user_profiles and recommendations.
Run once after pulling this commit:

    cd BACKEND
    python -c "from invest import create_app; app = create_app()
    from invest.migrate_analyzer_fields import run; run(app)"

Or from the BACKEND directory:
    python migrate_analyzer_fields.py

Safe to re-run — each ALTER TABLE is guarded by a column-existence check.
"""
import os
import sys

# Allow running as a standalone script from BACKEND/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(
        f"SELECT COUNT(*) FROM information_schema.columns "
        f"WHERE table_schema = DATABASE() "
        f"  AND table_name = '{table}' "
        f"  AND column_name = '{column}'"
    )
    return result.scalar() > 0


def run(app=None):
    if app is None:
        from invest import create_app
        app = create_app()

    from invest import db

    migrations = [
        # user_profiles — three new onboarding fields
        (
            "user_profiles", "display_name",
            "ALTER TABLE user_profiles ADD COLUMN display_name VARCHAR(50) NULL"
        ),
        (
            "user_profiles", "goal_text",
            "ALTER TABLE user_profiles ADD COLUMN goal_text VARCHAR(255) NULL"
        ),
        (
            "user_profiles", "sectors_of_interest",
            "ALTER TABLE user_profiles ADD COLUMN sectors_of_interest JSON NULL"
        ),
        # recommendations — three new structured output fields
        (
            "recommendations", "headline",
            "ALTER TABLE recommendations ADD COLUMN headline VARCHAR(255) NULL"
        ),
        (
            "recommendations", "action_plan",
            "ALTER TABLE recommendations ADD COLUMN action_plan VARCHAR(500) NULL"
        ),
        (
            "recommendations", "conviction_pct",
            "ALTER TABLE recommendations ADD COLUMN conviction_pct INT NULL"
        ),
    ]

    with app.app_context():
        with db.engine.connect() as conn:
            for table, column, sql in migrations:
                if _column_exists(conn, table, column):
                    print(f"  [SKIP]    {table}.{column} already exists")
                else:
                    conn.execute(db.text(sql))
                    conn.commit()
                    print(f"  [ADDED]   {table}.{column}")

    print("\nMigration complete.")


if __name__ == "__main__":
    run()

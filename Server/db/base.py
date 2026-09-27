from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from core.config import get_settings
from core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def apply_sqlite_compat_migrations() -> None:
    """
    Apply minimal SQLite compatibility migrations for legacy local databases.

    Note: SQLAlchemy create_all() does not alter existing tables, so we patch
    known missing columns that newer code depends on.
    """
    if "sqlite" not in settings.DATABASE_URL:
        return

    required_columns = {
        "dependencies": "TEXT",
        "architecture_patterns": "TEXT",
        "updated_at": "DATETIME",
        "project_id": "VARCHAR(64)",
        "project_name": "VARCHAR(255)",
    }

    user_profile_columns = {
        "phone_number": "VARCHAR(32)",
        "linkedin_url": "VARCHAR(512)",
        "bio": "TEXT",
    }

    with engine.begin() as conn:
        table_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='architecture_discoveries'")
        ).fetchone()

        if not table_exists:
            return

        existing_cols = {
            row[1] for row in conn.execute(text("PRAGMA table_info(architecture_discoveries)"))
        }

        for col_name, col_type in required_columns.items():
            if col_name not in existing_cols:
                conn.execute(
                    text(f"ALTER TABLE architecture_discoveries ADD COLUMN {col_name} {col_type}")
                )
                logger.info(f"[DB Migration] Added missing column architecture_discoveries.{col_name}")

        spans_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='spans'")
        ).fetchone()

        if spans_exists:
            span_existing_cols = {
                row[1] for row in conn.execute(text("PRAGMA table_info(spans)"))
            }

            if "project_id" not in span_existing_cols:
                conn.execute(text("ALTER TABLE spans ADD COLUMN project_id VARCHAR(64)"))
                logger.info("[DB Migration] Added missing column spans.project_id")

            if "attributes_json" not in span_existing_cols:
                conn.execute(text("ALTER TABLE spans ADD COLUMN attributes_json TEXT"))
                logger.info("[DB Migration] Added missing column spans.attributes_json")

            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_tenant_project_time "
                    "ON spans (tenant_id, project_id, start_time)"
                )
            )

        users_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        ).fetchone()

        if users_exists:
            user_existing_cols = {
                row[1] for row in conn.execute(text("PRAGMA table_info(users)"))
            }

            for col_name, col_type in user_profile_columns.items():
                if col_name not in user_existing_cols:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                    logger.info(f"[DB Migration] Added missing column users.{col_name}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

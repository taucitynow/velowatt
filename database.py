"""
Database connection and initialization.
Supports SQLite (local dev) and PostgreSQL (production).
Set DATABASE_URL env var for PostgreSQL.
"""

import os
from sqlmodel import SQLModel, Session, create_engine, text

# Default to SQLite for local development
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///velowatt.db")

# Railway/Render give postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite needs check_same_thread=False
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def init_db():
    """Create all tables and run migrations."""
    SQLModel.metadata.create_all(engine)
    _run_migrations()


def _run_migrations():
    """Add new columns to existing tables if they don't exist."""
    migrations = [
        ("user", "coach_messages_used", "INTEGER DEFAULT 0"),
        ("user", "coach_week_start", "DATE"),
        ("user", "is_admin", "BOOLEAN DEFAULT FALSE"),
        ("user", "strava_athlete_id", "INTEGER"),
    ]
    with Session(engine) as session:
        for table, column, col_type in migrations:
            try:
                session.exec(text(f"ALTER TABLE \"{table}\" ADD COLUMN {column} {col_type}"))
                session.commit()
            except Exception:
                session.rollback()


def get_session():
    """Get a database session."""
    with Session(engine) as session:
        yield session

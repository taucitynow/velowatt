"""
Database connection and initialization.
Supports SQLite (local dev) and PostgreSQL (production).
Set DATABASE_URL env var for PostgreSQL.
"""

import os
from sqlmodel import SQLModel, Session, create_engine

# Default to SQLite for local development
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///velowatt.db")

# Railway/Render give postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite needs check_same_thread=False
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def init_db():
    """Create all tables."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Get a database session."""
    with Session(engine) as session:
        yield session

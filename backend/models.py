"""
Database models for VeloWatt web app.
Uses SQLModel (SQLAlchemy + Pydantic combined).
Multi-user with authentication.
"""

from datetime import datetime, date
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship


# --- User & Auth ---

class User(SQLModel, table=True):
    """Registered user."""
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str = Field()
    name: str = Field(default="Cyclist")
    is_active: bool = Field(default=True)
    is_pro: bool = Field(default=False)
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Settings (inline — no separate table needed)
    ftp: float = Field(default=200.0)
    weight_kg: float = Field(default=75.0)
    resting_hr: Optional[int] = Field(default=None)
    max_hr: Optional[int] = Field(default=None)

    # Strava tokens
    strava_refresh_token: Optional[str] = Field(default=None)
    strava_access_token: Optional[str] = Field(default=None)
    strava_expires_at: Optional[int] = Field(default=None)
    strava_athlete_id: Optional[int] = Field(default=None, index=True)

    # AI Coach usage (free tier limits)
    coach_messages_used: int = Field(default=0)
    coach_week_start: Optional[date] = Field(default=None)


class UserSettings(SQLModel, table=True):
    """Legacy user settings — kept for backward compatibility during migration."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(default="Cyclist")
    ftp: float = Field(default=200.0)
    weight_kg: float = Field(default=75.0)
    resting_hr: Optional[int] = Field(default=None)
    max_hr: Optional[int] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# --- Rides ---

class Ride(SQLModel, table=True):
    """A single ride/workout record."""
    id: Optional[int] = Field(default=None, primary_key=True)

    # Owner
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)

    # Basic info
    title: str = Field(default="Ride")
    ride_date: date = Field(default_factory=date.today)
    description: Optional[str] = Field(default=None)

    # Duration
    duration_seconds: int = Field(default=0)

    # Power data
    avg_power: float = Field(default=0.0)
    normalized_power: Optional[float] = Field(default=None)
    max_power: Optional[float] = Field(default=None)
    ftp_at_time: float = Field(default=200.0)

    # Heart rate
    avg_heart_rate: Optional[float] = Field(default=None)
    max_heart_rate: Optional[int] = Field(default=None)

    # Calculated metrics
    tss: float = Field(default=0.0)
    intensity_factor: float = Field(default=0.0)
    variability_index: Optional[float] = Field(default=None)
    efficiency_factor: Optional[float] = Field(default=None)

    # Ride details
    distance_km: Optional[float] = Field(default=None)
    elevation_gain_m: Optional[float] = Field(default=None)
    avg_speed_kmh: Optional[float] = Field(default=None)
    avg_cadence: Optional[int] = Field(default=None)

    # Metadata
    ai_summary: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- Pydantic models for API requests ---

class RideCreate(SQLModel):
    """Schema for creating a new ride via API."""
    title: str = "Ride"
    ride_date: date = Field(default_factory=date.today)
    description: Optional[str] = None
    duration_seconds: int
    avg_power: float
    normalized_power: Optional[float] = None
    max_power: Optional[float] = None
    avg_heart_rate: Optional[float] = None
    max_heart_rate: Optional[int] = None
    distance_km: Optional[float] = None
    elevation_gain_m: Optional[float] = None
    avg_speed_kmh: Optional[float] = None
    avg_cadence: Optional[int] = None


class UserSettingsUpdate(SQLModel):
    """Schema for updating user settings."""
    name: Optional[str] = None
    ftp: Optional[float] = None
    weight_kg: Optional[float] = None
    resting_hr: Optional[int] = None
    max_hr: Optional[int] = None


class UserRegister(SQLModel):
    """Registration schema."""
    email: str
    password: str
    name: str = "Cyclist"


class UserLogin(SQLModel):
    """Login schema."""
    email: str
    password: str

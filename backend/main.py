"""
VeloWatt API — Web Backend

Multi-user cycling performance analytics platform.
FastAPI + PostgreSQL + JWT Auth.
"""

import os
import sys
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Optional
from collections import defaultdict

# Ensure local modules are importable
sys.path.insert(0, str(Path(__file__).parent))

# Load .env for local development
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from database import init_db, get_session, engine
from models import (
    User, UserRegister, UserLogin,
    Ride, RideCreate,
    UserSettings, UserSettingsUpdate,
)
from auth import (
    hash_password, verify_password, create_access_token,
    get_current_user,
)
from metrics import (
    calculate_ride_metrics,
    calculate_normalized_power,
    calculate_tss_simple,
    calculate_ctl,
    calculate_atl,
    calculate_tsb,
    get_power_zones,
)
from fit_parser import parse_fit_bytes, fit_data_to_ride_dict

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:8000,http://localhost:3000,https://velowatt.app").split(",")

app = FastAPI(title="VeloWatt API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


# ═══════════════════════════════════════
# AUTH ENDPOINTS
# ═══════════════════════════════════════

@app.post("/auth/register")
def register(data: UserRegister, session: Session = Depends(get_session)):
    """Register a new user."""
    # Check if email already exists
    existing = session.exec(select(User).where(User.email == data.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=data.email.lower().strip(),
        password_hash=hash_password(data.password),
        name=data.name,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    token = create_access_token(user.id, user.email)
    return {
        "token": token,
        "user": {"id": user.id, "email": user.email, "name": user.name},
    }


@app.post("/auth/login")
def login(data: UserLogin, session: Session = Depends(get_session)):
    """Login and get JWT token."""
    user = session.exec(select(User).where(User.email == data.email.lower().strip())).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id, user.email)
    return {
        "token": token,
        "user": {"id": user.id, "email": user.email, "name": user.name},
    }


@app.get("/auth/me")
def get_me(user: User = Depends(get_current_user)):
    """Get current user info."""
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "ftp": user.ftp,
        "weight_kg": user.weight_kg,
        "is_pro": user.is_pro,
        "created_at": user.created_at.isoformat(),
    }


# ═══════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════

@app.get("/api/settings")
def get_settings(user: User = Depends(get_current_user)):
    return {
        "name": user.name,
        "ftp": user.ftp,
        "weight_kg": user.weight_kg,
        "resting_hr": user.resting_hr,
        "max_hr": user.max_hr,
    }


@app.put("/api/settings")
def update_settings(
    data: UserSettingsUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if data.name is not None:
        user.name = data.name
    if data.ftp is not None:
        user.ftp = data.ftp
    if data.weight_kg is not None:
        user.weight_kg = data.weight_kg
    if data.resting_hr is not None:
        user.resting_hr = data.resting_hr
    if data.max_hr is not None:
        user.max_hr = data.max_hr
    session.add(user)
    session.commit()
    return {"message": "Settings updated", "ftp": user.ftp}


# ═══════════════════════════════════════
# RECALCULATE
# ═══════════════════════════════════════

@app.post("/api/recalculate")
def recalculate_all_rides(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    ftp = user.ftp
    rides = session.exec(
        select(Ride).where(Ride.user_id == user.id).order_by(Ride.ride_date)
    ).all()

    updated = 0
    for ride in rides:
        np_val = ride.normalized_power or ride.avg_power
        metrics = calculate_ride_metrics(
            duration_seconds=ride.duration_seconds,
            avg_power=ride.avg_power,
            ftp=ftp,
            normalized_power=np_val,
            avg_heart_rate=ride.avg_heart_rate,
        )
        ride.tss = metrics["tss"]
        ride.intensity_factor = metrics["intensity_factor"]
        ride.variability_index = metrics.get("variability_index")
        ride.efficiency_factor = metrics.get("efficiency_factor")
        ride.ftp_at_time = ftp
        session.add(ride)
        updated += 1

    session.commit()
    return {"rides_updated": updated, "ftp_used": ftp}


# ═══════════════════════════════════════
# RIDES
# ═══════════════════════════════════════

@app.post("/api/rides")
def create_ride(
    ride_data: RideCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    ftp = user.ftp
    metrics = calculate_ride_metrics(
        duration_seconds=ride_data.duration_seconds,
        avg_power=ride_data.avg_power,
        ftp=ftp,
        normalized_power=ride_data.normalized_power,
        avg_heart_rate=ride_data.avg_heart_rate,
    )

    ride = Ride(
        user_id=user.id,
        title=ride_data.title,
        ride_date=ride_data.ride_date,
        description=ride_data.description,
        duration_seconds=ride_data.duration_seconds,
        avg_power=ride_data.avg_power,
        normalized_power=metrics["normalized_power"],
        max_power=ride_data.max_power,
        ftp_at_time=ftp,
        avg_heart_rate=ride_data.avg_heart_rate,
        max_heart_rate=ride_data.max_heart_rate,
        tss=metrics["tss"],
        intensity_factor=metrics["intensity_factor"],
        variability_index=metrics.get("variability_index"),
        efficiency_factor=metrics.get("efficiency_factor"),
        distance_km=ride_data.distance_km,
        elevation_gain_m=ride_data.elevation_gain_m,
        avg_speed_kmh=ride_data.avg_speed_kmh,
        avg_cadence=ride_data.avg_cadence,
    )
    session.add(ride)
    session.commit()
    session.refresh(ride)
    return {**ride.dict(), **metrics}


@app.get("/api/rides")
def list_rides(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    rides = session.exec(
        select(Ride)
        .where(Ride.user_id == user.id)
        .order_by(Ride.ride_date.desc())
        .offset(offset).limit(limit)
    ).all()
    return rides


@app.get("/api/rides/{ride_id}")
def get_ride(
    ride_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    ride = session.get(Ride, ride_id)
    if not ride or ride.user_id != user.id:
        raise HTTPException(status_code=404, detail="Ride not found")
    return ride


@app.delete("/api/rides/{ride_id}")
def delete_ride(
    ride_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    ride = session.get(Ride, ride_id)
    if not ride or ride.user_id != user.id:
        raise HTTPException(status_code=404, detail="Ride not found")
    session.delete(ride)
    session.commit()
    return {"message": "Ride deleted", "id": ride_id}


# ═══════════════════════════════════════
# AI RIDE ANALYSIS
# ═══════════════════════════════════════

def _get_api_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY", "")


def generate_ride_analysis(ride: Ride, user: User, session: Session) -> Optional[str]:
    """Generate AI analysis for a ride."""
    api_key = _get_api_key()
    if not api_key:
        return None

    ftp = user.ftp

    recent = session.exec(
        select(Ride)
        .where(Ride.user_id == user.id)
        .where(Ride.ride_date <= ride.ride_date)
        .where(Ride.id != ride.id)
        .order_by(Ride.ride_date.desc())
        .limit(7)
    ).all()

    all_rides = session.exec(
        select(Ride)
        .where(Ride.user_id == user.id)
        .where(Ride.ride_date <= ride.ride_date)
        .order_by(Ride.ride_date)
    ).all()

    daily_tss: dict = {}
    for r in all_rides:
        if r.ride_date in daily_tss:
            daily_tss[r.ride_date] += r.tss
        else:
            daily_tss[r.ride_date] = r.tss

    ctl = 0.0
    atl = 0.0
    if all_rides:
        current = all_rides[0].ride_date
        while current <= ride.ride_date:
            day_tss = daily_tss.get(current, 0.0)
            ctl = ctl + (day_tss - ctl) / 42
            atl = atl + (day_tss - atl) / 7
            current += timedelta(days=1)
    tsb = ctl - atl

    recent_lines = []
    for r in recent[:5]:
        recent_lines.append(f"  {r.ride_date} | {r.title} | {r.duration_seconds//60}min | Avg {r.avg_power}W | TSS {r.tss}")

    if_val = ride.intensity_factor
    if if_val < 0.55:
        zone_name = "Recovery"
    elif if_val < 0.75:
        zone_name = "Endurance"
    elif if_val < 0.90:
        zone_name = "Tempo"
    elif if_val < 1.05:
        zone_name = "Threshold"
    elif if_val < 1.20:
        zone_name = "VO2max"
    else:
        zone_name = "Anaerobic"

    prompt = f"""Analyze this cycling workout in 2-3 sentences. Be specific, data-driven, and coaching-oriented.

RIDE:
  Title: {ride.title}
  Date: {ride.ride_date}
  Duration: {ride.duration_seconds // 60}min
  Avg Power: {ride.avg_power}W | NP: {ride.normalized_power or 'N/A'}W | Max: {ride.max_power or 'N/A'}W
  TSS: {ride.tss} | IF: {ride.intensity_factor} | Zone: {zone_name}
  HR: avg {ride.avg_heart_rate or 'N/A'} / max {ride.max_heart_rate or 'N/A'}
  Distance: {ride.distance_km or 'N/A'}km | Elevation: {ride.elevation_gain_m or 'N/A'}m
  FTP: {ftp}W

CURRENT FITNESS:
  CTL: {round(ctl, 1)} | ATL: {round(atl, 1)} | TSB: {round(tsb, 1)}

RECENT TRAINING:
{chr(10).join(recent_lines) if recent_lines else '  No recent rides'}

Give a brief, insightful analysis: what was the purpose of this ride, how it fits the recent training pattern, and one actionable suggestion. Keep it to 2-3 sentences max."""

    try:
        import httpx
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 200,
                "system": "You are VeloWatt AI Coach — a concise cycling performance analyst. Respond with 2-3 sentences only.",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        if response.status_code == 200:
            return response.json()["content"][0]["text"]
    except Exception:
        pass
    return None


@app.post("/api/rides/{ride_id}/analyze")
def analyze_ride(
    ride_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    ride = session.get(Ride, ride_id)
    if not ride or ride.user_id != user.id:
        raise HTTPException(status_code=404, detail="Ride not found")

    if ride.ai_summary:
        return {"ride_id": ride_id, "analysis": ride.ai_summary, "cached": True}

    analysis = generate_ride_analysis(ride, user, session)
    if analysis:
        ride.ai_summary = analysis
        session.add(ride)
        session.commit()
        return {"ride_id": ride_id, "analysis": analysis, "cached": False}
    return {"ride_id": ride_id, "analysis": None, "error": "AI analysis unavailable"}


@app.post("/api/rides/analyze-latest")
def analyze_latest_ride(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    ride = session.exec(
        select(Ride)
        .where(Ride.user_id == user.id)
        .order_by(Ride.created_at.desc())
        .limit(1)
    ).first()
    if not ride:
        return {"analysis": None, "error": "No rides found"}

    if ride.ai_summary:
        return {"ride_id": ride.id, "title": ride.title, "analysis": ride.ai_summary, "cached": True}

    analysis = generate_ride_analysis(ride, user, session)
    if analysis:
        ride.ai_summary = analysis
        session.add(ride)
        session.commit()
        return {"ride_id": ride.id, "title": ride.title, "analysis": analysis, "cached": False}
    return {"ride_id": ride.id, "title": ride.title, "analysis": None, "error": "AI unavailable"}


# ═══════════════════════════════════════
# FITNESS (CTL/ATL/TSB)
# ═══════════════════════════════════════

@app.get("/api/fitness")
def get_fitness(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    rides = session.exec(
        select(Ride)
        .where(Ride.user_id == user.id)
        .order_by(Ride.ride_date)
    ).all()

    if not rides:
        return {
            "current_ctl": 0, "current_atl": 0, "current_tsb": 0,
            "peak_ctl": 0, "history": [], "forecast": [],
        }

    daily_tss: dict = {}
    for ride in rides:
        if ride.ride_date in daily_tss:
            daily_tss[ride.ride_date] += ride.tss
        else:
            daily_tss[ride.ride_date] = ride.tss

    start = rides[0].ride_date
    end = max(date.today(), rides[-1].ride_date)

    ctl = 0.0
    atl = 0.0
    peak_ctl = 0.0
    history = []

    current = start
    while current <= end:
        day_tss = daily_tss.get(current, 0.0)
        ctl = ctl + (day_tss - ctl) / 42
        atl = atl + (day_tss - atl) / 7
        tsb = ctl - atl
        peak_ctl = max(peak_ctl, ctl)
        history.append({
            "date": current.isoformat(),
            "ctl": round(ctl, 1),
            "atl": round(atl, 1),
            "tsb": round(tsb, 1),
        })
        current += timedelta(days=1)

    # 30-day forecast
    forecast = []
    fc_ctl, fc_atl = ctl, atl
    for i in range(1, 31):
        fc_ctl = fc_ctl + (0 - fc_ctl) / 42
        fc_atl = fc_atl + (0 - fc_atl) / 7
        fc_tsb = fc_ctl - fc_atl
        forecast.append({
            "date": (end + timedelta(days=i)).isoformat(),
            "ctl": round(fc_ctl, 1),
            "atl": round(fc_atl, 1),
            "tsb": round(fc_tsb, 1),
        })

    return {
        "current_ctl": round(ctl, 1),
        "current_atl": round(atl, 1),
        "current_tsb": round(ctl - atl, 1),
        "peak_ctl": round(peak_ctl, 1),
        "history": history,
        "forecast": forecast,
    }


# ═══════════════════════════════════════
# ZONES
# ═══════════════════════════════════════

@app.get("/api/zones")
def get_zones(user: User = Depends(get_current_user)):
    return {"ftp": user.ftp, "zones": get_power_zones(user.ftp)}


# ═══════════════════════════════════════
# FTP ESTIMATE
# ═══════════════════════════════════════

@app.get("/api/ftp-estimate")
def ftp_estimate(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    rides_with_np = session.exec(
        select(Ride)
        .where(Ride.user_id == user.id)
        .where(Ride.normalized_power != None)
        .where(Ride.normalized_power > 0)
        .order_by(Ride.ride_date)
    ).all()

    if not rides_with_np:
        return {"estimated_ftp": None, "method": "no data"}

    long_rides = [r for r in rides_with_np if r.duration_seconds >= 2400]
    if long_rides:
        best_np = max(r.normalized_power for r in long_rides)
        est_ftp = round(best_np * 0.95, 1)
        return {"estimated_ftp": est_ftp, "method": "95% of best 40min+ NP"}

    best_np = max(r.normalized_power for r in rides_with_np)
    est_ftp = round(best_np * 0.90, 1)
    return {"estimated_ftp": est_ftp, "method": "90% of best NP (short rides)"}


# ═══════════════════════════════════════
# FIT FILE IMPORT
# ═══════════════════════════════════════

@app.post("/api/import/fit")
async def import_fit(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    contents = await file.read()
    fit_data = parse_fit_bytes(contents)

    if not fit_data.power_data or fit_data.avg_power == 0:
        raise HTTPException(status_code=400, detail="No power data in FIT file")

    ftp = user.ftp
    np_value = None
    if len(fit_data.power_data) >= 30:
        np_value = calculate_normalized_power(
            fit_data.power_data, sample_rate_seconds=fit_data.sample_rate_seconds
        )

    metrics = calculate_ride_metrics(
        duration_seconds=fit_data.duration_seconds,
        avg_power=fit_data.avg_power,
        ftp=ftp,
        normalized_power=np_value,
        avg_heart_rate=fit_data.avg_heart_rate,
    )

    ride_dict = fit_data_to_ride_dict(fit_data)

    ride = Ride(
        user_id=user.id,
        title=ride_dict.get("title", "Imported Ride"),
        ride_date=date.fromisoformat(ride_dict["ride_date"]),
        description=f"fit_import | {fit_data.device_manufacturer or ''} {fit_data.device_name or ''}",
        duration_seconds=fit_data.duration_seconds,
        avg_power=fit_data.avg_power,
        normalized_power=metrics["normalized_power"],
        max_power=fit_data.max_power,
        ftp_at_time=ftp,
        avg_heart_rate=fit_data.avg_heart_rate,
        max_heart_rate=fit_data.max_heart_rate,
        tss=metrics["tss"],
        intensity_factor=metrics["intensity_factor"],
        variability_index=metrics.get("variability_index"),
        efficiency_factor=metrics.get("efficiency_factor"),
        distance_km=fit_data.distance_km,
        elevation_gain_m=fit_data.elevation_gain_m,
        avg_speed_kmh=fit_data.avg_speed_kmh,
        avg_cadence=fit_data.avg_cadence,
    )
    session.add(ride)
    session.commit()
    session.refresh(ride)

    # Auto-analyze
    try:
        analysis = generate_ride_analysis(ride, user, session)
        if analysis:
            ride.ai_summary = analysis
            session.add(ride)
            session.commit()
    except Exception:
        pass

    return {**ride.dict(), **metrics, "ai_summary": ride.ai_summary}


# ═══════════════════════════════════════
# STRAVA SYNC
# ═══════════════════════════════════════

@app.get("/api/strava/status")
def strava_status(user: User = Depends(get_current_user)):
    client_id = os.environ.get("STRAVA_CLIENT_ID", "")
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        return {"configured": False, "connected": False, "message": "Strava not configured"}

    if not user.strava_refresh_token:
        return {"configured": True, "connected": False, "message": "Click Connect Strava to authorize"}

    return {"configured": True, "connected": True, "message": "Connected to Strava"}


@app.get("/api/strava/auth-url")
def strava_auth_url(user: User = Depends(get_current_user)):
    """Return Strava OAuth URL for frontend to open."""
    client_id = os.environ.get("STRAVA_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(status_code=400, detail="STRAVA_CLIENT_ID not configured")

    base_url = os.environ.get("BASE_URL", "https://velowatt.app")
    redirect_uri = f"{base_url}/api/strava/callback"

    url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&approval_prompt=auto"
        f"&scope=read,activity:read_all"
        f"&state={user.id}"
    )
    return {"url": url}


@app.get("/api/strava/callback")
def strava_callback(
    code: str,
    state: str = "",
    session: Session = Depends(get_session),
):
    """Handle Strava OAuth callback."""
    import httpx

    client_id = os.environ.get("STRAVA_CLIENT_ID", "")
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET", "")

    # Exchange code for tokens
    resp = httpx.post("https://www.strava.com/oauth/token", data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
    }, timeout=30)
    resp.raise_for_status()
    tokens = resp.json()

    # Save tokens to user
    user_id = int(state) if state else None
    if user_id:
        user = session.get(User, user_id)
        if user:
            user.strava_access_token = tokens["access_token"]
            user.strava_refresh_token = tokens["refresh_token"]
            user.strava_expires_at = tokens["expires_at"]
            session.add(user)
            session.commit()

    # Return success HTML
    from fastapi.responses import HTMLResponse
    return HTMLResponse(
        "<html><body style='font-family:Arial;text-align:center;padding:60px;background:#1a1a2e;color:#e6e6e6'>"
        "<h1 style='color:#16a34a'>⚡ VeloWatt Connected!</h1>"
        "<p>Strava authorization successful. You can close this window.</p>"
        "</body></html>"
    )


def _get_strava_token(user: User, session: Session) -> Optional[str]:
    """Get valid Strava access token, refreshing if needed."""
    import httpx
    import time

    if not user.strava_refresh_token:
        return None

    # Check if token is still valid
    if user.strava_access_token and user.strava_expires_at and user.strava_expires_at > time.time():
        return user.strava_access_token

    # Refresh
    client_id = os.environ.get("STRAVA_CLIENT_ID", "")
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET", "")

    try:
        resp = httpx.post("https://www.strava.com/oauth/token", data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": user.strava_refresh_token,
            "grant_type": "refresh_token",
        }, timeout=30)
        resp.raise_for_status()
        tokens = resp.json()

        user.strava_access_token = tokens["access_token"]
        user.strava_refresh_token = tokens["refresh_token"]
        user.strava_expires_at = tokens["expires_at"]
        session.add(user)
        session.commit()

        return tokens["access_token"]
    except Exception:
        return None


@app.post("/api/strava/sync")
def strava_sync(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    limit: int = 50,
):
    import httpx

    access_token = _get_strava_token(user, session)
    if not access_token:
        raise HTTPException(status_code=401, detail="Not connected to Strava")

    ftp = user.ftp

    # Get already imported strava IDs
    user_rides = session.exec(select(Ride).where(Ride.user_id == user.id)).all()
    already_imported = set()
    for r in user_rides:
        if r.description and "strava_id:" in r.description:
            try:
                sid = r.description.split("strava_id:")[1].split("|")[0].strip()
                already_imported.add(int(sid))
            except (ValueError, IndexError):
                pass

    # Fetch activities
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"page": 1, "per_page": limit},
        )
        resp.raise_for_status()
        activities = resp.json()

    imported = []
    skipped = []
    errors = []

    for act in activities:
        sport = act.get("sport_type", act.get("type", ""))
        if sport.lower() not in ("ride", "cycling", "virtualride", "ebikeride", "gravelride", "mountainbikeride"):
            continue

        act_id = act["id"]
        if act_id in already_imported:
            skipped.append({"name": act.get("name"), "reason": "already imported"})
            continue

        if not act.get("device_watts") or not act.get("average_watts"):
            skipped.append({"name": act.get("name"), "reason": "no power data"})
            continue

        try:
            # Get power stream for NP
            np_value = None
            try:
                stream_resp = httpx.get(
                    f"https://www.strava.com/api/v3/activities/{act_id}/streams",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"keys": "watts", "key_by_type": "true"},
                    timeout=30,
                )
                if stream_resp.status_code == 200:
                    stream_data = stream_resp.json()
                    if isinstance(stream_data, dict) and "watts" in stream_data:
                        power_data = [float(w) for w in stream_data["watts"].get("data", [])]
                        if len(power_data) >= 30:
                            np_value = calculate_normalized_power(power_data)
            except Exception:
                pass

            metrics = calculate_ride_metrics(
                duration_seconds=int(act.get("moving_time", 0)),
                avg_power=act.get("average_watts", 0),
                ftp=ftp,
                normalized_power=np_value,
                avg_heart_rate=act.get("average_heartrate"),
            )

            ride_date = None
            if act.get("start_date_local"):
                try:
                    ride_date = datetime.fromisoformat(act["start_date_local"].replace("Z", "+00:00")).date()
                except Exception:
                    pass

            distance_km = round(act.get("distance", 0) / 1000, 2)
            avg_speed = act.get("average_speed")
            avg_speed_kmh = round(avg_speed * 3.6, 1) if avg_speed else None

            ride = Ride(
                user_id=user.id,
                title=act.get("name", "Ride"),
                ride_date=ride_date or date.today(),
                description=f"strava_id:{act_id} | {act.get('device_name', 'Strava')}",
                duration_seconds=int(act.get("moving_time", 0)),
                avg_power=act.get("average_watts", 0),
                normalized_power=metrics["normalized_power"],
                max_power=act.get("max_watts"),
                ftp_at_time=ftp,
                avg_heart_rate=act.get("average_heartrate"),
                max_heart_rate=act.get("max_heartrate"),
                tss=metrics["tss"],
                intensity_factor=metrics["intensity_factor"],
                variability_index=metrics.get("variability_index"),
                efficiency_factor=metrics.get("efficiency_factor"),
                distance_km=distance_km,
                elevation_gain_m=act.get("total_elevation_gain", 0),
                avg_speed_kmh=avg_speed_kmh,
                avg_cadence=int(act["average_cadence"]) if act.get("average_cadence") else None,
            )
            session.add(ride)
            session.commit()

            imported.append({
                "name": act.get("name"),
                "date": ride_date.isoformat() if ride_date else "",
                "tss": metrics["tss"],
                "np": metrics["normalized_power"],
            })
        except Exception as e:
            errors.append({"name": act.get("name"), "error": str(e)})

    # Auto-analyze latest
    latest_analysis = None
    if imported:
        try:
            latest_ride = session.exec(
                select(Ride).where(Ride.user_id == user.id).order_by(Ride.created_at.desc()).limit(1)
            ).first()
            if latest_ride:
                analysis = generate_ride_analysis(latest_ride, user, session)
                if analysis:
                    latest_ride.ai_summary = analysis
                    session.add(latest_ride)
                    session.commit()
                    latest_analysis = {"ride": latest_ride.title, "analysis": analysis}
        except Exception:
            pass

    return {
        "total_found": len(activities),
        "imported": len(imported),
        "skipped": len(skipped),
        "errors": len(errors),
        "imported_rides": imported,
        "skipped_rides": skipped,
        "error_details": errors,
        "ai_analysis": latest_analysis,
    }


# ═══════════════════════════════════════
# AI COACH CHAT
# ═══════════════════════════════════════

from pydantic import BaseModel


class ChatMessage(BaseModel):
    message: str
    history: list[dict] = []


@app.post("/api/coach/chat")
def coach_chat(
    msg: ChatMessage,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    api_key = _get_api_key()
    if not api_key:
        return {"response": "AI Coach is not configured. Contact admin.", "needs_api_key": True}

    ftp = user.ftp
    weight = user.weight_kg

    recent_rides = session.exec(
        select(Ride).where(Ride.user_id == user.id).order_by(Ride.ride_date.desc()).limit(20)
    ).all()

    all_rides = session.exec(
        select(Ride).where(Ride.user_id == user.id).order_by(Ride.ride_date)
    ).all()

    # Calculate CTL/ATL
    daily_tss: dict = {}
    for ride in all_rides:
        if ride.ride_date in daily_tss:
            daily_tss[ride.ride_date] += ride.tss
        else:
            daily_tss[ride.ride_date] = ride.tss

    ctl = 0.0
    atl = 0.0
    if all_rides:
        current = all_rides[0].ride_date
        end = max(date.today(), all_rides[-1].ride_date)
        while current <= end:
            day_tss = daily_tss.get(current, 0.0)
            ctl = ctl + (day_tss - ctl) / 42
            atl = atl + (day_tss - atl) / 7
            current += timedelta(days=1)
    tsb = ctl - atl

    ride_lines = []
    for r in recent_rides[:15]:
        ride_lines.append(
            f"  {r.ride_date} | {r.title} | {r.duration_seconds//60}min | "
            f"Avg {r.avg_power}W | NP {r.normalized_power}W | TSS {r.tss} | IF {r.intensity_factor}"
        )

    weekly_tss = defaultdict(float)
    for r in all_rides:
        week_start = r.ride_date - timedelta(days=r.ride_date.weekday())
        weekly_tss[week_start] += r.tss
    sorted_weeks = sorted(weekly_tss.items(), reverse=True)[:4]
    week_lines = [f"  Week of {w[0]}: TSS {round(w[1])}" for w in sorted_weeks]

    context = f"""You are VeloWatt AI Coach for {user.name}.

ATHLETE PROFILE:
  FTP: {ftp}W | Weight: {weight}kg | W/kg: {round(ftp/weight, 2)}

CURRENT FITNESS:
  CTL (Fitness): {round(ctl, 1)}
  ATL (Fatigue): {round(atl, 1)}
  TSB (Form): {round(tsb, 1)}
  Total rides: {len(all_rides)}

RECENT RIDES:
{chr(10).join(ride_lines) if ride_lines else '  No rides yet'}

WEEKLY TSS:
{chr(10).join(week_lines) if week_lines else '  No data'}

POWER ZONES (FTP={ftp}W):
  Z1 Recovery: <{round(ftp*0.55)}W | Z2 Endurance: {round(ftp*0.55)}-{round(ftp*0.75)}W
  Z3 Tempo: {round(ftp*0.75)}-{round(ftp*0.90)}W | Z4 Threshold: {round(ftp*0.90)}-{round(ftp*1.05)}W
  Z5 VO2max: {round(ftp*1.05)}-{round(ftp*1.20)}W | Z6 Anaerobic: >{round(ftp*1.20)}W

SCOPE: Only cycling and endurance sports coaching. Politely redirect off-topic questions."""

    messages = []
    for h in msg.history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": msg.message})

    try:
        import httpx
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1024,
                "system": context,
                "messages": messages,
            },
            timeout=60,
        )
        if response.status_code == 200:
            reply = response.json()["content"][0]["text"]
            return {"response": reply, "needs_api_key": False}
        else:
            error = response.json().get("error", {}).get("message", response.text)
            return {"response": f"API Error: {error}", "needs_api_key": False}
    except Exception as e:
        return {"response": f"Error: {str(e)}", "needs_api_key": False}


# ═══════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════

@app.get("/api/health")
def health():
    return {"status": "ok", "app": "VeloWatt", "version": "1.0.0"}


# ═══════════════════════════════════════
# FRONTEND — Serve static HTML
# ═══════════════════════════════════════

from fastapi.responses import FileResponse

@app.get("/")
def serve_frontend():
    static_path = Path(__file__).parent / "static" / "index.html"
    if static_path.exists():
        return FileResponse(static_path, media_type="text/html")
    return {"message": "VeloWatt API", "docs": "/docs"}

"""
Garmin .FIT File Parser

Extracts ride data from Garmin .FIT files:
- Second-by-second power data (for accurate NP calculation)
- Heart rate, cadence, speed, altitude
- GPS coordinates
- Lap summaries
- Session totals

Uses the `fitparse` library (pip install fitparse)

Supported Garmin devices: Edge series, Forerunner, Fenix, etc.
Also works with .FIT files exported from Wahoo, Hammerhead, etc.
"""

from datetime import datetime, date, timedelta
from typing import Optional
from dataclasses import dataclass, field

from fitparse import FitFile


@dataclass
class FitRecord:
    """A single data point from the ride (typically 1-second interval)."""
    timestamp: Optional[datetime] = None
    power: Optional[float] = None
    heart_rate: Optional[int] = None
    cadence: Optional[int] = None
    speed: Optional[float] = None          # m/s
    altitude: Optional[float] = None       # meters
    distance: Optional[float] = None       # meters (cumulative)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    temperature: Optional[float] = None    # Celsius


@dataclass
class FitLap:
    """Summary data for a single lap."""
    start_time: Optional[datetime] = None
    duration_seconds: float = 0
    distance_m: float = 0
    avg_power: float = 0
    max_power: float = 0
    avg_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None
    avg_cadence: Optional[int] = None
    avg_speed: Optional[float] = None


@dataclass
class FitRideData:
    """Complete parsed ride data from a .FIT file."""
    # Session info
    sport: str = "cycling"
    start_time: Optional[datetime] = None
    ride_date: Optional[date] = None
    
    # Totals
    duration_seconds: int = 0
    distance_km: float = 0
    elevation_gain_m: float = 0
    calories: int = 0
    
    # Averages
    avg_power: float = 0
    max_power: float = 0
    avg_heart_rate: Optional[float] = None
    max_heart_rate: Optional[int] = None
    avg_cadence: Optional[int] = None
    avg_speed_kmh: Optional[float] = None
    
    # Raw data for NP calculation
    power_data: list[float] = field(default_factory=list)
    heart_rate_data: list[int] = field(default_factory=list)
    
    # Detailed records and laps
    records: list[FitRecord] = field(default_factory=list)
    laps: list[FitLap] = field(default_factory=list)
    
    # Sample rate (seconds between records)
    sample_rate_seconds: int = 1
    
    # Source info
    device_name: Optional[str] = None
    device_manufacturer: Optional[str] = None


def parse_fit_file(file_path: str) -> FitRideData:
    """
    Parse a .FIT file and extract all ride data.
    
    Args:
        file_path: Path to the .FIT file
    
    Returns:
        FitRideData with all extracted data
    """
    fitfile = FitFile(file_path)
    return _parse_fitfile(fitfile)


def _parse_fitfile(fitfile) -> FitRideData:
    """Parse a FitFile object and extract all ride data."""
    ride = FitRideData()
    
    records = []
    timestamps = []
    
    for record in fitfile.get_messages():
        msg_type = record.name
        
        if msg_type == "record":
            rec = _parse_record(record)
            if rec:
                records.append(rec)
                if rec.power is not None:
                    ride.power_data.append(rec.power)
                else:
                    ride.power_data.append(0.0)
                if rec.heart_rate is not None:
                    ride.heart_rate_data.append(rec.heart_rate)
                if rec.timestamp:
                    timestamps.append(rec.timestamp)
        
        elif msg_type == "lap":
            lap = _parse_lap(record)
            if lap:
                ride.laps.append(lap)
        
        elif msg_type == "session":
            _parse_session(record, ride)
        
        elif msg_type == "device_info":
            _parse_device_info(record, ride)
    
    ride.records = records
    
    # Determine sample rate from timestamps
    if len(timestamps) >= 2:
        deltas = []
        for i in range(1, min(20, len(timestamps))):
            dt = (timestamps[i] - timestamps[i-1]).total_seconds()
            if 0 < dt <= 10:  # Reasonable range
                deltas.append(dt)
        if deltas:
            ride.sample_rate_seconds = max(1, round(sum(deltas) / len(deltas)))
    
    # If session data is missing, calculate from records
    if ride.duration_seconds == 0 and len(timestamps) >= 2:
        ride.duration_seconds = int((timestamps[-1] - timestamps[0]).total_seconds())
    
    if ride.start_time is None and timestamps:
        ride.start_time = timestamps[0]
        ride.ride_date = timestamps[0].date()
    
    if ride.avg_power == 0 and ride.power_data:
        non_zero = [p for p in ride.power_data if p > 0]
        ride.avg_power = round(sum(non_zero) / len(non_zero), 1) if non_zero else 0
    
    if ride.max_power == 0 and ride.power_data:
        ride.max_power = max(ride.power_data)
    
    if ride.avg_heart_rate is None and ride.heart_rate_data:
        ride.avg_heart_rate = round(sum(ride.heart_rate_data) / len(ride.heart_rate_data), 1)
    
    if ride.max_heart_rate is None and ride.heart_rate_data:
        ride.max_heart_rate = max(ride.heart_rate_data)
    
    # Calculate elevation gain from altitude data
    if ride.elevation_gain_m == 0:
        altitudes = [r.altitude for r in records if r.altitude is not None]
        if altitudes:
            gain = 0
            for i in range(1, len(altitudes)):
                diff = altitudes[i] - altitudes[i-1]
                if diff > 0:
                    gain += diff
            ride.elevation_gain_m = round(gain, 1)
    
    return ride


def parse_fit_bytes(file_bytes: bytes) -> FitRideData:
    """
    Parse .FIT file from bytes (for file upload handling).
    
    Args:
        file_bytes: Raw bytes of the .FIT file
    
    Returns:
        FitRideData with all extracted data
    """
    import os
    import io
    
    # Try parsing directly from BytesIO first (avoids temp file issues on Windows)
    try:
        fitfile = FitFile(io.BytesIO(file_bytes))
        fitfile.parse()
        return _parse_fitfile(fitfile)
    except Exception:
        pass
    
    # Fallback: write to a regular file in the current directory
    tmp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"_temp_import.fit")
    try:
        with open(tmp_path, "wb") as f:
            f.write(file_bytes)
        return parse_fit_file(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _parse_record(record) -> Optional[FitRecord]:
    """Parse a single data record message."""
    data = _get_values(record)
    if not data:
        return None
    
    rec = FitRecord()
    rec.timestamp = data.get("timestamp")
    rec.power = data.get("power")
    rec.heart_rate = data.get("heart_rate")
    rec.cadence = data.get("cadence")
    rec.speed = data.get("speed")  # Enhanced speed or speed
    if rec.speed is None:
        rec.speed = data.get("enhanced_speed")
    rec.altitude = data.get("altitude")
    if rec.altitude is None:
        rec.altitude = data.get("enhanced_altitude")
    rec.distance = data.get("distance")
    rec.temperature = data.get("temperature")
    
    # GPS â€” fitparse stores as semicircles, convert to degrees
    lat = data.get("position_lat")
    lon = data.get("position_long")
    if lat is not None and lon is not None:
        rec.latitude = lat * (180.0 / 2**31) if isinstance(lat, int) else lat
        rec.longitude = lon * (180.0 / 2**31) if isinstance(lon, int) else lon
    
    return rec


def _parse_lap(record) -> Optional[FitLap]:
    """Parse a lap summary message."""
    data = _get_values(record)
    if not data:
        return None
    
    lap = FitLap()
    lap.start_time = data.get("start_time")
    lap.duration_seconds = data.get("total_timer_time", 0)
    lap.distance_m = data.get("total_distance", 0)
    lap.avg_power = data.get("avg_power", 0)
    lap.max_power = data.get("max_power", 0)
    lap.avg_heart_rate = data.get("avg_heart_rate")
    lap.max_heart_rate = data.get("max_heart_rate")
    lap.avg_cadence = data.get("avg_cadence")
    
    speed = data.get("avg_speed") or data.get("enhanced_avg_speed")
    if speed:
        lap.avg_speed = speed
    
    return lap


def _parse_session(record, ride: FitRideData):
    """Parse session summary message (overall ride totals)."""
    data = _get_values(record)
    if not data:
        return
    
    ride.sport = data.get("sport", "cycling")
    ride.start_time = data.get("start_time")
    if ride.start_time:
        ride.ride_date = ride.start_time.date()
    
    ride.duration_seconds = int(data.get("total_timer_time", 0))
    
    distance_m = data.get("total_distance", 0)
    ride.distance_km = round(distance_m / 1000, 2) if distance_m else 0
    
    ride.elevation_gain_m = data.get("total_ascent", 0) or 0
    ride.calories = data.get("total_calories", 0) or 0
    
    ride.avg_power = data.get("avg_power", 0) or 0
    ride.max_power = data.get("max_power", 0) or 0
    ride.avg_heart_rate = data.get("avg_heart_rate")
    ride.max_heart_rate = data.get("max_heart_rate")
    ride.avg_cadence = data.get("avg_cadence")
    
    speed = data.get("avg_speed") or data.get("enhanced_avg_speed")
    if speed:
        ride.avg_speed_kmh = round(speed * 3.6, 1)  # m/s to km/h


def _parse_device_info(record, ride: FitRideData):
    """Parse device info message."""
    data = _get_values(record)
    if not data:
        return
    
    manufacturer = data.get("manufacturer")
    product_name = data.get("product_name") or data.get("garmin_product")
    
    if manufacturer and ride.device_manufacturer is None:
        ride.device_manufacturer = str(manufacturer)
    if product_name and ride.device_name is None:
        ride.device_name = str(product_name)


def _get_values(record) -> dict:
    """Extract field values from a FIT record message."""
    values = {}
    for field_data in record.fields:
        if field_data.value is not None:
            values[field_data.name] = field_data.value
    return values


def fit_data_to_ride_dict(fit_data: FitRideData) -> dict:
    """
    Convert parsed FIT data to a dict matching our RideCreate API schema.
    Ready to POST to /api/rides.
    """
    # Generate title from date and sport
    date_str = fit_data.ride_date.strftime("%b %d") if fit_data.ride_date else "Ride"
    device = fit_data.device_name or "Garmin"
    title = f"{date_str} â€” {device}"
    
    result = {
        "title": title,
        "ride_date": fit_data.ride_date.isoformat() if fit_data.ride_date else date.today().isoformat(),
        "duration_seconds": fit_data.duration_seconds,
        "avg_power": fit_data.avg_power,
        "max_power": fit_data.max_power,
    }
    
    if fit_data.avg_heart_rate:
        result["avg_heart_rate"] = fit_data.avg_heart_rate
    if fit_data.max_heart_rate:
        result["max_heart_rate"] = fit_data.max_heart_rate
    if fit_data.distance_km:
        result["distance_km"] = fit_data.distance_km
    if fit_data.elevation_gain_m:
        result["elevation_gain_m"] = fit_data.elevation_gain_m
    if fit_data.avg_speed_kmh:
        result["avg_speed_kmh"] = fit_data.avg_speed_kmh
    if fit_data.avg_cadence:
        result["avg_cadence"] = fit_data.avg_cadence
    
    return result

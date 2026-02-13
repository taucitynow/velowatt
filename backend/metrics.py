"""
Cycling Performance Metrics Calculator

Calculates key training metrics:
- NP (Normalized Power): Weighted average power that accounts for variability
- IF (Intensity Factor): Ratio of NP to FTP
- TSS (Training Stress Score): Overall training load for a ride
- CTL (Chronic Training Load): Long-term fitness (42-day rolling avg)
- ATL (Acute Training Load): Short-term fatigue (7-day rolling avg)
- TSB (Training Stress Balance): Form = CTL - ATL
- VI (Variability Index): NP / Average Power
- EF (Efficiency Factor): NP / Average Heart Rate
- Power Zones: 7-zone model based on FTP
"""

import math
from typing import Optional


def calculate_normalized_power(power_data: list[float], sample_rate_seconds: int = 1) -> float:
    """
    Calculate Normalized Power (NP).
    
    Algorithm:
    1. Calculate 30-second rolling average of power
    2. Raise each value to the 4th power
    3. Take the average of those values
    4. Take the 4th root
    
    Args:
        power_data: List of power values in watts (one per sample)
        sample_rate_seconds: Seconds between each sample (default 1s)
    
    Returns:
        Normalized Power in watts
    """
    if not power_data or len(power_data) < 30:
        return 0.0

    # Calculate window size for 30-second rolling average
    window = max(1, 30 // sample_rate_seconds)

    if len(power_data) < window:
        return 0.0

    # 30-second rolling average
    rolling_avg = []
    for i in range(window - 1, len(power_data)):
        segment = power_data[i - window + 1: i + 1]
        avg = sum(segment) / len(segment)
        rolling_avg.append(avg)

    if not rolling_avg:
        return 0.0

    # Raise to 4th power, average, then 4th root
    fourth_powers = [p ** 4 for p in rolling_avg]
    avg_fourth = sum(fourth_powers) / len(fourth_powers)
    np_value = avg_fourth ** 0.25

    return round(np_value, 1)


def calculate_intensity_factor(normalized_power: float, ftp: float) -> float:
    """
    Calculate Intensity Factor (IF).
    
    IF = NP / FTP
    
    Interpretation:
    - < 0.75: Recovery ride
    - 0.75-0.85: Endurance ride
    - 0.85-0.95: Tempo ride
    - 0.95-1.05: Threshold ride
    - 1.05-1.15: VO2max intervals
    - > 1.15: Anaerobic/Neuromuscular
    """
    if ftp <= 0:
        return 0.0
    return round(normalized_power / ftp, 3)


def calculate_tss(
    normalized_power: float,
    intensity_factor: float,
    duration_seconds: int,
    ftp: float
) -> float:
    """
    Calculate Training Stress Score (TSS).
    
    TSS = (duration_seconds * NP * IF) / (FTP * 3600) * 100
    
    Interpretation:
    - < 150: Low — recovery usually within 24h
    - 150-300: Medium — some residual fatigue next day
    - 300-450: High — residual fatigue likely for 2 days
    - > 450: Very high — residual fatigue for several days
    """
    if ftp <= 0 or duration_seconds <= 0:
        return 0.0

    tss = (duration_seconds * normalized_power * intensity_factor) / (ftp * 3600) * 100
    return round(tss, 1)


def calculate_tss_simple(
    avg_power: float,
    duration_seconds: int,
    ftp: float
) -> float:
    """
    Simplified TSS calculation when only average power is available.
    Uses average power instead of NP (less accurate but useful for manual entry).
    
    TSS ≈ (duration_seconds * (avg_power/FTP)^2) / 3600 * 100
    """
    if ftp <= 0 or duration_seconds <= 0:
        return 0.0

    intensity = avg_power / ftp
    tss = (duration_seconds * intensity ** 2) / 3600 * 100
    return round(tss, 1)


def calculate_variability_index(normalized_power: float, avg_power: float) -> float:
    """
    Calculate Variability Index (VI).
    
    VI = NP / AP
    
    A perfectly steady ride would have VI = 1.0
    More variable rides have VI > 1.0
    """
    if avg_power <= 0:
        return 0.0
    return round(normalized_power / avg_power, 2)


def calculate_efficiency_factor(normalized_power: float, avg_heart_rate: float) -> float:
    """
    Calculate Efficiency Factor (EF).
    
    EF = NP / Avg HR
    
    Higher EF indicates better aerobic fitness.
    Track EF over time at similar intensities to monitor fitness.
    """
    if avg_heart_rate <= 0:
        return 0.0
    return round(normalized_power / avg_heart_rate, 2)


def calculate_ctl(tss_history: list[float], days: int = 42) -> float:
    """
    Calculate Chronic Training Load (CTL) — "Fitness".
    
    Exponentially weighted moving average of daily TSS over 42 days.
    
    CTL_today = CTL_yesterday + (TSS_today - CTL_yesterday) / 42
    """
    if not tss_history:
        return 0.0

    ctl = 0.0
    for daily_tss in tss_history:
        ctl = ctl + (daily_tss - ctl) / days
    return round(ctl, 1)


def calculate_atl(tss_history: list[float], days: int = 7) -> float:
    """
    Calculate Acute Training Load (ATL) — "Fatigue".
    
    Exponentially weighted moving average of daily TSS over 7 days.
    
    ATL_today = ATL_yesterday + (TSS_today - ATL_yesterday) / 7
    """
    if not tss_history:
        return 0.0

    atl = 0.0
    for daily_tss in tss_history:
        atl = atl + (daily_tss - atl) / days
    return round(atl, 1)


def calculate_tsb(ctl: float, atl: float) -> float:
    """
    Calculate Training Stress Balance (TSB) — "Form".
    
    TSB = CTL - ATL
    
    Interpretation:
    - Negative: Fatigued (training hard)
    - 0 to -10: Optimal for training
    - Positive: Fresh (good for racing)
    - > 25: Possibly losing fitness (too much rest)
    """
    return round(ctl - atl, 1)


def get_power_zones(ftp: float) -> list[dict]:
    """
    Calculate 7 power zones based on FTP.
    
    Returns list of zones with name, min/max watts, and % FTP range.
    """
    zones = [
        {"zone": 1, "name": "Active Recovery", "min_pct": 0, "max_pct": 0.55},
        {"zone": 2, "name": "Endurance", "min_pct": 0.55, "max_pct": 0.75},
        {"zone": 3, "name": "Tempo", "min_pct": 0.75, "max_pct": 0.90},
        {"zone": 4, "name": "Threshold", "min_pct": 0.90, "max_pct": 1.05},
        {"zone": 5, "name": "VO2max", "min_pct": 1.05, "max_pct": 1.20},
        {"zone": 6, "name": "Anaerobic", "min_pct": 1.20, "max_pct": 1.50},
        {"zone": 7, "name": "Neuromuscular", "min_pct": 1.50, "max_pct": None},
    ]

    result = []
    for z in zones:
        min_watts = round(ftp * z["min_pct"])
        max_watts = round(ftp * z["max_pct"]) if z["max_pct"] else None
        result.append({
            "zone": z["zone"],
            "name": z["name"],
            "min_watts": min_watts,
            "max_watts": max_watts,
            "min_pct": round(z["min_pct"] * 100),
            "max_pct": round(z["max_pct"] * 100) if z["max_pct"] else None,
        })

    return result


def get_ride_intensity_label(intensity_factor: float) -> str:
    """Return a human-readable label for the ride intensity."""
    if intensity_factor < 0.75:
        return "Recovery"
    elif intensity_factor < 0.85:
        return "Endurance"
    elif intensity_factor < 0.95:
        return "Tempo"
    elif intensity_factor < 1.05:
        return "Threshold"
    elif intensity_factor < 1.15:
        return "VO2max"
    else:
        return "Anaerobic"


def get_tss_recovery_label(tss: float) -> str:
    """Return estimated recovery time based on TSS."""
    if tss < 150:
        return "Low — recovery within 24h"
    elif tss < 300:
        return "Medium — some fatigue next day"
    elif tss < 450:
        return "High — fatigue for ~2 days"
    else:
        return "Very high — fatigue for several days"


def calculate_ride_metrics(
    duration_seconds: int,
    avg_power: float,
    ftp: float,
    normalized_power: Optional[float] = None,
    avg_heart_rate: Optional[float] = None,
    power_data: Optional[list[float]] = None,
    sample_rate_seconds: int = 1,
) -> dict:
    """
    Calculate all ride metrics from available data.
    
    If power_data is provided, NP is calculated from it.
    If normalized_power is provided directly, it's used as-is.
    Otherwise, average power is used as an approximation.
    """
    # Determine NP
    if power_data:
        np_value = calculate_normalized_power(power_data, sample_rate_seconds)
    elif normalized_power:
        np_value = normalized_power
    else:
        np_value = avg_power  # Approximation

    # Core metrics
    if_value = calculate_intensity_factor(np_value, ftp)
    tss = calculate_tss(np_value, if_value, duration_seconds, ftp)
    vi = calculate_variability_index(np_value, avg_power)

    result = {
        "duration_seconds": duration_seconds,
        "duration_formatted": format_duration(duration_seconds),
        "avg_power": round(avg_power, 1),
        "normalized_power": np_value,
        "ftp": ftp,
        "intensity_factor": if_value,
        "tss": tss,
        "variability_index": vi,
        "intensity_label": get_ride_intensity_label(if_value),
        "recovery_label": get_tss_recovery_label(tss),
    }

    if avg_heart_rate:
        result["avg_heart_rate"] = round(avg_heart_rate, 1)
        result["efficiency_factor"] = calculate_efficiency_factor(np_value, avg_heart_rate)

    return result


def format_duration(seconds: int) -> str:
    """Format seconds into H:MM:SS string."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"

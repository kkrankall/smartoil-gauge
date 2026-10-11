"""Turn Smart Oil Gauge web-app responses into entity values.

The rules for "days to" estimates and the offline cutoff follow the web
app's own JavaScript (app.js: calcDTL, calcDTE, isOffline), so the numbers
match what app.smartoilgauge.com shows.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

# The web app treats a sensor as offline after 96 h without a reading and
# then stops showing "days to" estimates.
OFFLINE_AFTER = 96 * 3600
# The web app shows usage under 0.2 gal/day as 0.
MIN_USAGE_RATE = 0.2
# A rise this large between readings is a delivery, not sensor noise
# (readings wander by a gallon or two).
FILL_MIN_GALLONS = 20.0
FILL_MIN_FRACTION = 0.10
BATTERY_RANK = {"Poor": 0, "Low": 0, "Fair": 1, "Good": 2, "Excellent": 3}


def _num(value: Any) -> float | None:
    try:
        return None if value is None or value == "" else float(value)
    except (TypeError, ValueError):
        return None


def _time(ts: float | None) -> datetime | None:
    return None if ts is None else datetime.fromtimestamp(ts, UTC)


def _oldest_read(last_read: Any) -> int | None:
    """last_read is one epoch per sensor, comma-separated; use the oldest."""
    times = [int(t) for t in str(last_read or "").split(",") if t.strip().isdigit()]
    return min(times) if times else None


def _worst_battery(battery: Any) -> str | None:
    """battery is one reading per sensor, comma-separated; report the worst."""
    values = [b.strip() for b in str(battery or "").split(",") if b.strip()]
    return min(values, key=lambda b: BATTERY_RANK.get(b, 0)) if values else None


def _days_until(gallons: float, target: float, rate: float | None) -> float | None:
    if not rate or rate <= 0:
        return None
    return round(max((gallons - target) / rate, 0.0), 1)


def _dataset(graph: dict | None, tank: dict) -> dict:
    """The graph datasets are keyed by sensor registration id."""
    datasets = (graph or {}).get("datasets") or {}
    for sensor in tank.get("sensors") or []:
        if str(sensor.get("registration_id")) in datasets:
            return datasets[str(sensor["registration_id"])]
    return next(iter(datasets.values()), {})


def detect_last_fill(dataset: dict, capacity: float | None) -> tuple[int | None, float | None]:
    """Find the latest delivery in the history: (reading time, gallons added).

    The year, month, week and day series are readings of the same tank at
    different spacing, so they merge into one series. After a fill the raw
    reading can sit in the sensor's dead zone near the top of the tank; the
    site's corrected value (fgal) is used for the level after the fill.
    """
    points: dict[int, tuple[float, float | None]] = {}
    for period in ("year", "month", "week", "day"):
        for point in (dataset.get(period) or {}).get("points") or []:
            gallons = _num(point.get("gallons"))
            if point.get("ts") is not None and gallons is not None:
                points[int(point["ts"])] = (gallons, _num(point.get("fgal")))
    series = sorted(points.items())
    threshold = max(FILL_MIN_GALLONS, (capacity or 0) * FILL_MIN_FRACTION)
    for i in range(len(series) - 1, 0, -1):
        ts, (gallons, corrected) = series[i]
        before = series[i - 1][1][0]
        if gallons - before >= threshold:
            return ts, round(max(gallons, corrected or 0) - before, 1)
    return None, None


def _latest_temperature(dataset: dict) -> float | None:
    """Temperature comes in tenths of a degree F (a basement tank reads
    540-810 over a year). Use the newest reading that has one."""
    for period in ("day", "week", "month"):
        points = [p for p in (dataset.get(period) or {}).get("points") or []
                  if _num(p.get("temperature"))]
        if points:
            latest = max(points, key=lambda p: int(p["ts"]))
            return round(_num(latest["temperature"]) / 10, 1)
    return None


def parse_tank(tank: dict, graph: dict | None, now: float) -> dict[str, Any]:
    """Build entity values from a get_tanks_list entry and its graph data."""
    capacity = _num(tank.get("nominal"))
    fillable = _num(tank.get("fillable"))
    low_fraction = _num(tank.get("low_level")) or 0.25
    sensor_gallons = _num(tank.get("sensor_gallons"))
    # Tanks without a sensor (the "virtual" gauge) only have a modelled level.
    gallons = sensor_gallons if sensor_gallons is not None else _num(tank.get("model_gallons"))
    rate = _num(tank.get("sensor_usg"))
    if rate is not None and abs(rate) < MIN_USAGE_RATE:
        rate = 0.0
    last_read = _oldest_read(tank.get("last_read"))
    offline = last_read is not None and now - last_read > OFFLINE_AFTER

    data: dict[str, Any] = {
        "gallons": gallons,
        "level": None,
        "usage_rate": None if rate is None else round(rate, 2),
        "days_to_low": None,
        "days_to_eighth": None,
        "gallons_to_fill": None,
        "low_level": None,
        "battery": _worst_battery(tank.get("battery")),
        "last_reading": _time(last_read),
        "sensor_offline": offline,
        "sensor_status": tank.get("sensor_status") or None,
        "capacity": capacity,
        "fillable_capacity": fillable,
        "low_level_alert": round(low_fraction * 100, 1),
    }
    if gallons is not None and capacity:
        data["level"] = round(min(max(gallons * 100 / capacity, 0.0), 100.0), 1)
        data["low_level"] = gallons < capacity * low_fraction
        if not offline:
            data["days_to_low"] = (0.0 if data["low_level"] else
                                   _days_until(gallons, capacity * low_fraction, rate))
            data["days_to_eighth"] = _days_until(gallons, capacity * 0.125, rate)
    if gallons is not None and fillable:
        data["gallons_to_fill"] = round(max(fillable - gallons, 0.0), 1)

    dataset = _dataset(graph, tank)
    for key, period in (("used_7_days", "week"), ("used_30_days", "month"),
                        ("used_365_days", "year")):
        data[key] = _num((dataset.get(period) or {}).get("gallons"))
    data["temperature"] = _latest_temperature(dataset)
    fill_ts, fill_gallons = detect_last_fill(dataset, capacity)
    data["last_fill"] = _time(fill_ts)
    data["last_fill_amount"] = fill_gallons
    return data

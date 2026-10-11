"""Values computed from captured Smart Oil Gauge responses."""

from datetime import UTC, datetime

from custom_components.smartoil_gauge.parse import detect_last_fill, parse_tank

from .conftest import NOW, load


def _parse(now=NOW, **tank_changes):
    tank = {**load("tanks_list.json")["tanks"][0], **tank_changes}
    return parse_tank(tank, load("graph_data.json"), now)


def test_matches_the_website():
    data = _parse()
    assert data["gallons"] == 68.84
    assert data["level"] == 25.0
    assert data["usage_rate"] == 1.42
    # The website shows 0 days to 1/4 and 24 days to 1/8 for this reading.
    assert data["days_to_low"] == 0.1
    assert data["days_to_eighth"] == 24.3
    assert data["gallons_to_fill"] == 182.2
    assert data["low_level"] is False
    assert data["battery"] == "Good"
    assert data["sensor_offline"] is False
    assert data["last_reading"] == datetime(2026, 10, 11, 13, 9, 13, tzinfo=UTC)


def test_history():
    data = _parse()
    assert data["used_7_days"] == 10.29
    assert data["used_30_days"] == 24.26
    assert data["used_365_days"] == 693.46
    assert data["temperature"] == 71.2
    # 109.35 gal before the March delivery, 259.11 after (corrected for the dead zone).
    assert data["last_fill"] == datetime.fromtimestamp(1774501475, UTC)
    assert data["last_fill_amount"] == 149.8


def test_below_low_level():
    data = _parse(sensor_gallons="50")
    assert data["low_level"] is True
    assert data["days_to_low"] == 0.0
    assert data["days_to_eighth"] == 11.0


def test_offline_after_96_hours_drops_estimates():
    data = _parse(now=1791724153 + 97 * 3600)
    assert data["sensor_offline"] is True
    assert data["days_to_low"] is None
    assert data["days_to_eighth"] is None
    assert data["gallons"] == 68.84


def test_tiny_or_negative_usage_gives_no_estimate():
    assert _parse(sensor_usg="0.1")["usage_rate"] == 0.0
    assert _parse(sensor_usg="0.1")["days_to_eighth"] is None
    assert _parse(sensor_usg="-1.5")["days_to_eighth"] is None


def test_multi_sensor_tank_uses_oldest_read_and_worst_battery():
    data = _parse(last_read="1791724153,1791000000", battery="Good,Poor")
    assert data["last_reading"] == datetime.fromtimestamp(1791000000, UTC)
    assert data["battery"] == "Poor"


def test_virtual_gauge_uses_model_level():
    data = _parse(sensor_gallons=None, model_gallons="137.5", sensor_usg=None, battery="")
    assert data["gallons"] == 137.5
    assert data["level"] == 50.0
    assert data["usage_rate"] is None
    assert data["battery"] is None


def test_no_history():
    tank = load("tanks_list.json")["tanks"][0]
    data = parse_tank(tank, None, NOW)
    assert data["gallons"] == 68.84
    assert data["used_7_days"] is None
    assert data["temperature"] is None
    assert data["last_fill"] is None


def test_noise_is_not_a_fill():
    dataset = {"day": {"points": [
        {"ts": 1, "gallons": 67.0}, {"ts": 2, "gallons": 68.9}, {"ts": 3, "gallons": 66.5},
    ]}}
    assert detect_last_fill(dataset, 275) == (None, None)

import pytest

from app.services.integrations.http import IntegrationUnavailable
from app.services.weather import cache_key, location_key, normalize_forecast


def test_weather_normalization_converts_reported_units_to_canonical_units():
    data, units = normalize_forecast({
        "units": {"rainfall": "in", "temperature": "F", "wind_speed": "km/h"},
        "forecast": [{"timestamp": "2026-10-30T12:00:00Z", "rainfall": 0.5,
                      "temperature": 68, "wind_speed": 36}],
    })
    assert units == {"rainfall": "mm", "temperature": "C", "wind_speed": "m/s"}
    point = data["forecast"][0]
    assert point["rainfall_mm"] == pytest.approx(12.7)
    assert point["temperature_c"] == pytest.approx(20)
    assert point["wind_speed_m_s"] == pytest.approx(10)


def test_weather_rejects_unknown_units_and_timezone_naive_timestamps():
    with pytest.raises(IntegrationUnavailable, match="invalid forecast point"):
        normalize_forecast({"units": {}, "forecast": [{"at": "2026-10-30T12:00:00", "rainfall": 1}]})
    with pytest.raises(IntegrationUnavailable, match="invalid forecast point"):
        normalize_forecast({"units": {}, "forecast": [{"at": "2026-10-30T12:00:00Z", "rainfall": 1}]})


def test_weather_cache_key_uses_rounded_plot_coordinates_and_provider_version():
    rounded = location_key(12.97161, 77.59461)
    assert rounded == "12.972:77.595"
    assert cache_key(rounded) == "weather:v1:open_meteo:12.972:77.595"

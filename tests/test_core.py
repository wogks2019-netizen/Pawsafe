import numpy as np
import pandas as pd

from src.pawsafe.features import build_edge_time_features
from src.pawsafe.utils import minmax


def test_minmax():
    assert minmax(pd.Series([1, 2, 3])).tolist() == [0, 50, 100]


def test_sun_and_storage_increase():
    edges = pd.DataFrame({"edge_id":["E1"], "length_m":[100], "surface_code":["SWB005"], "surface_absorptivity":[0.88]})
    ts = pd.date_range("2026-08-01 12:00", periods=3, freq="h")
    shadows = pd.DataFrame({"edge_id":["E1"]*3, "timestamp":ts, "shade_ratio":[0,0,0]})
    weather = pd.DataFrame({"timestamp":ts, "solar_radiation_mj_m2":[2,2,2], "air_temperature_c":[33]*3, "humidity_pct":[60]*3, "wind_speed_ms":[1]*3, "rainfall_mm":[0]*3})
    cfg={"time":{"shadow_interval_minutes":60,"recent_sun_window_hours":3,"cumulative_window_hours":6},"heat":{"thermal_memory_hours":2.5,"wind_cooling_factor":.12,"rain_cooling_factor":.35}}
    out=build_edge_time_features(edges, shadows, weather, cfg)
    assert out.heat_storage_proxy.is_monotonic_increasing
    assert out.recent_direct_sun_minutes.iloc[-1] == 180


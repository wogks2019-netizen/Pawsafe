from __future__ import annotations

import math
from datetime import timezone

import geopandas as gpd
import numpy as np
import pandas as pd
from pysolar.solar import get_altitude, get_azimuth
from shapely import affinity
from shapely.geometry import LineString
from shapely.ops import unary_union


def solar_position(timestamp: pd.Timestamp, lat: float, lon: float, tz_name: str) -> tuple[float, float]:
    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        ts = ts.tz_localize(tz_name)
    utc = ts.tz_convert(timezone.utc).to_pydatetime()
    return float(get_altitude(lat, lon, utc)), float(get_azimuth(lat, lon, utc))


def _shadow_vector(height: float, altitude: float, azimuth: float, cap: float) -> tuple[float, float]:
    length = min(cap, height / max(math.tan(math.radians(altitude)), 0.08))
    return -length * math.sin(math.radians(azimuth)), -length * math.cos(math.radians(azimuth))


def _extruded_shadow(geom, dx: float, dy: float):
    moved = affinity.translate(geom, xoff=dx, yoff=dy)
    return unary_union([geom, moved]).convex_hull


def shadow_union(buildings: gpd.GeoDataFrame, trees: gpd.GeoDataFrame, altitude: float, azimuth: float, cfg: dict):
    if altitude <= 0:
        return None
    shadows = []
    for geom, h in zip(buildings.geometry, buildings["height_m"]):
        dx, dy = _shadow_vector(float(h), altitude, azimuth, cfg["geometry"]["max_building_shadow_m"])
        shadows.append(_extruded_shadow(geom, dx, dy))
    for geom, h, crown in zip(trees.geometry, trees["height_m"], trees["crown_width_m"]):
        disk = geom.buffer(float(crown) / 2)
        dx, dy = _shadow_vector(float(h), altitude, azimuth, cfg["geometry"]["max_tree_shadow_m"])
        shadows.append(_extruded_shadow(disk, dx, dy))
    return unary_union(shadows) if shadows else None


def shade_ratio_by_edge(edges: gpd.GeoDataFrame, shadow, spacing_m: float) -> np.ndarray:
    if shadow is None or shadow.is_empty:
        return np.zeros(len(edges), dtype=float)
    prepared = shadow
    values = []
    for geom in edges.geometry:
        n = max(2, int(math.ceil(geom.length / spacing_m)) + 1)
        pts = [geom.interpolate(i / (n - 1), normalized=True) for i in range(n)]
        values.append(sum(prepared.covers(p) for p in pts) / n)
    return np.asarray(values, dtype=float)


def calculate_shadows(edges, buildings, trees, timestamps, cfg):
    rows = []
    lat, lon = cfg["location"]["latitude"], cfg["location"]["longitude"]
    for ts in pd.to_datetime(timestamps):
        altitude, azimuth = solar_position(ts, lat, lon, cfg["timezone"])
        union = shadow_union(buildings, trees, altitude, azimuth, cfg) if altitude > 0 else None
        ratios = shade_ratio_by_edge(edges, union, cfg["geometry"]["edge_sample_spacing_m"]) if altitude > 0 else np.ones(len(edges))
        rows.append(pd.DataFrame({"edge_id": edges["edge_id"], "timestamp": ts, "solar_altitude_deg": altitude, "solar_azimuth_deg": azimuth, "shade_ratio": ratios}))
    return pd.concat(rows, ignore_index=True)


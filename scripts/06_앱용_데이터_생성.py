from pathlib import Path
import os

import geopandas as gpd
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)


OUTPUT_DIR = Path("outputs")

HEAT_INPUT = OUTPUT_DIR / "edge_heat_continuous_20260808_1500.geojson"
ROUTE_INPUT = OUTPUT_DIR / "route_comparison.geojson"
SEGMENT_INPUT = OUTPUT_DIR / "route_segments.geojson"


# 1. 앱용 열지도 데이터
heat = gpd.read_file(HEAT_INPUT)

heat["surface_code"] = (
    heat["surface_code_y"]
    .fillna(heat["surface_code_x"])
    .fillna("unknown")
)

heat["surface_absorptivity"] = (
    heat["surface_absorptivity_y"]
    .fillna(heat["surface_absorptivity_x"])
    .fillna(0.75)
)

heat["heat_level"] = pd.cut(
    heat["heat_cost_continuous"],
    bins=[0, 20, 40, 60, 80, 100],
    labels=["very_low", "low", "medium", "high", "very_high"],
    include_lowest=True,
)

heat["pavement_known"] = heat["pavement_known"].fillna(False).astype(bool)

heat_columns = [
    "edge_id",
    "osm_id",
    "name",
    "fclass",
    "length_m",
    "timestamp",
    "heat_cost_continuous",
    "heat_level",
    "shade_ratio",
    "recent_direct_sun_minutes",
    "cumulative_effective_solar_mj_m2",
    "surface_code",
    "surface_absorptivity",
    "pavement_known",
    "geometry",
]

app_heat = heat[heat_columns].copy()
app_heat = app_heat.rename(
    columns={"heat_cost_continuous": "heat_cost"}
)

app_heat.to_crs(4326).to_file(
    OUTPUT_DIR / "app_edge_heat.geojson",
    driver="GeoJSON",
)


# 2. 앱용 경로 요약 데이터
routes = gpd.read_file(ROUTE_INPUT)

routes["mean_heat_cost_100"] = routes["mean_heat_cost"] * 100

route_columns = [
    "mode",
    "distance_m",
    "mean_heat_cost_100",
    "geometry",
]

app_routes = routes[route_columns].copy()

app_routes.to_crs(4326).to_file(
    OUTPUT_DIR / "app_routes.geojson",
    driver="GeoJSON",
)


# 3. 앱용 경로 구간 데이터
segments = gpd.read_file(SEGMENT_INPUT)

segment_columns = [
    "mode",
    "segment_order",
    "edge_id",
    "length_m",
    "heat_cost",
    "geometry",
]

app_segments = segments[segment_columns].copy()

app_segments["heat_level"] = pd.cut(
    app_segments["heat_cost"],
    bins=[0, 20, 40, 60, 80, 100],
    labels=["very_low", "low", "medium", "high", "very_high"],
    include_lowest=True,
)

app_segments.to_crs(4326).to_file(
    OUTPUT_DIR / "app_route_segments.geojson",
    driver="GeoJSON",
)


print("앱용 데이터 생성 완료")
print(f"열지도 Edge: {len(app_heat)}개")
print(f"추천 경로: {len(app_routes)}개")
print(f"경로 구간: {len(app_segments)}개")

print("\n생성 파일")
print("outputs/app_edge_heat.geojson")
print("outputs/app_routes.geojson")
print("outputs/app_route_segments.geojson")

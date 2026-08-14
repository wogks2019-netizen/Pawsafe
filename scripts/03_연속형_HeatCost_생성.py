import geopandas as gpd
import numpy as np
import pandas as pd
import os
from pathlib import Path
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)


TARGET_TIME = pd.Timestamp("2026-08-08 15:00:00")

data = pd.read_parquet(
    "data/processed/edge_time_features.parquet"
)

data["timestamp"] = pd.to_datetime(data["timestamp"])

current = data[
    data["timestamp"].eq(TARGET_TIME)
].copy()

if current.empty:
    raise ValueError(
        f"{TARGET_TIME}에 해당하는 데이터가 없습니다."
    )

features = [
    "recent_direct_sun_minutes",
    "cumulative_effective_solar_mj_m2",
    "shade_ratio",
    "air_temperature_c",
    "wind_speed_ms",
    "heat_storage_proxy",
]

X = current[features].replace(
    [np.inf, -np.inf],
    np.nan,
)

X = X.fillna(X.median()).fillna(0)

Z = pd.DataFrame(
    StandardScaler().fit_transform(X),
    columns=features,
    index=current.index,
)

# 물리적 방향에 기반한 상대 가중치
weights = {
    "recent_direct_sun_minutes": 0.20,
    "cumulative_effective_solar_mj_m2": 0.30,
    "shade_ratio": -0.20,
    "air_temperature_c": 0.15,
    "wind_speed_ms": -0.05,
    "heat_storage_proxy": 0.20,
}

current["heat_raw"] = sum(
    Z[column] * weight
    for column, weight in weights.items()
)

# 이상치가 전체 색상 범위를 지배하지 않도록
# 5~95 분위수 기준으로 0~100 변환
low = current["heat_raw"].quantile(0.05)
high = current["heat_raw"].quantile(0.95)

if high <= low:
    raise ValueError(
        "Heat Cost 변환 범위가 올바르지 않습니다."
    )

current["heat_cost_continuous"] = (
    (current["heat_raw"] - low)
    / (high - low)
    * 100
).clip(0, 100)

# 포장재 정보 확인 여부
current["pavement_known"] = (
    current["surface_code"].ne("unknown")
)

edges = gpd.read_file(
    "data/processed/edges_static.gpkg",
    layer="edges",
)

columns = [
    "edge_id",
    "timestamp",
    "cluster",
    "heat_cost",
    "heat_cost_continuous",
    "shade_ratio",
    "recent_direct_sun_minutes",
    "cumulative_effective_solar_mj_m2",
    "surface_code",
    "surface_absorptivity",
    "pavement_known",
]

result = edges.merge(
    current[columns],
    on="edge_id",
    how="left",
)

result = result.to_crs(4326)

output_path = (
    "outputs/"
    "edge_heat_continuous_20260808_1500.geojson"
)

result.to_file(
    output_path,
    driver="GeoJSON",
)

print("저장 완료:", output_path)
print("Edge 수:", len(result))
print("누락:", result["heat_cost_continuous"].isna().sum())
print(result["heat_cost_continuous"].describe())

print("\n구간별 Edge 수")
print(
    pd.cut(
        result["heat_cost_continuous"],
        bins=[0, 20, 40, 60, 80, 100],
        include_lowest=True,
    ).value_counts().sort_index()
)

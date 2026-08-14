from pathlib import Path
import os
import sys

import geopandas as gpd
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from src.pawsafe.routing import route_all_modes
from src.pawsafe.utils import load_config


cfg = load_config("config.json")

# QGIS 표시 순서와 반대로: 경도, 위도
start = (127.11261, 37.48508)
end = (127.15297, 37.48804)

target_time = pd.Timestamp("2026-08-08 15:00:00")

edges = gpd.read_file(
    "data/processed/edges_static.gpkg",
    layer="edges",
)

heat = gpd.read_file(
    "outputs/edge_heat_continuous_20260808_1500.geojson"
)

# 경로 함수가 사용하는 컬럼명으로 변경
edge_time = heat[
    [
        "edge_id",
        "timestamp",
        "heat_cost_continuous",
    ]
].copy()

edge_time["timestamp"] = pd.to_datetime(
    edge_time["timestamp"]
)

edge_time = edge_time.rename(
    columns={
        "heat_cost_continuous": "heat_cost"
    }
)

result = route_all_modes(
    edges=edges,
    edge_time=edge_time,
    start_lonlat=start,
    end_lonlat=end,
    timestamp=target_time,
    cfg=cfg,
    output_dir=Path("outputs"),
)

print("경로 생성 완료")

for mode, values in result["routes"].items():
    print()
    print("모드:", mode)
    print(
        "거리:",
        round(values["distance_m"], 1),
        "m",
    )
    print(
        "평균 Heat Cost:",
        f'{values["mean_heat_cost"] * 100:.1f}/100',
    )
    print(
        "통과 Edge 수:",
        len(values["edge_ids"]),
    )

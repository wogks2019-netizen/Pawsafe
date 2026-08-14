import geopandas as gpd
import networkx as nx
import pandas as pd
import os
import sys
from pathlib import Path
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, davies_bouldin_score
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from src.pawsafe.routing import build_graph
from src.pawsafe.utils import load_config


cfg = load_config("config.json")

# 이미 계산된 Edge×시간 피처
data = pd.read_parquet(
    "data/processed/edge_time_features.parquet"
)

# 포장재가 확인된 행만 사용
known = data[
    data["surface_code"].ne("unknown")
].copy()

feature_columns = cfg["clustering"]["features"]

X = (
    known[feature_columns]
    .replace([float("inf"), float("-inf")], pd.NA)
)

X = X.fillna(X.median(numeric_only=True)).fillna(0)

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

print("================================")
print("1. 포장재 확인 데이터 규모")
print("================================")
print("포장재 확인 Edge 수:", known["edge_id"].nunique())
print("Edge×시간 행 수:", len(known))
print()
print(known["surface_code"].value_counts())


print("\n================================")
print("2. K-means 군집 품질")
print("================================")

for k in [2, 3, 4, 5]:
    model = KMeans(
        n_clusters=k,
        random_state=42,
        n_init=20,
    )

    labels = model.fit_predict(X_scaled)

    silhouette = silhouette_score(
        X_scaled,
        labels,
        sample_size=min(10000, len(X_scaled)),
        random_state=42,
    )

    dbi = davies_bouldin_score(
        X_scaled,
        labels,
    )

    print(
        f"k={k}: "
        f"silhouette={silhouette:.4f}, "
        f"davies_bouldin={dbi:.4f}"
    )


print("\n================================")
print("3. 포장재 확인 도로 연결성")
print("================================")

edges = gpd.read_file(
    "data/processed/edges_static.gpkg",
    layer="edges",
)

known_edge_ids = set(known["edge_id"].unique())

known_edges = edges[
    edges["edge_id"].isin(known_edge_ids)
].copy()

graph, _ = build_graph(known_edges, cfg)

components = sorted(
    nx.connected_components(graph),
    key=len,
    reverse=True,
)

print("전체 포장재 확인 Edge:", len(known_edges))
print("연결요소 개수:", len(components))

if components:
    largest_nodes = components[0]

    largest_edge_ids = set()

    for u, v, attrs in graph.edges(
        largest_nodes,
        data=True,
    ):
        largest_edge_ids.add(attrs["edge_id"])

    print(
        "가장 큰 연결망 Edge:",
        len(largest_edge_ids),
    )

    print(
        "가장 큰 연결망 비율:",
        round(
            len(largest_edge_ids)
            / len(known_edges)
            * 100,
            1,
        ),
        "%",
    )

    output = known_edges[
        known_edges["edge_id"].isin(
            largest_edge_ids
        )
    ].to_crs(4326)

    output.to_file(
        "outputs/"
        "largest_known_pavement_network.geojson",
        driver="GeoJSON",
    )

    print(
        "지도 저장:",
        "outputs/"
        "largest_known_pavement_network.geojson",
    )

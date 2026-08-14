from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .clustering import fit_clusters, validate_optional
from .features import build_edge_time_features
from .preprocess import attach_pavement, load_boundary, load_buildings, load_trees, load_walkways, load_weather
from .routing import build_graph, route_all_modes
from .shadow import calculate_shadows


def run(cfg: dict, start=None, end=None, route_time=None):
    root = Path(cfg["_root"]); out = root / "outputs"; processed = root / "data" / "processed"
    out.mkdir(exist_ok=True); processed.mkdir(parents=True, exist_ok=True)
    boundary = load_boundary(cfg)
    edges = attach_pavement(cfg, load_walkways(cfg, boundary))
    buildings = load_buildings(cfg, boundary)
    trees = load_trees(cfg, boundary)
    weather = load_weather(cfg)
    if cfg["time"]["start"]: weather = weather[weather.timestamp >= pd.Timestamp(cfg["time"]["start"])]
    if cfg["time"]["end"]: weather = weather[weather.timestamp <= pd.Timestamp(cfg["time"]["end"])]
    shadows = calculate_shadows(edges, buildings, trees, weather.timestamp, cfg)
    features = build_edge_time_features(edges, shadows, weather, cfg)
    scored, metrics, profiles = fit_clusters(features, cfg, out)
    validate_optional(scored, cfg, out)

    edges.to_file(processed / "edges_static.gpkg", layer="edges", driver="GPKG")
    scored.to_parquet(processed / "edge_time_features.parquet", index=False)
    scored.to_csv(processed / "edge_time_features.csv", index=False, encoding="utf-8-sig")
    latest = scored.sort_values("timestamp").groupby("edge_id").tail(1)
    heat_map = edges.merge(latest[["edge_id", "timestamp", "cluster", "heat_cost"]], on="edge_id", how="left").to_crs(4326)
    heat_map.to_file(out / "edge_heat_latest.geojson", driver="GeoJSON")
    graph, _ = build_graph(edges, cfg)
    nodes = gpd.GeoDataFrame([{"node_id": i, "geometry": gpd.points_from_xy([n[0]],[n[1]])[0]} for i,n in enumerate(graph.nodes)], crs=cfg["project_crs"]).to_crs(4326)
    nodes.to_file(out / "graph_nodes.geojson", driver="GeoJSON")
    report = {"edges": len(edges), "buildings": len(buildings), "trees": len(trees), "time_rows": len(scored), "weather_start": str(weather.timestamp.min()), "weather_end": str(weather.timestamp.max())}
    (out / "run_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if start and end:
        route_all_modes(edges, scored, start, end, route_time or scored.timestamp.max(), cfg, out)
    return report


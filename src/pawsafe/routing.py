from __future__ import annotations

import heapq
import json
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point


def _node_key(x, y, snap):
    return (round(x / snap) * snap, round(y / snap) * snap)


def build_graph(edges: gpd.GeoDataFrame, cfg: dict):
    graph = nx.MultiGraph()
    snap = cfg["geometry"]["node_snap_m"]
    rows = []

    # MultiLineString을 LineString으로 분리
    exploded = edges.explode(
        index_parts=False
    ).reset_index(drop=True)

    for _, row in exploded.iterrows():
        geom = row.geometry

        if geom is None or geom.is_empty:
            continue

        if geom.geom_type != "LineString":
            continue

        coordinates = list(geom.coords)

        if len(coordinates) < 2:
            continue

        # 긴 도로의 시작·끝만 연결하지 않고,
        # 모든 중간 꼭짓점을 노드로 사용
        for segment_index in range(
            len(coordinates) - 1
        ):
            start_coordinate = coordinates[
                segment_index
            ]
            end_coordinate = coordinates[
                segment_index + 1
            ]

            u = _node_key(
                start_coordinate[0],
                start_coordinate[1],
                snap,
            )

            v = _node_key(
                end_coordinate[0],
                end_coordinate[1],
                snap,
            )

            if u == v:
                continue

            segment_geometry = LineString(
                [start_coordinate, end_coordinate]
            )

            segment_length = float(
                segment_geometry.length
            )

            if segment_length <= 0:
                continue

            graph.add_node(
                u,
                x=u[0],
                y=u[1],
            )

            graph.add_node(
                v,
                x=v[0],
                y=v[1],
            )

            graph.add_edge(
                u,
                v,
                edge_id=row["edge_id"],
                segment_index=segment_index,
                length_m=segment_length,
                geometry=segment_geometry,
            )

            rows.append(
                {
                    "edge_id": row["edge_id"],
                    "segment_index": segment_index,
                    "u": u,
                    "v": v,
                    "length_m": segment_length,
                }
            )

    return graph, pd.DataFrame(rows)

def nearest_node(graph, xy):
    nodes = np.array(list(graph.nodes), dtype=float)
    i = np.argmin((nodes[:, 0] - xy[0]) ** 2 + (nodes[:, 1] - xy[1]) ** 2)
    return tuple(nodes[i])


def route(graph, start_xy, end_xy, heat_by_edge: dict, heat_weight: float):
    if not 0 <= heat_weight <= 1:
        raise ValueError("heat_weight는 0 이상 1 이하이어야 합니다.")

    start = nearest_node(graph, start_xy)
    end = nearest_node(graph, end_xy)

    def edge_weight(data):
        edge_heat = float(heat_by_edge.get(data["edge_id"], 50))
        normalized_heat = edge_heat / 100

        return data["length_m"] * (
            (1 - heat_weight)
            + heat_weight * (0.25 + 1.75 * normalized_heat)
        )

    def weight(u, v, attrs):
        return min(edge_weight(data) for data in attrs.values())

    nodes = nx.shortest_path(
        graph,
        start,
        end,
        weight=weight,
        method="dijkstra",
    )

    edge_ids = []
    geoms = []
    segments = []

    total_len = 0.0
    exposure = 0.0

    for u, v in zip(nodes[:-1], nodes[1:]):
        choices = graph.get_edge_data(u, v)
        selected = min(choices.values(), key=edge_weight)

        edge_id = selected["edge_id"]
        length_m = float(selected["length_m"])
        heat_cost = float(heat_by_edge.get(edge_id, 50))
        geometry = selected["geometry"]

        edge_ids.append(edge_id)
        geoms.append(geometry)

        total_len += length_m
        exposure += length_m * heat_cost / 100

        segments.append({
            "edge_id": edge_id,
            "length_m": length_m,
            "heat_cost": heat_cost,
            "geometry": geometry,
        })

    coords = []

    for geom in geoms:
        current_coords = list(geom.coords)

        if coords:
            previous_point = Point(coords[-1])

            if (
                previous_point.distance(Point(current_coords[-1]))
                < previous_point.distance(Point(current_coords[0]))
            ):
                current_coords.reverse()

        coords.extend(current_coords if not coords else current_coords[1:])

    return {
        "edge_ids": edge_ids,
        "distance_m": total_len,
        "mean_heat_cost": exposure / total_len if total_len else None,
        "geometry": LineString(coords) if len(coords) > 1 else None,
        "segments": segments,
    }
def route_all_modes(
    edges,
    edge_time,
    start_lonlat,
    end_lonlat,
    timestamp,
    cfg,
    output_dir: Path,
):
    output_dir.mkdir(parents=True, exist_ok=True)

    graph, lookup = build_graph(edges, cfg)

    pts = gpd.GeoSeries(
        [Point(start_lonlat), Point(end_lonlat)],
        crs=4326,
    ).to_crs(cfg["project_crs"])

    requested_time = pd.Timestamp(timestamp)
    available_times = pd.to_datetime(edge_time["timestamp"])

    matched_time = available_times.iloc[
        np.argmin(abs(available_times - requested_time))
    ]

    snapshot = edge_time[
        pd.to_datetime(edge_time["timestamp"]) == matched_time
    ]

    heat_by_edge = dict(zip(snapshot.edge_id, snapshot.heat_cost))

    route_features = []
    segment_features = []
    metric_rows = []

    summary = {
        "requested_timestamp": str(requested_time),
        "matched_timestamp": str(matched_time),
        "routes": {},
    }

    for mode, settings in cfg["routing"]["modes"].items():
        result = route(
            graph,
            pts.iloc[0].coords[0],
            pts.iloc[1].coords[0],
            heat_by_edge,
            settings["heat_weight"],
        )

        summary["routes"][mode] = {
            "edge_ids": result["edge_ids"],
            "distance_m": result["distance_m"],
            "mean_heat_cost": result["mean_heat_cost"],
        }

        route_features.append({
            "mode": mode,
            "distance_m": result["distance_m"],
            "mean_heat_cost": result["mean_heat_cost"],
            "geometry": result["geometry"],
        })

        for order, segment in enumerate(result["segments"], start=1):
            segment_features.append({
                "mode": mode,
                "segment_order": order,
                "edge_id": segment["edge_id"],
                "length_m": segment["length_m"],
                "heat_cost": segment["heat_cost"],
                "geometry": segment["geometry"],
            })

        segment_table = pd.DataFrame([
            {
                "length_m": segment["length_m"],
                "heat_cost": segment["heat_cost"],
            }
            for segment in result["segments"]
        ])

        total_distance = float(segment_table["length_m"].sum())

        high_heat_distance = float(
            segment_table.loc[
                segment_table["heat_cost"] >= 80,
                "length_m",
            ].sum()
        )

        low_heat_distance = float(
            segment_table.loc[
                segment_table["heat_cost"] <= 60,
                "length_m",
            ].sum()
        )

        metric_rows.append({
            "mode": mode,
            "distance_m": total_distance,
            "mean_heat_cost_100": result["mean_heat_cost"] * 100,
            "high_heat_distance_m": high_heat_distance,
            "high_heat_ratio_pct": (
                high_heat_distance / total_distance * 100
                if total_distance > 0 else 0
            ),
            "low_heat_distance_m": low_heat_distance,
            "low_heat_ratio_pct": (
                low_heat_distance / total_distance * 100
                if total_distance > 0 else 0
            ),
            "edge_segment_count": len(result["segments"]),
        })

    route_gdf = gpd.GeoDataFrame(
        route_features,
        crs=cfg["project_crs"],
    ).to_crs(4326)

    route_gdf.to_file(
        output_dir / "route_comparison.geojson",
        driver="GeoJSON",
    )

    segment_gdf = gpd.GeoDataFrame(
        segment_features,
        crs=cfg["project_crs"],
    ).to_crs(4326)

    segment_gdf.to_file(
        output_dir / "route_segments.geojson",
        driver="GeoJSON",
    )

    metrics = pd.DataFrame(metric_rows)

    metrics.to_csv(
        output_dir / "route_metrics.csv",
        index=False,
        encoding="utf-8-sig",
    )

    (output_dir / "route_comparison.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return summary


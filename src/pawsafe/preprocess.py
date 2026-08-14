from __future__ import annotations

import re
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, box

from .utils import find_column, read_csv_auto


def _layer(path: str, preferred: str | None = None) -> str | None:
    if preferred:
        return preferred
    try:
        import pyogrio
        layers = pyogrio.list_layers(path)
        return str(layers[0, 0]) if len(layers) else None
    except Exception:
        return None


def load_boundary(cfg: dict) -> gpd.GeoDataFrame:
    path = cfg["files"]["boundary"]
    gdf = gpd.read_file(path, layer=_layer(path, cfg["layers"].get("boundary")))
    return gdf.to_crs(cfg["project_crs"])


def load_walkways(cfg: dict, boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    path = cfg["files"]["walkways"]
    gdf = gpd.read_file(path, layer=_layer(path, cfg["layers"].get("walkways")))
    gdf = gdf.to_crs(cfg["project_crs"])
    gdf = gpd.clip(gdf, boundary).explode(index_parts=False).reset_index(drop=True)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    if "fclass" in gdf:
        allowed = {"footway", "path", "steps", "pedestrian", "living_street", "residential", "service"}
        gdf = gdf[gdf["fclass"].isin(allowed)].copy()
    gdf["edge_id"] = [f"E{i:07d}" for i in range(len(gdf))]
    gdf["length_m"] = gdf.length
    return gdf[gdf.length > 0].reset_index(drop=True)


def _extract_shapefile(zip_path: str, root: Path) -> Path:
    target = root / "data" / "processed" / "buildings_extracted"
    target.mkdir(parents=True, exist_ok=True)
    if not list(target.rglob("*.shp")):
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(target)
    shp = list(target.rglob("*.shp"))
    if not shp:
        raise FileNotFoundError("건물 ZIP 안에서 SHP를 찾지 못했습니다.")
    return shp[0]


def _building_register_heights(path: str) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame()
    df = read_csv_auto(path)
    sigungu = find_column(df, ["시군구코드"], False)
    beop = find_column(df, ["법정동코드"], False)
    main = find_column(df, ["번"], False)
    sub = find_column(df, ["지"], False)
    height = find_column(df, ["높이(m)", "높이", "건물높이"], False)
    floors = find_column(df, ["지상층수"], False)
    if not all([sigungu, beop, main, sub]):
        return pd.DataFrame()
    out = pd.DataFrame({
        "BJCD": df[sigungu].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5)
                + df[beop].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(5),
        "BONU": pd.to_numeric(df[main], errors="coerce").fillna(0).astype(int),
        "BUNU": pd.to_numeric(df[sub], errors="coerce").fillna(0).astype(int),
        "register_height_m": pd.to_numeric(df[height], errors="coerce") if height else np.nan,
        "register_floors": pd.to_numeric(df[floors], errors="coerce") if floors else np.nan,
    })
    return out.groupby(["BJCD", "BONU", "BUNU"], as_index=False).max(numeric_only=True)


def load_buildings(cfg: dict, boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    root = Path(cfg["_root"])
    shp = _extract_shapefile(cfg["files"]["buildings_zip"], root)
    bbox = tuple(boundary.to_crs(5179).total_bounds)
    gdf = gpd.read_file(shp, bbox=bbox).to_crs(cfg["project_crs"])
    gdf = gpd.clip(gdf, boundary)
    for c in ("BJCD", "BONU", "BUNU"):
        if c not in gdf:
            gdf[c] = ""
    gdf["BONU"] = pd.to_numeric(gdf["BONU"], errors="coerce").fillna(0).astype(int)
    gdf["BUNU"] = pd.to_numeric(gdf["BUNU"], errors="coerce").fillna(0).astype(int)
    reg = _building_register_heights(cfg["files"]["building_register"])
    if not reg.empty:
        gdf = gdf.merge(reg, on=["BJCD", "BONU", "BUNU"], how="left")
    floors = pd.to_numeric(gdf.get("NMLY", np.nan), errors="coerce")
    if "register_floors" in gdf:
        floors = gdf["register_floors"].fillna(floors)
    estimated = floors * cfg["geometry"]["default_floor_height_m"]
    measured = gdf.get("register_height_m", pd.Series(np.nan, index=gdf.index))
    gdf["height_m"] = measured.where(measured > 0, estimated).fillna(cfg["geometry"]["default_building_height_m"])
    return gdf[["height_m", "geometry"]].reset_index(drop=True)


def load_trees(cfg: dict, boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    df = read_csv_auto(cfg["files"]["street_trees"])
    cols = cfg["columns"]
    lon = find_column(df, cols["tree_lon"]); lat = find_column(df, cols["tree_lat"])
    height = find_column(df, cols["tree_height"], False)
    crown = find_column(df, cols["tree_crown_width"], False)
    district = find_column(df, cols["tree_district"], False)
    x, y = pd.to_numeric(df[lon], errors="coerce"), pd.to_numeric(df[lat], errors="coerce")
    mask = x.between(120, 135) & y.between(30, 40)
    if district:
        mask &= df[district].astype(str).str.contains("송파", na=False)
    out = gpd.GeoDataFrame({
        "height_m": pd.to_numeric(df.loc[mask, height], errors="coerce") if height else cfg["geometry"]["default_tree_height_m"],
        "crown_width_m": pd.to_numeric(df.loc[mask, crown], errors="coerce") if crown else cfg["geometry"]["default_tree_crown_width_m"],
    }, geometry=gpd.points_from_xy(x[mask], y[mask]), crs=4326).to_crs(cfg["project_crs"])
    out["height_m"] = out["height_m"].where(out["height_m"].between(1, 40), cfg["geometry"]["default_tree_height_m"])
    out["crown_width_m"] = out["crown_width_m"].where(out["crown_width_m"].between(0.5, 30), cfg["geometry"]["default_tree_crown_width_m"])
    return gpd.clip(out, boundary).reset_index(drop=True)


def load_weather(cfg: dict) -> pd.DataFrame:
    df = read_csv_auto(cfg["files"]["asos"])
    cols = cfg["columns"]
    mapping = {
        "timestamp": "asos_time", "air_temperature_c": "air_temperature",
        "humidity_pct": "humidity", "wind_speed_ms": "wind_speed",
        "rainfall_mm": "rainfall", "solar_radiation_mj_m2": "solar_radiation"
    }
    out = pd.DataFrame()
    for new, key in mapping.items():
        c = find_column(df, cols[key], required=(new in {"timestamp", "air_temperature_c", "solar_radiation_mj_m2"}))
        out[new] = df[c] if c else np.nan
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    for c in out.columns.drop("timestamp"):
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna(subset=["timestamp"]).sort_values("timestamp")
    out["rainfall_mm"] = out["rainfall_mm"].fillna(0)
    out["wind_speed_ms"] = out["wind_speed_ms"].interpolate(limit_direction="both").fillna(0)
    out["humidity_pct"] = out["humidity_pct"].interpolate(limit_direction="both")
    out["solar_radiation_mj_m2"] = out["solar_radiation_mj_m2"].fillna(0).clip(lower=0)
    return out.reset_index(drop=True)


def attach_pavement(
    cfg: dict,
    edges: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    path = Path(cfg["files"]["pavement"])

    edges = edges.copy()
    edges["surface_code"] = "unknown"

    unknown_absorptivity = cfg["heat"]["surface_absorptivity"]["unknown"]

    # 포장재 파일이 없으면 모든 Edge를 unknown으로 처리
    if not path.exists():
        edges["surface_absorptivity"] = unknown_absorptivity
        return edges

    df = read_csv_auto(path)
    columns = cfg["columns"]

    names = {
        key: find_column(df, columns[key], False)
        for key in (
            "pavement_code",
            "pavement_xmin",
            "pavement_ymin",
            "pavement_xmax",
            "pavement_ymax",
        )
    }

    # 필요한 컬럼이 없으면 모든 Edge를 unknown으로 처리
    if not all(names.values()):
        edges["surface_absorptivity"] = unknown_absorptivity
        return edges

    scale = cfg["geometry"]["pavement_coordinate_scale"]

    xmin = (
        pd.to_numeric(
            df[names["pavement_xmin"]],
            errors="coerce",
        )
        / scale
    )

    ymin = (
        pd.to_numeric(
            df[names["pavement_ymin"]],
            errors="coerce",
        )
        / scale
    )

    xmax = (
        pd.to_numeric(
            df[names["pavement_xmax"]],
            errors="coerce",
        )
        / scale
    )

    ymax = (
        pd.to_numeric(
            df[names["pavement_ymax"]],
            errors="coerce",
        )
        / scale
    )

    valid = (
        xmin.notna()
        & ymin.notna()
        & xmax.notna()
        & ymax.notna()
        & (xmax >= xmin)
        & (ymax >= ymin)
    )

    surface_codes = (
        df.loc[valid, names["pavement_code"]]
        .astype(str)
        .str.strip()
        .replace(
            {
                "-": "unknown",
                "": "unknown",
                "nan": "unknown",
                "None": "unknown",
            }
        )
    )

    # 최소·최대 좌표로 포장재 사각형 영역 생성
    pavement = gpd.GeoDataFrame(
        {
            "surface_code": surface_codes.to_numpy(),
        },
        geometry=[
            box(x1, y1, x2, y2)
            for x1, y1, x2, y2 in zip(
                xmin[valid],
                ymin[valid],
                xmax[valid],
                ymax[valid],
            )
        ],
        crs="EPSG:5181",
    )

    # 구형 서울 좌표계에서 프로젝트 좌표계로 변환
    pavement = pavement.to_crs(cfg["project_crs"])

    # 1차 결합: 포장재 영역과 실제로 교차하는 Edge
    candidates = gpd.sjoin(
        edges[["edge_id", "geometry"]],
        pavement[["surface_code", "geometry"]],
        how="left",
        predicate="intersects",
    )

    candidates = candidates.dropna(subset=["index_right"]).copy()

    if not candidates.empty:
        candidates["index_right"] = candidates["index_right"].astype(int)

        # 한 Edge가 여러 포장 영역과 겹칠 경우
        # 가장 길게 겹치는 포장재를 선택
        candidates["overlap_length_m"] = candidates.apply(
            lambda row: row.geometry.intersection(
                pavement.geometry.loc[row["index_right"]]
            ).length,
            axis=1,
        )

        best_matches = (
            candidates.sort_values(
                ["edge_id", "overlap_length_m"],
                ascending=[True, False],
            )
            .drop_duplicates("edge_id")
        )

        intersection_map = dict(
            zip(
                best_matches["edge_id"],
                best_matches["surface_code"],
            )
        )

        edges["surface_code"] = (
            edges["edge_id"]
            .map(intersection_map)
            .fillna("unknown")
        )

    # 2차 보완: 아직 unknown인 Edge에 가까운 포장재 연결
    missing_edges = edges.loc[
        edges["surface_code"].eq("unknown"),
        ["edge_id", "geometry"],
    ].copy()

    if not missing_edges.empty:
        pavement_centres = pavement.copy()
        pavement_centres["geometry"] = pavement_centres.geometry.centroid

        nearest = gpd.sjoin_nearest(
            missing_edges,
            pavement_centres[["surface_code", "geometry"]],
            how="left",
            max_distance=cfg["geometry"][
                "pavement_join_max_distance_m"
            ],
            distance_col="pavement_distance_m",
        )

        nearest = (
            nearest.sort_values("pavement_distance_m")
            .drop_duplicates("edge_id")
        )

        nearest = nearest[
            nearest["surface_code"].notna()
            & ~nearest["surface_code"].isin(
                ["unknown", "-", "", "nan", "None"]
            )
        ]

        nearest_map = dict(
            zip(
                nearest["edge_id"],
                nearest["surface_code"],
            )
        )

        nearest_values = edges["edge_id"].map(nearest_map)
        fill_mask = (
            edges["surface_code"].eq("unknown")
            & nearest_values.notna()
        )

        edges.loc[fill_mask, "surface_code"] = nearest_values[fill_mask]

    # 결측 코드 정리
    edges["surface_code"] = (
        edges["surface_code"]
        .fillna("unknown")
        .astype(str)
        .str.strip()
        .replace(
            {
                "-": "unknown",
                "": "unknown",
                "nan": "unknown",
                "None": "unknown",
            }
        )
    )

    # 포장재 코드에 따른 흡수율 적용
    edges["surface_absorptivity"] = (
        edges["surface_code"]
        .map(cfg["heat"]["surface_absorptivity"])
        .fillna(unknown_absorptivity)
    )

    return edges.reset_index(drop=True)
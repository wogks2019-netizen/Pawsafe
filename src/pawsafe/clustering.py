from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from .utils import minmax, read_csv_auto


def fit_clusters(features: pd.DataFrame, cfg: dict, output_dir: Path):
    cols = cfg["clustering"]["features"]
    xdf = features[cols].replace([np.inf, -np.inf], np.nan)
    xdf = xdf.fillna(xdf.median(numeric_only=True)).fillna(0)
    scaler = StandardScaler(); X = scaler.fit_transform(xdf)
    rng = np.random.default_rng(cfg["clustering"]["random_state"])
    limit = cfg["clustering"]["sample_limit"]
    eval_idx = rng.choice(len(X), min(limit, len(X)), replace=False)
    rows, candidates = [], {}
    for k in cfg["clustering"]["k_values"]:
        if k >= len(X):
            continue
        for kind in ("kmeans", "gmm"):
            model = KMeans(k, n_init=20, random_state=cfg["clustering"]["random_state"]) if kind == "kmeans" else GaussianMixture(k, covariance_type="full", random_state=cfg["clustering"]["random_state"])
            labels = model.fit_predict(X)
            s = silhouette_score(X[eval_idx], labels[eval_idx]) if len(np.unique(labels[eval_idx])) > 1 else -1
            d = davies_bouldin_score(X[eval_idx], labels[eval_idx]) if len(np.unique(labels[eval_idx])) > 1 else np.inf
            rows.append({"model": kind, "k": k, "silhouette": s, "davies_bouldin": d})
            candidates[(kind, k)] = (model, labels)
    metrics = pd.DataFrame(rows)
    metrics["selection_score"] = metrics["silhouette"].rank(pct=True) + (-metrics["davies_bouldin"]).rank(pct=True)
    best = metrics.sort_values(["selection_score", "silhouette"], ascending=False).iloc[0]
    model, labels = candidates[(best["model"], int(best["k"]))]
    result = features.copy(); result["cluster"] = labels
    if best["model"] == "gmm":
        probs = model.predict_proba(X)
    else:
        probs = np.eye(int(best["k"]))[labels]

    z = pd.DataFrame(X, columns=cols)
    z["cluster"] = labels
    profiles_z = z.groupby("cluster")[cols].mean()
    weights = pd.Series(cfg["clustering"]["heat_direction_weights"]).reindex(cols).fillna(0)
    raw_cluster_heat = profiles_z.mul(weights, axis=1).sum(axis=1)
    cluster_heat = minmax(raw_cluster_heat)
    result["heat_cost"] = probs @ cluster_heat.sort_index().to_numpy()
    profiles = result.groupby("cluster")[cols + ["heat_cost"]].mean().reset_index()
    model_bundle = {"scaler": scaler, "model": model, "features": cols, "model_type": best["model"], "k": int(best["k"]), "cluster_heat": cluster_heat.to_dict()}
    joblib.dump(model_bundle, output_dir / "heat_cluster_model.joblib")
    metrics.to_csv(output_dir / "cluster_metrics.csv", index=False, encoding="utf-8-sig")
    profiles.to_csv(output_dir / "cluster_profiles.csv", index=False, encoding="utf-8-sig")
    (output_dir / "model_selection.json").write_text(json.dumps(best.to_dict(), ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    return result, metrics, profiles


def validate_optional(result: pd.DataFrame, cfg: dict, output_dir: Path):
    path = Path(cfg["files"]["measured_surface_temperature"])
    if not path.exists():
        pd.DataFrame(columns=["edge_id", "timestamp", "surface_temperature_c"]).to_csv(path, index=False, encoding="utf-8-sig")
        return None
    measured = read_csv_auto(path)
    if measured.empty or not {"edge_id", "timestamp", "surface_temperature_c"}.issubset(measured):
        return None
    measured["timestamp"] = pd.to_datetime(measured["timestamp"])
    joined = result.merge(measured, on=["edge_id", "timestamp"])
    if len(joined) < 5:
        return None
    report = {"n": len(joined), "spearman_heat_cost_vs_surface_temp": float(joined["heat_cost"].corr(joined["surface_temperature_c"], method="spearman"))}
    (output_dir / "field_validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


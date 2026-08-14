from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pandas as pd


def load_config(path: str | Path) -> dict:
    path = Path(path).resolve()
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg["_root"] = str(path.parent)
    for key, value in cfg["files"].items():
        cfg["files"][key] = str((path.parent / value).resolve())
    return cfg


def find_column(df: pd.DataFrame, candidates: Iterable[str], required: bool = True) -> str | None:
    normalized = {str(c).replace(" ", "").lower(): c for c in df.columns}
    for candidate in candidates:
        key = str(candidate).replace(" ", "").lower()
        if key in normalized:
            return normalized[key]
    if required:
        raise KeyError(f"필수 컬럼을 찾지 못했습니다. 후보={list(candidates)}, 실제={list(df.columns)}")
    return None


def read_csv_auto(path: str | Path, **kwargs) -> pd.DataFrame:
    errors = []
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False, **kwargs)
        except UnicodeDecodeError as exc:
            errors.append(str(exc))
    raise ValueError(f"CSV 인코딩을 판별하지 못했습니다: {path}; {errors[-1]}")


def minmax(series: pd.Series) -> pd.Series:
    lo, hi = series.min(), series.max()
    if pd.isna(lo) or hi <= lo:
        return pd.Series(50.0, index=series.index)
    return 100.0 * (series - lo) / (hi - lo)


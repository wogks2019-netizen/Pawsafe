from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from src.pawsafe.pipeline import run
from src.pawsafe.utils import load_config


def lonlat(value: str):
    lon, lat = map(float, value.split(","))
    return lon, lat


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="PawSafe 전처리→열환경 군집→경로추천 파이프라인")
    p.add_argument("--config", default="config.json")
    p.add_argument("--start", type=lonlat, help="출발점 경도,위도")
    p.add_argument("--end", type=lonlat, help="도착점 경도,위도")
    p.add_argument("--time", help="산책시각, 예: 2026-08-08 15:00")
    args = p.parse_args()
    if bool(args.start) != bool(args.end):
        p.error("--start와 --end는 함께 입력해야 합니다.")
    print(run(load_config(args.config), args.start, args.end, args.time))

"""무거운 그림자 계산 전에 파일 존재 여부와 공간 레이어를 점검한다."""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from src.pawsafe.utils import load_config


if __name__ == "__main__":
    cfg = load_config("config.json")
    required = {"walkways", "boundary", "buildings_zip", "asos"}
    failed = False
    for key, value in cfg["files"].items():
        exists = Path(value).exists()
        state = "OK" if exists else ("MISSING(필수)" if key in required else "MISSING(선택)")
        print(f"{key:32s} {state:14s} {value}")
        failed |= key in required and not exists
    if failed:
        raise SystemExit("필수 파일을 data/raw에 배치하거나 config.json 경로를 수정하세요.")
    print("필수 파일 확인 완료")

# PawSafe 분석·경로추천 파이프라인

> 팀 공유용 정리본은 안내문을 `docs/01_프로젝트_안내/`에, 실행 스크립트를 `scripts/`에 모았습니다. 처음 보는 팀원은 프로젝트 루트의 `README.md`부터 읽어주세요.

송파구 보행로를 `Edge × 시간` 단위로 만들고, 건물·가로수 그림자와 ASOS 일사·기상, 포장재를 결합해 **상대적 노면 열노출**을 계산합니다. K-means와 GMM을 비교한 뒤 선택 모델의 군집을 Heat Cost(0~100)로 해석하고, 거리와 Heat Cost를 함께 사용해 산책 경로를 추천합니다.

> 이 결과는 실측 노면온도(℃)의 대체물이 아닙니다. 현재 정답값(Y)이 부족하므로 서비스 출력은 “예상 상대 열노출”입니다. 실측 온도 파일을 추가하면 방향성 검증까지 자동 수행합니다.

## 1. 전체 흐름과 선택 근거

| 단계 | 수행 내용 | 이렇게 한 이유 |
|---|---|---|
| 공간 전처리 | 보행로·건물·가로수를 EPSG:5186으로 통일하고 송파구로 자름 | 거리, 높이, 그림자 길이는 미터 좌표계에서 계산해야 함 |
| 포장재 결합 | SWM 포장 지점/영역을 가까운 Edge와 결합 | 포장재에 따라 단파복사 흡수율이 달라짐. 알 수 없는 구간은 별도 코드 처리 |
| 태양·그림자 | PySolar 태양고도·방위각과 건물 높이·수관으로 시간대별 그림자 생성 | ASOS 일조시간만으로는 어느 도로가 그늘인지 알 수 없기 때문 |
| 누적 일사 | `일사 × (1-그늘비율) × 흡수율`의 최근 6시간 합 | 같은 현재 일사라도 이전에 오래 햇빛을 받은 노면은 더 많은 열을 저장할 수 있음 |
| 열저장 상태 | 태양 입력은 더하고, 시간·바람·강수에 따라 지수적으로 감소 | 뉴턴 냉각 개념을 이용한 1차 열관성 근사. 절대온도식이 아닌 상대 피처 |
| 군집 | 표준화 후 K-means/GMM, k=2~5 비교 | 정답값 없이 반복되는 열환경 유형을 찾기 위함. 비구형 군집 가능성 때문에 GMM도 비교 |
| 모델 선택 | Silhouette↑, Davies–Bouldin↓를 함께 평가 | 군집 분리도와 군집 내부 응집도를 동시에 확인 |
| Heat Cost | 군집 프로필에 물리적 방향 가중치를 적용해 0~100 변환 | 군집 번호 자체에는 고온/저온 의미가 없으므로 해석 단계가 필요 |
| 경로 | Edge 길이에 Heat Cost 패널티를 더해 Dijkstra 수행 | 최단거리와 열노출 사이의 trade-off를 명시적으로 조정 가능 |

## 2. 데이터 배치

`data/raw/` 아래에 다음 이름으로 놓습니다. 원본 이름을 바꾸기 어렵다면 `config.json` 경로만 수정합니다.

| 파일명 | 원본 | 필수 여부 |
|---|---|---|
| `songpa_walkways.gpkg` | 송파구 OSM 보행로 | 필수 |
| `songpa_boundary.gpkg` | 송파구 경계 | 필수 |
| `buildings_seoul.zip` | 연속수치지형도 건물 서울 ZIP | 필수 |
| `building_register.csv` | 건축물대장 표제부 | 권장; 없으면 층수×3m |
| `street_trees.csv` | 서울시 가로수 위치 | 권장 |
| `asos_hourly.csv` | 기상청 ASOS 시간자료 | 필수 |
| `SWM_WKAR_AS.csv` | 서울시 보도 포장 공간자료 | 권장 |
| `SWM_BASIC_CODE.csv` | 포장 코드표 | 설명용 |
| `measured_surface_temperature.csv` | 직접 측정한 선택 자료 | 선택 |

건물 ZIP은 압축을 풀지 않아도 됩니다. 코드가 최초 실행 시 `data/processed/buildings_extracted/`에 풉니다.

## 3. 설치와 실행

Windows PowerShell 기준:

```powershell
cd pawsafe_pipeline
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/00_실행환경_확인.py
python scripts/01_전체_전처리_군집화_실행.py --start 127.1000,37.5100 --end 127.1200,37.5050 --time "2026-08-08 15:00"
```

경로를 만들지 않고 데이터·모델만 생성하려면:

```powershell
python scripts/01_전체_전처리_군집화_실행.py
```

시간 범위가 너무 크면 건물 그림자 계산량이 커집니다. 해커톤 PoC에서는 `config.json`의 `time.start`, `time.end`를 폭염일 1일, 간격을 60분으로 두는 것을 권장합니다.

## 4. 주요 산출물

| 파일 | 네이티브 앱 사용법 |
|---|---|
| `outputs/edge_heat_latest.geojson` | 지도 위 도로별 Heat Cost 색상 표시 |
| `outputs/route_comparison.geojson` | fast/cool 경로 선 표시 |
| `outputs/route_comparison.json` | 거리, 평균 Heat Cost, Edge 목록 표시 |
| `outputs/graph_nodes.geojson` | 출발·도착점 스냅 또는 디버깅 |
| `outputs/cluster_metrics.csv` | K-means/GMM 평가표 |
| `outputs/cluster_profiles.csv` | 군집별 열환경 특징 설명 |
| `outputs/heat_cluster_model.joblib` | 동일 피처에 군집 재적용 |
| `data/processed/edge_time_features.parquet` | 서버/앱 백엔드용 전체 시간 데이터 |

자세한 필드와 앱 계약은 [NATIVE_APP_HANDOFF.md](NATIVE_APP_HANDOFF.md), 방법론 한계는 [METHODOLOGY.md](METHODOLOGY.md)를 참고합니다.

## 5. 경로 모드

- `fast`: 열 가중치 0.00 — 거리 우선
- `cool`: 0.95 — 열노출 감소 우선

모든 모드는 같은 Edge 길이를 사용하며, Heat Cost가 높은 Edge의 유효 비용만 더 크게 만듭니다. 따라서 1.5km의 그늘길이 1km의 노출길보다 항상 선택되는 것이 아니라 선택 모드와 실제 Heat Cost 차이에 따라 결정됩니다.

## 6. 실측 검증

`data/raw/measured_surface_temperature.csv`에 다음 형태로 5개 이상 넣으면 Spearman 순위상관을 계산합니다.

```csv
edge_id,timestamp,surface_temperature_c
E0000123,2026-08-08 15:00,44.2
```

절대 오차보다 “Heat Cost가 높은 구간이 실제로도 더 뜨거운가”를 먼저 확인합니다. ℃ 예측으로 확장하려면 더 많은 시공간 실측값으로 별도 회귀모델을 학습해야 합니다.

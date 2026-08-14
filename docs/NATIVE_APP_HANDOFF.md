# 네이티브 앱 연동 규격

앱 팀에는 `outputs/`의 GeoJSON/JSON만 전달하면 됩니다. Python 모델을 모바일 앱 안에서 실행할 필요는 없습니다.

## 지도 Heat Layer

`edge_heat_latest.geojson`의 각 Feature 주요 속성:

| 필드 | 타입 | 의미 |
|---|---|---|
| `edge_id` | string | 보행 Edge 고유키 |
| `length_m` | number | 길이(m) |
| `surface_code` | string | 포장재 코드 또는 unknown |
| `timestamp` | datetime string | Heat Cost 기준시각 |
| `cluster` | integer | 선택 군집 번호; 번호 자체에 순서 의미 없음 |
| `heat_cost` | number | 상대 열노출 0~100 |

색상 권장: 0~33 청록, 34~66 주황, 67~100 빨강. 사용자에게는 “예상 상대 열노출”로 표기합니다.

## 경로 결과

`route_comparison.json`:

```json
{
  "requested_timestamp": "2026-08-08 15:00:00",
  "matched_timestamp": "2026-08-08 15:00:00",
  "routes": {
    "fast": {"edge_ids": ["E..."], "distance_m": 950, "mean_heat_cost": 61.2},
    "cool": {"edge_ids": ["E..."], "distance_m": 1230, "mean_heat_cost": 28.1}
  }
}
```

실제 선 좌표는 `route_comparison.geojson`에서 mode로 구분합니다. 앱은 일반적으로 다음을 표시하면 됩니다.

1. 지도 위 두 경로 또는 선택 경로
2. 총거리와 예상 도보시간
3. 평균 Heat Cost
4. 최단경로 대비 우회거리와 Heat Cost 감소율

## 서버화 시 권장 API

- `GET /heat-map?time=...` → Edge Heat GeoJSON
- `POST /routes` body: `{start:[lon,lat], end:[lon,lat], time:"..."}` → Fast·Cool 두 경로
- `GET /model-info` → 모델 종류, k, 입력시각, 한계 문구

현재 산출물은 정적 파일이므로 팀원이 네이티브 앱에 번들로 포함해 PoC를 만들 수 있습니다. 실시간화를 할 때만 이 Python 코드를 서버 배치/API로 감싸면 됩니다.

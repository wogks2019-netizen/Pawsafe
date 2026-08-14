# PawSafe 팀 공유용 정리본

이 폴더는 송파구 보행로의 **상대 열노출을 계산하고, Fast·Cool 경로를 비교하는 PawSafe PoC**입니다.

## 처음 열었을 때 읽는 순서

1. `docs/01_프로젝트_안내/01_데이터_구조_가이드.md` — 데이터가 어떤 단위로 저장되는지
2. `docs/01_프로젝트_안내/02_코드_실행순서.md` — 어느 코드를 어떤 순서로 실행하는지
3. `docs/01_프로젝트_안내/04_현재상태_및_남은작업.md` — 이미 된 것과 추가 작업

## 폴더 구성

```text
PawSafe/
├─ data/raw/          원본 데이터: 보행로·건물·가로수·포장재·기상·IoT
├─ data/processed/    전처리 결과: Edge 고정정보와 Edge×시간 피처
├─ src/pawsafe/       핵심 계산 코드
├─ outputs/           군집·열지도·경로·IoT 검증·앱 전달 결과
├─ docs/              프로젝트 안내·상세 방법론·앱 전달 규격
├─ tests/             핵심 함수 테스트
├─ scripts/           실행 순서가 표시된 00~06 실행 스크립트
├─ config.json        파일경로·결측 기본값·가중치 설정
└─ requirements.txt   설치할 Python 패키지
```

## 현재 데이터 규모

- 보행 Edge: 3,797개
- 시간: 24개 시점
- Edge×시간 데이터: 91,128행
- 포장재 확인 Edge: 784개
- 포장재 미확인 Edge: 3,013개

## 결과 해석 시 주의

- Heat Cost는 실제 노면온도(℃)가 아니라 **상대 열노출 점수**입니다.
- 포장재가 없는 Edge는 `unknown`, 흡수율 0.75로 추정합니다.
- 현재 임시 경로는 포장재 실데이터와 추정 구간이 섞여 있습니다.
- 잠실 IoT 결과는 환경별 방향성 검증이며, 아직 특정 Edge와 직접 연결한 검증은 아닙니다.

## 정리본에서 제외한 파일

- `.venv/`: PC마다 다시 만드는 가상환경
- `__pycache__/`: 실행 시 자동 생성되는 캐시
- `data/processed/buildings_extracted/`: `buildings_seoul.zip`에서 다시 생성 가능
- `desktop.ini` 등 Windows 임시파일

from pathlib import Path
import os
import re

import matplotlib.pyplot as plt
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)


INPUT = Path("data/raw/jamsil_iot_observations.xlsx")
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Windows 한글 폰트
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def clean_environment_name(sheet_name):
    return re.sub(r"^\d+\.", "", sheet_name)


excel = pd.ExcelFile(INPUT)
records = []

for sheet_name in excel.sheet_names:
    # 병합된 머리글이 있으므로 header=None으로 읽음
    raw = pd.read_excel(
        INPUT,
        sheet_name=sheet_name,
        header=None,
    )

    # 22번째 열: '3일 전체'의 지면온도
    ground_temperature = pd.to_numeric(
        raw.iloc[2:, 22],
        errors="coerce",
    ).dropna()

    if ground_temperature.empty:
        print(f"경고: {sheet_name}에서 지면온도를 찾지 못했습니다.")
        continue

    records.append({
        "environment": clean_environment_name(sheet_name),
        "observation_count": len(ground_temperature),
        "ground_mean_c": ground_temperature.mean(),
        "ground_median_c": ground_temperature.median(),
        "ground_min_c": ground_temperature.min(),
        "ground_max_c": ground_temperature.max(),
        "ground_std_c": ground_temperature.std(),
    })


summary = pd.DataFrame(records)
summary = summary.sort_values(
    "ground_mean_c",
    ascending=False,
).reset_index(drop=True)

# 환경 유형 구분
hot_environments = {
    "아스팔트",
    "주택밀집지역",
    "아파트촌",
}

cool_environments = {
    "그늘쉼터",
    "석촌호수공원",
    "도심소공원",
}


def classify_environment(name):
    if name in hot_environments:
        return "고열 예상 환경"
    if name in cool_environments:
        return "저열 예상 환경"
    return "중간 환경"


summary["expected_group"] = summary["environment"].apply(
    classify_environment
)

summary.to_csv(
    OUTPUT_DIR / "iot_validation_summary.csv",
    index=False,
    encoding="utf-8-sig",
)

# 고열 예상 환경과 저열 예상 환경의 평균 비교
hot_mean = summary.loc[
    summary["expected_group"] == "고열 예상 환경",
    "ground_mean_c",
].mean()

cool_mean = summary.loc[
    summary["expected_group"] == "저열 예상 환경",
    "ground_mean_c",
].mean()

temperature_gap = hot_mean - cool_mean
direction_match = hot_mean > cool_mean

validation_result = pd.DataFrame([{
    "hot_environment_mean_c": hot_mean,
    "cool_environment_mean_c": cool_mean,
    "temperature_gap_c": temperature_gap,
    "direction_match": direction_match,
}])

validation_result.to_csv(
    OUTPUT_DIR / "iot_direction_validation.csv",
    index=False,
    encoding="utf-8-sig",
)

# 환경별 색상
colors = []

for group in summary["expected_group"]:
    if group == "고열 예상 환경":
        colors.append("#E64B35")
    elif group == "저열 예상 환경":
        colors.append("#2E86C1")
    else:
        colors.append("#F5B041")

# 막대그래프 생성
fig, ax = plt.subplots(figsize=(11, 6))

bars = ax.bar(
    summary["environment"],
    summary["ground_mean_c"],
    color=colors,
    edgecolor="white",
)

ax.set_title(
    "잠실 환경별 IoT 3일 평균 지면온도",
    fontsize=16,
    fontweight="bold",
)

ax.set_xlabel("관측 환경")
ax.set_ylabel("평균 지면온도(℃)")
ax.tick_params(axis="x", rotation=25)
ax.grid(axis="y", alpha=0.25)

for bar, value in zip(bars, summary["ground_mean_c"]):
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() + 0.3,
        f"{value:.1f}℃",
        ha="center",
        fontsize=10,
    )

fig.text(
    0.5,
    0.01,
    (
        f"고열 예상 환경 평균 {hot_mean:.1f}℃ / "
        f"저열 예상 환경 평균 {cool_mean:.1f}℃ / "
        f"차이 {temperature_gap:.1f}℃"
    ),
    ha="center",
    fontsize=11,
)

plt.tight_layout(rect=[0, 0.05, 1, 1])

plt.savefig(
    OUTPUT_DIR / "iot_validation_chart.png",
    dpi=200,
    bbox_inches="tight",
)

plt.close()

print("\n환경별 지면온도 요약")
print(summary.round(2).to_string(index=False))

print("\n방향성 검증")
print(f"고열 예상 환경 평균: {hot_mean:.2f}℃")
print(f"저열 예상 환경 평균: {cool_mean:.2f}℃")
print(f"평균 차이: {temperature_gap:.2f}℃")
print(f"모델 방향성과 일치: {direction_match}")

print("\n저장 완료")
print("outputs/iot_validation_summary.csv")
print("outputs/iot_direction_validation.csv")
print("outputs/iot_validation_chart.png")

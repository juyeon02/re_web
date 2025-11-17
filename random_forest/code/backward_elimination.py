import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score
from datetime import datetime
import os
from src.utils.model_utils import save_model

# ----------------------------------------------------------
# ✅ macOS 한글 폰트 설정
# ----------------------------------------------------------
plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False


# ----------------------------------------------------------
# 🔧 경로 설정
# ----------------------------------------------------------
BASE_DIR = "/Users/parkhyeji/Desktop/PV"
DATA_PATH = os.path.join(BASE_DIR, "data/outliers_removed/이상치제거_데이터.csv")

RESULT_DIR = os.path.join(BASE_DIR, "src/models/individual/random_forest/results/backward_elimination")
DETAIL_DIR = os.path.join(RESULT_DIR, "details")
PLOT_DIR = os.path.join(BASE_DIR, "src/models/individual/random_forest/plots/backward_elimination")
LOG_DIR = os.path.join(BASE_DIR, "src/models/individual/random_forest/logs/backward_elimination")
MODEL_DIR = os.path.join(BASE_DIR, "outputs/models/individual/random_forest/backward_elimination")

os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(DETAIL_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

SUMMARY_CSV = os.path.join(RESULT_DIR, "RF_backward_elimination.csv")

# ----------------------------------------------------------
# 1️⃣ 데이터 로드 및 결측 처리
# ----------------------------------------------------------
df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")

# ----------------------------------------------------------
# 2️⃣ 열별 결측치 개수 출력
# ----------------------------------------------------------
missing_summary = df.isnull().sum().reset_index()
missing_summary.columns = ['컬럼명', '결측치수']
missing_summary['결측치비율(%)'] = (missing_summary['결측치수'] / len(df) * 100).round(2)

print("\n📊 결측치 요약:")
print(missing_summary.to_string(index=False))

print(f"\n✅ 결측치 처리 완료 — 최종 데이터 {len(df):,}행 유지")

# 발전량 0 제거
df = df[df['발전량(MWh)'] != 0].copy()
print(f"✅ 발전량 0제거 후 데이터 로드 완료 ({len(df)}행)")

base_features = [
    '설비용량(MW)', '평균기온', '평균습도', '총강수량', '총적설량',
    '평균풍속', '일조시간', '일사량', '평균운량'
]

# ----------------------------------------------------------
# 2️⃣ 발전기별 후진제거법 수행
# ----------------------------------------------------------
all_results = []
summary_r2 = {}

for gen_name, group in df.groupby("발전기명"):
    if len(group) < 10:
        print(f"⚠️ {gen_name}: 데이터 부족 → 스킵")
        continue

    print(f"\n[{gen_name}] 후진제거법 시작 ({len(group)}건)")

    features = base_features.copy()
    y = group["발전량(MWh)"]
    min_features = 3
    history, logs, r2_list, step_importances = [], [], [], []

    while len(features) > min_features:
        X = group[features].dropna()
        y_sub = y.loc[X.index]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y_sub, test_size=0.2, random_state=42
        )

        model = RandomForestRegressor(n_estimators=500, random_state=42)
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        r2 = r2_score(y_test, y_pred)
        importances = model.feature_importances_
        least_important = features[np.argmin(importances)]

        # ✅ 모델 저장 (단계별)
        step_model_name = f"rf_full_{gen_name.replace('/', '_')}_step{len(features)}"
        save_model(model, model_name=step_model_name, output_dir=MODEL_DIR)

        logs.append(f"제거: {least_important}, R²={r2:.4f}, 남은 변수={features}")
        r2_list.append(r2)
        step_importances.append(importances)

        history.append({
            "발전기명": gen_name,
            "남은 변수 수": len(features),
            "R²": round(r2, 4),
            "제거된 변수": least_important,
            "남은 변수": ", ".join(features)
        })

        features.remove(least_important)
        print(f"  - 제거: {least_important}, R²={r2:.4f}")

    # ----------------------------------------------------------
    # 3️⃣ 발전기별 상세 CSV 저장
    # ----------------------------------------------------------
    hist_df = pd.DataFrame(history)
    detail_path = os.path.join(DETAIL_DIR, f"{gen_name}_elimination_detail.csv")
    hist_df.to_csv(detail_path, index=False, encoding="utf-8-sig")

    # ----------------------------------------------------------
    # 4️⃣ 로그 파일 저장
    # ----------------------------------------------------------
    log_path = os.path.join(LOG_DIR, f"{gen_name}_log.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"[{gen_name}] 후진제거 로그 ({datetime.now()})\n\n")
        f.write("\n".join(logs))

    # ----------------------------------------------------------
    # 5️⃣ 그래프 저장
    # ----------------------------------------------------------
    # (1) 변수 개수 vs R² 변화
    plt.figure(figsize=(7, 5))
    plt.plot(hist_df["남은 변수 수"], hist_df["R²"], marker="o", color="teal")
    plt.title(f"[{gen_name}] 변수 개수 vs R² 변화")
    plt.xlabel("남은 변수 수")
    plt.ylabel("R²")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, f"{gen_name}_R2변화.png"), dpi=300)
    plt.close()

    # (2) 단계별 변수 중요도 변화
    plt.figure(figsize=(8, 5))
    for step_idx, imp in enumerate(step_importances):
        plt.plot(base_features[:len(imp)], imp, label=f"Step {step_idx+1}")
    plt.title(f"[{gen_name}] 단계별 변수 중요도 변화")
    plt.xlabel("변수명")
    plt.ylabel("중요도")
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, f"{gen_name}_중요도변화.png"), dpi=300)
    plt.close()

    # ✅ 통합 결과
    all_results.extend(history)
    summary_r2[gen_name] = round(max(r2_list), 4)

# ----------------------------------------------------------
# 6️⃣ 전체 요약 저장 + 통합 시각화
# ----------------------------------------------------------
result_df = pd.DataFrame(all_results)
result_df.to_csv(SUMMARY_CSV, index=False, encoding="utf-8-sig")

# (1) 발전기별 최종 R² 비교
plt.figure(figsize=(10, 6))
plt.bar(summary_r2.keys(), summary_r2.values(), color="seagreen")
plt.title("발전기별 후진제거법 최종 R² 비교")
plt.xticks(rotation=45)
plt.ylabel("최종 R²")
plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "전체_R2비교.png"), dpi=300)
plt.close()

# (2) 변수 제거 빈도 분석
removed_var_counts = result_df["제거된 변수"].value_counts()
plt.figure(figsize=(8, 5))
plt.barh(removed_var_counts.index, removed_var_counts.values, color="darkorange")
plt.title("전체 발전기 기준 변수 제거 빈도")
plt.xlabel("제거 횟수")
plt.gca().invert_yaxis()
plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "전체_변수제거빈도.png"), dpi=300)
plt.close()

print("\n✅ 모든 발전기 후진제거법 완료 및 모델 저장 완료!")
print(f"📄 요약 CSV: {SUMMARY_CSV}")
print(f"📁 상세 CSV 폴더: {DETAIL_DIR}")
print(f"🖼️ 그래프 폴더: {PLOT_DIR}")
print(f"🧾 로그 폴더: {LOG_DIR}")
print(f"💾 모델 폴더: {MODEL_DIR}")
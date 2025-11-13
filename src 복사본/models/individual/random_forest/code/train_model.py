# 전체 기상데이터 사용

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_squared_error
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

RESULT_DIR = os.path.join(BASE_DIR, "src/models/individual/random_forest/results/train")
PLOT_DIR = os.path.join(BASE_DIR, "src/models/individual/random_forest/plots/train")
LOG_DIR = os.path.join(BASE_DIR, "src/models/individual/random_forest/logs/train")
MODEL_DIR = os.path.join(BASE_DIR, "outputs/models/individual/random_forest/train")

os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

OUTPUT_CSV = os.path.join(RESULT_DIR, "RF_results.csv")


# ----------------------------------------------------------
# 1️⃣ 데이터 로드 및 결측치 처리
# ----------------------------------------------------------
df = pd.read_csv(DATA_PATH, encoding='utf-8-sig')

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


# ----------------------------------------------------------
# 2️⃣ 발전기별 모델 학습
# ----------------------------------------------------------
results = []

for gen_name, group in df.groupby('발전기명'):
    if len(group) < 10:
        print(f"⚠️ {gen_name}: 데이터 부족으로 스킵 ({len(group)}개)")
        continue

    X = group[['설비용량(MW)', '평균기온', '평균습도', '총강수량', '총적설량',
                '평균풍속', '일조시간', '일사량', '평균운량']]
    y = group['발전량(MWh)']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestRegressor(
        n_estimators=500,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    # ----------------------------------------------------------
    # ✅ 학습된 모델 저장 (발전기별로 개별 파일 생성)
    # ----------------------------------------------------------
    model_name = f"rf_integrated_{gen_name.replace('/', '_').replace(' ', '_')}"  # ✅ 추가
    save_model(model, model_name=model_name, output_dir=MODEL_DIR)

    # ----------------------------------------------------------
    # 3️⃣ 성능지표 계산
    # ----------------------------------------------------------
    r2 = r2_score(y_test, y_pred)
    rmse = mean_squared_error(y_test, y_pred) ** 0.5
    mape = np.mean(np.abs((y_test - y_pred) / y_test.replace(0, np.nan))) * 100
    mean_y, max_y, min_y = y_test.mean(), y_test.max(), y_test.min()
    nrmse_mean = rmse / mean_y
    nrmse_range = rmse / (max_y - min_y)

    if nrmse_mean < 0.1:
        level = "✅ 매우 우수"
    elif nrmse_mean < 0.2:
        level = "👍 양호"
    elif nrmse_mean < 0.3:
        level = "⚖️ 보통"
    else:
        level = "⚠️ 부정확"

    print(f"{gen_name} ▶ R²={r2:.3f}, RMSE={rmse:.2f}, MAPE={mape:.1f}%, {level}")

    results.append({
        "발전기명": gen_name,
        "데이터 수": len(group),
        "R²": round(r2, 4),
        "RMSE": round(rmse, 4),
        "NRMSE(평균)": round(nrmse_mean, 3),
        "NRMSE(범위)": round(nrmse_range, 3),
        "MAPE(%)": round(mape, 2),
        "정확도 수준": level
    })


    # ----------------------------------------------------------
    # 4️⃣ 시각화 저장
    # ----------------------------------------------------------

    ## (1) 실제 vs 예측 산점도
    plt.figure(figsize=(6, 6))
    plt.scatter(y_test, y_pred, alpha=0.7, color='royalblue')
    plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'r--', lw=2)
    plt.title(f"[{gen_name}] 실제 vs 예측 발전량")
    plt.xlabel("실제 발전량(MWh)")
    plt.ylabel("예측 발전량(MWh)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, f"{gen_name}_산점도.png"), dpi=300)
    plt.close()

    ## (2) 피처 중요도
    importances = model.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    plt.figure(figsize=(7, 4))
    plt.bar(X.columns[sorted_idx], importances[sorted_idx], color='seagreen')
    plt.title(f"[{gen_name}] 특성 중요도")
    plt.ylabel("중요도")
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, f"{gen_name}_특성중요도.png"), dpi=300)
    plt.close()

    ## (3) 잔차 분석
    residuals = y_test - y_pred
    plt.figure(figsize=(7, 4))
    plt.hist(residuals, bins=25, color='gray', alpha=0.8)
    plt.title(f"[{gen_name}] 잔차 분포")
    plt.xlabel("잔차(실제 - 예측)")
    plt.ylabel("빈도")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, f"{gen_name}_잔차분포.png"), dpi=300)
    plt.close()


# ----------------------------------------------------------
# 5️⃣ 전체 결과 저장 및 통합 시각화
# ----------------------------------------------------------
results_df = pd.DataFrame(results)
results_df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')

plt.figure(figsize=(10, 6))
plt.bar(results_df["발전기명"], results_df["R²"], color="teal", alpha=0.8)
plt.title("발전기별 모델 R² 비교")
plt.ylabel("R² (결정계수)")
plt.xticks(rotation=45)
plt.grid(axis="y")
plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "전체_R2비교.png"), dpi=300)
plt.close()

plt.figure(figsize=(10, 6))
plt.bar(results_df["발전기명"], results_df["MAPE(%)"], color="coral", alpha=0.8)
plt.title("발전기별 MAPE(%) 비교")
plt.ylabel("MAPE(%)")
plt.xticks(rotation=45)
plt.grid(axis="y")
plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "전체_MAPE비교.png"), dpi=300)
plt.close()

print(f"\n📊 결과 요약 저장 완료: {OUTPUT_CSV}")
print(f"🖼️ 그래프 저장 경로: {PLOT_DIR}")
print(f"💾 개별 모델 저장 경로: {MODEL_DIR}") 
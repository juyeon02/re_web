import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GridSearchCV, train_test_split
import os, json
from datetime import datetime
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

RESULT_DIR = os.path.join(BASE_DIR, "src/models/individual/random_forest/results/hyperparameter_tuning")
DETAIL_DIR = os.path.join(RESULT_DIR, "details")
PLOT_DIR = os.path.join(BASE_DIR, "src/models/individual/random_forest/plots/hyperparameter_tuning")
LOG_DIR = os.path.join(BASE_DIR, "src/models/individual/random_forest/logs/hyperparameter_tuning")
MODEL_DIR = os.path.join(BASE_DIR, "outputs/models/individual/random_forest/hyperparameter_tuning")

os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(DETAIL_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

SUMMARY_JSON = os.path.join(RESULT_DIR, "RF_hyperparam_summary.json")
SUMMARY_CSV = os.path.join(RESULT_DIR, "RF_hyperparam_summary.csv")

# ----------------------------------------------------------
# 1️⃣ 데이터 로드
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

features = [
    '설비용량(MW)', '평균기온', '평균습도', '총강수량', '총적설량',
    '평균풍속', '일조시간', '일사량', '평균운량'
]

param_grid = {
    'n_estimators': [100, 300, 500],
    'max_depth': [None, 10, 20],
    'min_samples_split': [2, 5, 10],
    'min_samples_leaf': [1, 2, 4],
    'max_features': ['sqrt', 'log2']
}


# ----------------------------------------------------------
# 2️⃣ 발전기별 하이퍼파라미터 튜닝 및 모델 저장
# ----------------------------------------------------------
summary_results = {}
summary_rows = []

for gen_name, group in df.groupby('발전기명'):
    if len(group) < 10:
        print(f"⚠️ {gen_name}: 데이터 부족 → 스킵")
        continue

    print(f"\n[{gen_name}] 하이퍼파라미터 튜닝 시작 ({len(group)}건)")
    log_path = os.path.join(LOG_DIR, f"{gen_name}_tuning_log.txt")

    X = group[features].dropna()
    y = group.loc[X.index, '발전량(MWh)']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # ----------------------------------------------------------
    # GridSearchCV 실행
    # ----------------------------------------------------------
    model = RandomForestRegressor(random_state=42)
    grid = GridSearchCV(
        estimator=model,
        param_grid=param_grid,
        scoring='r2',
        cv=3,
        n_jobs=-1,
        verbose=0
    )

    grid.fit(X_train, y_train)
    best_params = grid.best_params_
    best_score = grid.best_score_

    # ----------------------------------------------------------
    # 최적 모델로 재학습 및 저장
    # ----------------------------------------------------------
    best_model = RandomForestRegressor(**best_params, random_state=42)
    best_model.fit(X_train, y_train)

    from src.utils.model_utils import save_model
    save_model(best_model, model_name=f"rf_full_{gen_name.replace('/', '_')}_best", output_dir=MODEL_DIR)

    # ----------------------------------------------------------
    # 상세 결과 CSV 저장
    # ----------------------------------------------------------
    result_df = pd.DataFrame(grid.cv_results_)
    detail_csv = os.path.join(DETAIL_DIR, f"{gen_name}_tuning_results.csv")
    result_df.to_csv(detail_csv, index=False, encoding='utf-8-sig')

    # ----------------------------------------------------------
    # 로그 파일 저장
    # ----------------------------------------------------------
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"[{gen_name}] 하이퍼파라미터 튜닝 로그 ({datetime.now()})\n\n")
        f.write(f"최적 파라미터:\n{json.dumps(best_params, ensure_ascii=False, indent=4)}\n\n")
        f.write(f"평균 R² (CV): {round(best_score, 4)}\n\n")
        f.write(f"테스트 R²: {round(best_model.score(X_test, y_test), 4)}\n\n")
        f.write("전체 파라미터 조합:\n")
        f.write(result_df[['params', 'mean_test_score']].to_string())

    # ----------------------------------------------------------
    # 시각화: 주요 파라미터별 R² 변화
    # ----------------------------------------------------------
    # (1) n_estimators vs R²
    plt.figure(figsize=(7, 5))
    n_est_df = result_df.groupby("param_n_estimators")["mean_test_score"].mean().reset_index()
    plt.plot(n_est_df["param_n_estimators"], n_est_df["mean_test_score"], marker='o', color='teal')
    plt.title(f"[{gen_name}] n_estimators vs 평균 R²")
    plt.xlabel("n_estimators")
    plt.ylabel("평균 R²")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, f"{gen_name}_n_estimators_R2.png"), dpi=300)
    plt.close()

    # (2) max_depth vs R²
    plt.figure(figsize=(7, 5))
    depth_df = result_df.groupby("param_max_depth")["mean_test_score"].mean().reset_index()
    plt.plot(depth_df["param_max_depth"].astype(str), depth_df["mean_test_score"], marker='o', color='darkorange')
    plt.title(f"[{gen_name}] max_depth vs 평균 R²")
    plt.xlabel("max_depth")
    plt.ylabel("평균 R²")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, f"{gen_name}_max_depth_R2.png"), dpi=300)
    plt.close()

    # ----------------------------------------------------------
    # 결과 누적
    # ----------------------------------------------------------
    summary_results[gen_name] = {
        "데이터수": len(X),
        "best_params": best_params,
        "cv_mean_R²": round(best_score, 4),
        "test_R²": round(best_model.score(X_test, y_test), 4),
        "csv": detail_csv,
        "log": log_path
    }
    summary_rows.append({
        "발전기명": gen_name,
        "데이터수": len(X),
        "CV 평균 R²": round(best_score, 4),
        "테스트 R²": round(best_model.score(X_test, y_test), 4),
        **best_params
    })

    print(f"✅ {gen_name} 완료 | CV R²={best_score:.4f}, TEST R²={best_model.score(X_test, y_test):.4f}")

# ----------------------------------------------------------
# 3️⃣ 전체 요약 저장
# ----------------------------------------------------------
with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
    json.dump(summary_results, f, ensure_ascii=False, indent=4)

summary_df = pd.DataFrame(summary_rows)
summary_df.to_csv(SUMMARY_CSV, index=False, encoding="utf-8-sig")

# ----------------------------------------------------------
# 4️⃣ 전체 요약 시각화
# ----------------------------------------------------------
# (1) 발전기별 CV 평균 R²
plt.figure(figsize=(10, 6))
plt.bar(summary_df["발전기명"], summary_df["CV 평균 R²"], color="seagreen")
plt.title("발전기별 교차검증 평균 R² 비교")
plt.xticks(rotation=45)
plt.ylabel("CV 평균 R²")
plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "전체_CV_R2비교.png"), dpi=300)
plt.close()

# (2) 발전기별 TEST R²
plt.figure(figsize=(10, 6))
plt.bar(summary_df["발전기명"], summary_df["테스트 R²"], color="slateblue")
plt.title("발전기별 테스트 R² 비교")
plt.xticks(rotation=45)
plt.ylabel("테스트 R²")
plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "전체_TEST_R2비교.png"), dpi=300)
plt.close()

print("\n✅ 모든 발전기 하이퍼파라미터 튜닝 + 모델 저장 완료!")
print(f"📄 요약 JSON: {SUMMARY_JSON}")
print(f"📊 요약 CSV: {SUMMARY_CSV}")
print(f"🖼️ 그래프 폴더: {PLOT_DIR}")
print(f"🧾 로그 폴더: {LOG_DIR}")
print(f"💾 모델 폴더: {MODEL_DIR}")
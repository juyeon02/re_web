"""
🌞 랜덤포레스트 성능 비교 + 전체 발전기에 동일 모델 유형 선정
─────────────────────────────────────────────
① 발전기별 Base / BE / Tuned 모델 학습 및 평가
② 결과(CSV/PNG) 저장
③ 전체 발전기의 평균 R²을 비교해 가장 우수한 모델 유형 선택
④ 선택된 모델 유형 정보를 CSV로 저장
"""

import os
import json
import math
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split, GridSearchCV, KFold
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from sklearn.inspection import permutation_importance

# ✅ macOS 한글 폰트 설정
plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False
warnings.filterwarnings("ignore", category=UserWarning)

# --------------------------------------------------
# 경로 설정
# --------------------------------------------------
BASE_DIR = "/Users/parkhyeji/Desktop/PV"
DATA_PATH = os.path.join(BASE_DIR, "data/outliers_removed/이상치제거_데이터.csv")

RESULT_ROOT = os.path.join(BASE_DIR, "src/models/individual/analysis/results")
SUMMARY_DIR = os.path.join(RESULT_ROOT, "comparison")

os.makedirs(RESULT_ROOT, exist_ok=True)
os.makedirs(SUMMARY_DIR, exist_ok=True)

RANDOM_STATE = 42
TEST_SIZE = 0.2

# --------------------------------------------------
# 사용할 변수 (9개 고정)
# --------------------------------------------------
FEATURE_COLS = [
    '설비용량(MW)',
    '평균기온',
    '평균습도',
    '총강수량',
    '총적설량',
    '평균풍속',
    '일조시간',
    '일사량',
    '평균운량'
]

# --------------------------------------------------
# 유틸 함수
# --------------------------------------------------
def metric_dict(y_true, y_pred):
    rmse = math.sqrt(mean_squared_error(y_true, y_pred))
    mean_y = np.mean(y_true)
    return {
        "R2": r2_score(y_true, y_pred),
        "RMSE": rmse,
        "MAE": mean_absolute_error(y_true, y_pred),
        "MAPE(%)": np.mean(np.abs((y_true - y_pred) / y_true.replace(0, np.nan))) * 100,
        "NRMSE(mean)": rmse / mean_y if mean_y != 0 else np.nan
    }

def plot_actual_vs_pred(y_true, y_pred, title, path_png):
    plt.figure(figsize=(5,5))
    plt.scatter(y_true, y_pred, s=18, alpha=0.7)
    lims = [min(np.min(y_true), np.min(y_pred)), max(np.max(y_true), np.max(y_pred))]
    plt.plot(lims, lims, color='red', lw=1)
    plt.xlabel("실제 발전량(MWh)")
    plt.ylabel("예측 발전량(MWh)")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(path_png, dpi=150)
    plt.close()

# --------------------------------------------------
# 데이터 로드
# --------------------------------------------------
print("📁 데이터 로드 중...")
df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
df.columns = df.columns.str.strip()
df = df[df['발전량(MWh)'] != 0].copy()
print(f"✅ 데이터 로드 완료 ({len(df)}행)")

rows_summary = []

# --------------------------------------------------
# 발전기별 학습 시작
# --------------------------------------------------
for gen_name, group in df.groupby('발전기명'):
    if len(group) < 16:
        print(f"⏭️ {gen_name}: 데이터 {len(group)}행 (스킵)")
        continue

    print(f"\n==============================")
    print(f"🔆 발전기: {gen_name} (n={len(group)})")
    print(f"==============================")

    available_cols = [c for c in FEATURE_COLS if c in group.columns]
    if len(available_cols) == 0:
        print(f"⚠️ {gen_name}: 사용 가능한 컬럼이 없습니다. 스킵")
        continue

    X = group[available_cols].fillna(0)
    y = group['발전량(MWh)']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE
    )

    # 1️⃣ Base 모델
    base_rf = RandomForestRegressor(n_estimators=500, random_state=RANDOM_STATE, n_jobs=-1)
    base_rf.fit(X_train, y_train)
    base_pred = base_rf.predict(X_test)
    base_m = metric_dict(y_test, base_pred)
    print(f"✅ Base 완료 | R²={base_m['R2']:.3f}, RMSE={base_m['RMSE']:.3f}")

    # 2️⃣ BE (후진제거)
    be_feats = available_cols.copy()
    best_rmse = base_m["RMSE"]
    best_model = base_rf
    step = 0
    improved = True
    while improved and len(be_feats) > 2:
        improved = False
        perm = permutation_importance(best_model, X_test[be_feats], y_test, n_repeats=5, random_state=RANDOM_STATE)
        worst = be_feats[np.argmin(perm.importances_mean)]
        trial_feats = [f for f in be_feats if f != worst]
        temp_model = RandomForestRegressor(n_estimators=500, random_state=RANDOM_STATE, n_jobs=-1)
        temp_model.fit(X_train[trial_feats], y_train)
        pred = temp_model.predict(X_test[trial_feats])
        rmse = math.sqrt(mean_squared_error(y_test, pred))
        step += 1
        if rmse < best_rmse:
            improved = True
            best_rmse = rmse
            best_model = temp_model
            be_feats = trial_feats.copy()
    be_pred = best_model.predict(X_test[be_feats])
    be_m = metric_dict(y_test, be_pred)
    print(f"🧹 BE 완료 | 특성수={len(be_feats)}, RMSE={be_m['RMSE']:.3f}")

    # 3️⃣ Tuning (GridSearch)
    param_grid = {
        "n_estimators": [300, 600],
        "max_depth": [None, 10, 20],
        "min_samples_split": [2, 5],
        "min_samples_leaf": [1, 2],
        "max_features": [None, "sqrt", "log2"]  # ✅ 'auto' 제거
    }
    cv = KFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE)
    gs = GridSearchCV(
        RandomForestRegressor(random_state=RANDOM_STATE, n_jobs=-1),
        param_grid=param_grid,
        cv=cv, scoring="neg_root_mean_squared_error", n_jobs=-1
    )
    gs.fit(X_train, y_train)
    tuned = gs.best_estimator_
    tuned_pred = tuned.predict(X_test)
    tune_m = metric_dict(y_test, tuned_pred)
    print(f"🎯 Tuning 완료 | R²={tune_m['R2']:.3f}, RMSE={tune_m['RMSE']:.3f}")

    # 결과 저장
    rows_summary.append({
        "발전기명": gen_name,
        "Base_R2": base_m["R2"], "Base_RMSE": base_m["RMSE"],
        "BE_R2": be_m["R2"], "BE_RMSE": be_m["RMSE"],
        "Tuned_R2": tune_m["R2"], "Tuned_RMSE": tune_m["RMSE"],
        "BE_최종특성수": len(be_feats),
        "BE_최종특성리스트": "; ".join(be_feats)
    })

# --------------------------------------------------
# 전체 요약 저장
# --------------------------------------------------
summary_df = pd.DataFrame(rows_summary).sort_values("Tuned_RMSE")
summary_path = os.path.join(SUMMARY_DIR, "RF_compare_summary_by_generator.csv")
summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
print(f"\n📊 요약 저장 완료 → {summary_path}")

# --------------------------------------------------
# 🌍 전체 발전기 평균 R² 비교
# --------------------------------------------------
avg_base = summary_df['Base_R2'].mean()
avg_be = summary_df['BE_R2'].mean()
avg_tuned = summary_df['Tuned_R2'].mean()

best_type, best_r2 = max(
    [('Base', avg_base), ('BE', avg_be), ('Tuned', avg_tuned)],
    key=lambda x: x[1]
)

print("\n📈 모델 유형별 평균 R²:")
print(f"Base  : {avg_base:.4f}")
print(f"BE    : {avg_be:.4f}")
print(f"Tuned : {avg_tuned:.4f}")
print(f"\n🏆 전체적으로 가장 우수한 모델 유형: {best_type} (평균 R²={best_r2:.4f})")

# --------------------------------------------------
# 결과 저장
# --------------------------------------------------
global_result_path = os.path.join(SUMMARY_DIR, "RF_global_best_model.csv")
pd.DataFrame({
    "모델유형": ["Base", "BE", "Tuned"],
    "평균_R2": [avg_base, avg_be, avg_tuned],
    "선택모델": ["✅" if m == best_type else "" for m in ["Base", "BE", "Tuned"]]
}).to_csv(global_result_path, index=False, encoding='utf-8-sig')

print(f"\n💾 전체 평균 비교 결과 저장 완료 → {global_result_path}")
print(f"✅ 모든 발전기에 '{best_type}' 모델 유형을 공통 적용하면 됩니다.")

# --------------------------------------------------
# 선택된 모델 유형 저장 (추가 부분)
# --------------------------------------------------
MODEL_INFO_DIR = os.path.join(BASE_DIR, "outputs/models/analysis")
os.makedirs(MODEL_INFO_DIR, exist_ok=True)

best_model_info = {
    "selected_model_type": best_type,
    "average_R2": best_r2,
    "average_scores": {
        "Base": avg_base,
        "BE": avg_be,
        "Tuned": avg_tuned
    }
}

best_model_info_path = os.path.join(MODEL_INFO_DIR, "best_RF_model_type.json")
with open(best_model_info_path, "w", encoding="utf-8") as f:
    json.dump(best_model_info, f, ensure_ascii=False, indent=2)

print(f"🧾 선택된 모델 유형 정보 저장 완료 → {best_model_info_path}")
print("🏁 전체 프로세스 완료")

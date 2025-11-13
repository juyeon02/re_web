import os
import numpy as np
import pandas as pd
from sklearn.ensemble import StackingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from src.utils.model_utils import save_model
import matplotlib.pyplot as plt

# macOS 한글 폰트
plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False


# -----------------------------------------------------------
# 🔧 경로 설정
# -----------------------------------------------------------
BASE_DIR = "/Users/parkhyeji/Desktop/PV"

DATA_PATH = os.path.join(BASE_DIR, "data/outliers_removed/이상치제거_데이터.csv")
RESULT_BASE = os.path.join(BASE_DIR, "src/models/ensemble/results/stacking")
MODEL_BASE = os.path.join(BASE_DIR, "outputs/models/ensemble/stacking")

os.makedirs(RESULT_BASE, exist_ok=True)
os.makedirs(MODEL_BASE, exist_ok=True)

# -----------------------------------------------------------
# 🔹 데이터 로드
# -----------------------------------------------------------
df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
print(f"📁 전체 데이터 로드 완료: {df.shape}")


# -----------------------------------------------------------
# 📌 평가 지표 함수
# -----------------------------------------------------------
def evaluate(y_test, pred):
    return {
        "R2": r2_score(y_test, pred),
        "RMSE": np.sqrt(mean_squared_error(y_test, pred)),
        "MAE": mean_absolute_error(y_test, pred)
    }


FEATURE_COLS = [
    '설비용량(MW)', '평균기온', '평균습도', '총강수량', '총적설량',
    '평균풍속', '일조시간', '일사량', '평균운량'
]


# -----------------------------------------------------------
# 📌 발전기별 Stacking Ensemble 학습 함수
# -----------------------------------------------------------
def train_stacking(df_sub, gen_name):

    print(f"🚀 학습 시작 — {gen_name} (행: {len(df_sub)})")

    RESULT_DIR = os.path.join(RESULT_BASE, gen_name)
    MODEL_DIR = os.path.join(MODEL_BASE, gen_name)

    os.makedirs(RESULT_DIR, exist_ok=True)
    os.makedirs(MODEL_DIR, exist_ok=True)

    # -----------------------
    # 1) 데이터 분리
    # -----------------------
    X = df_sub[FEATURE_COLS]
    y = df_sub['발전량(MWh)']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # -----------------------
    # 2) Base models
    # -----------------------
    estimators = [
        ('rf', RandomForestRegressor(n_estimators=300, random_state=42)),
        ('xgb', XGBRegressor(
            n_estimators=300, learning_rate=0.07,
            max_depth=5, subsample=0.8, colsample_bytree=0.8,
            random_state=42
        )),
    ]

    meta_model = LinearRegression()

    stacking = StackingRegressor(
        estimators=estimators,
        final_estimator=meta_model,
        passthrough=True
    )

    # -----------------------
    # 3) 학습
    # -----------------------
    stacking.fit(X_train, y_train)
    pred = stacking.predict(X_test)

    metrics = evaluate(y_test, pred)

    # -------------------------------
    # 4) 모델 저장
    # -------------------------------
    save_model(
        stacking,
        model_name=f"StackingEnsemble_{gen_name}",
        output_dir=MODEL_DIR
    )

    # ============================================================
    # 📌 [A] 성능 지표 저장
    # ============================================================
    pd.DataFrame([metrics]).to_csv(
        os.path.join(RESULT_DIR, "metrics.csv"),
        index=False, encoding="utf-8-sig"
    )

    # ============================================================
    # 📌 [B] 예측 결과 저장
    # ============================================================
    pred_df = pd.DataFrame({
        "y_test": y_test.values,
        "prediction": pred,
        "error": y_test.values - pred,
        "abs_error": np.abs(y_test.values - pred)
    })
    pred_df.to_csv(
        os.path.join(RESULT_DIR, "prediction_results.csv"),
        index=False, encoding="utf-8-sig"
    )

    # ============================================================
    # 📌 [C] Feature Importance (XGB 기반)
    # ============================================================
    xgb_model = estimators[1][1]
    xgb_model.fit(X_train, y_train)
    importance_df = pd.DataFrame({
        "feature": FEATURE_COLS,
        "importance": xgb_model.feature_importances_
    }).sort_values(by="importance", ascending=False)

    importance_df.to_csv(
        os.path.join(RESULT_DIR, "feature_importance.csv"),
        index=False, encoding="utf-8-sig"
    )

    # ============================================================
    # 📌 [D] 시각화 저장
    # ============================================================

    # 1) 산점도
    plt.figure(figsize=(7, 7))
    plt.scatter(y_test, pred, alpha=0.6)
    plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'r--')
    plt.xlabel("실제 발전량(MWh)")
    plt.ylabel("예측 발전량(MWh)")
    plt.title(f"{gen_name} - Stacking Ensemble 실제 vs 예측")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULT_DIR, "scatter_plot.png"))
    plt.close()

    # 2) 오차 시계열
    plt.figure(figsize=(10, 4))
    plt.plot(pred_df["error"])
    plt.xlabel("Index")
    plt.ylabel("Error")
    plt.title(f"{gen_name} - 예측 오차(Time Series)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULT_DIR, "error_plot.png"))
    plt.close()

    print(f"✅ 완료 — {gen_name}")
    return metrics


# -----------------------------------------------------------
# 🔥 실행 구간: 발전기별 Stacking Ensemble 수행
# -----------------------------------------------------------
if __name__ == "__main__":

    metrics_all = []

    for gen_name, group in df.groupby("발전기명"):

        if len(group) < 20:
            print(f"⚠️ {gen_name}: 데이터 부족({len(group)}행) → 스킵")
            continue

        metrics = train_stacking(group, gen_name)
        metrics["발전기명"] = gen_name
        metrics_all.append(metrics)

    # 📌 전체 발전기 비교표 저장
    summary_df = pd.DataFrame(metrics_all)
    summary_df.to_csv(
        os.path.join(RESULT_BASE, "metrics_all_generators.csv"),
        index=False, encoding="utf-8-sig"
    )

    print("🎉 모든 발전기 Stacking Ensemble 학습 완료!")

# src/models/ensemble/blending.py

import os
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from sklearn.model_selection import train_test_split
import matplotlib.pyplot as plt
from src.utils.model_utils import save_model

# macOS 한글 폰트 설정
plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False


# -----------------------------------------------------------
# 🔧 경로 설정
# -----------------------------------------------------------
BASE_DIR = "/Users/parkhyeji/Desktop/PV"

DATA_PATH = os.path.join(BASE_DIR, "data/outliers_removed/이상치제거_데이터.csv")
RESULT_BASE = os.path.join(BASE_DIR, "src/models/ensemble/results/blending")
MODEL_BASE = os.path.join(BASE_DIR, "outputs/models/ensemble/blending")

os.makedirs(RESULT_BASE, exist_ok=True)
os.makedirs(MODEL_BASE, exist_ok=True)

df = pd.read_csv(DATA_PATH, encoding='utf-8-sig')
print(f"📁 전체 데이터 로드 완료: {df.shape}")


# -----------------------------------------------------------
# 📌 지표 계산 함수
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
# 📌 발전기별 Blending Ensemble 학습 함수
# -----------------------------------------------------------
def train_blending(df_sub, gen_name):

    print(f"\n🚀 Blending 학습 시작: {gen_name} (행: {len(df_sub)})")

    RESULT_DIR = os.path.join(RESULT_BASE, gen_name)
    MODEL_DIR = os.path.join(MODEL_BASE, gen_name)

    os.makedirs(RESULT_DIR, exist_ok=True)
    os.makedirs(MODEL_DIR, exist_ok=True)

    X = df_sub[FEATURE_COLS]
    y = df_sub['발전량(MWh)']

    # -----------------------
    # 1) blending = train 70% / blend 30%
    # -----------------------
    X_train, X_blend, y_train, y_blend = train_test_split(
        X, y, test_size=0.3, random_state=42
    )

    # -----------------------
    # 2) Base models
    # -----------------------
    rf = RandomForestRegressor(n_estimators=300, random_state=42)
    xgb = XGBRegressor(
        n_estimators=300, learning_rate=0.08,
        max_depth=5, subsample=0.8, colsample_bytree=0.8,
        random_state=42
    )
    lr = LinearRegression()

    models = [rf, xgb, lr]

    # Base 모델 학습
    for m in models:
        m.fit(X_train, y_train)

    # -----------------------
    # 3) Blend용 training set 생성
    # -----------------------
    blend_train = np.column_stack([m.predict(X_blend) for m in models])

    meta_model = LinearRegression()
    meta_model.fit(blend_train, y_blend)

    pred = meta_model.predict(blend_train)
    metrics = evaluate(y_blend, pred)

    # -----------------------
    # 4) 모델 저장
    # -----------------------
    blend_dict = {
        "models": models,
        "meta_model": meta_model
    }

    save_model(
        blend_dict,
        model_name=f"BlendingEnsemble_{gen_name}",
        output_dir=MODEL_DIR
    )

    # ============================================================
    # 📌 [A] 성능 저장
    # ============================================================
    pd.DataFrame([metrics]).to_csv(
        os.path.join(RESULT_DIR, "metrics.csv"),
        index=False, encoding='utf-8-sig'
    )

    # ============================================================
    # 📌 [B] 예측 결과 저장
    # ============================================================
    pred_df = pd.DataFrame({
        "y_blend": y_blend.values,
        "prediction": pred,
        "error": y_blend.values - pred,
        "abs_error": np.abs(y_blend.values - pred)
    })
    pred_df.to_csv(
        os.path.join(RESULT_DIR, "prediction_results.csv"),
        index=False, encoding='utf-8-sig'
    )

    # ============================================================
    # 📌 [C] Feature Importance (XGB 기반)
    # ============================================================
    xgb_model = xgb
    fi_df = pd.DataFrame({
        "feature": FEATURE_COLS,
        "importance": xgb_model.feature_importances_
    }).sort_values(by="importance", ascending=False)

    fi_df.to_csv(
        os.path.join(RESULT_DIR, "feature_importance.csv"),
        index=False, encoding='utf-8-sig'
    )

    # ============================================================
    # 📌 [D] 그래프 저장
    # ============================================================

    # 1) 실제값 vs 예측값
    plt.figure(figsize=(7, 7))
    plt.scatter(y_blend, pred, alpha=0.6)
    plt.plot([y_blend.min(), y_blend.max()], [y_blend.min(), y_blend.max()], 'r--')
    plt.xlabel("실제 발전량(MWh)")
    plt.ylabel("예측 발전량(MWh)")
    plt.title(f"{gen_name} - Blending Ensemble 실제 vs 예측")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULT_DIR, "scatter_plot.png"))
    plt.close()

    # 2) 오차 시계열
    plt.figure(figsize=(10, 4))
    plt.plot(pred_df["error"])
    plt.title(f"{gen_name} - Blending 예측 오차(Time Series)")
    plt.xlabel("Index")
    plt.ylabel("Error")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULT_DIR, "error_plot.png"))
    plt.close()

    print(f"✅ 완료: {gen_name}")
    return metrics


# -----------------------------------------------------------
# 🔥 발전기별 Blending 실행
# -----------------------------------------------------------
if __name__ == "__main__":

    metrics_all = []

    for gen_name, group in df.groupby("발전기명"):

        if len(group) < 20:
            print(f"⚠️ {gen_name}: 데이터 부족({len(group)}행) → 스킵")
            continue

        metrics = train_blending(group, gen_name)
        metrics["발전기명"] = gen_name
        metrics_all.append(metrics)

    # 📌 전체 발전기 비교표 저장
    summary_df = pd.DataFrame(metrics_all)
    summary_df.to_csv(
        os.path.join(RESULT_BASE, "metrics_all_generators.csv"),
        index=False, encoding='utf-8-sig'
    )

    print("\n🎉 모든 발전기 Blending Ensemble 학습 완료!")

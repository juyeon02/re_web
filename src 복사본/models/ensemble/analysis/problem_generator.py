"""
🔧 문제 발전기 맞춤형 모델 재학습 파이프라인
- 예천태양광 / 고흥만수상태양광
- 이상치 제거 + 비선형 특징 자동 생성 + XGBoost/LGBM 비교
"""

import os
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split, RandomizedSearchCV
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

from xgboost import XGBRegressor
from lightgbm import LGBMRegressor

# ---------------------------------------------------------
# 🔧 경로 설정
# ---------------------------------------------------------
BASE_DIR = "/Users/parkhyeji/Desktop/PV"
DATA_PATH = os.path.join(BASE_DIR, "data/outliers_removed/이상치제거_데이터.csv")
RESULT_DIR = os.path.join(BASE_DIR, "src/models/ensemble/analysis/problem_generators/results")
PLOT_DIR = os.path.join(BASE_DIR, "src/models/ensemble/analysis/problem_generators/plots")
MODEL_DIR = os.path.join(BASE_DIR, "src/models/ensemble/analysis/problem_generators/models")

os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

# ---------------------------------------------------------
# 📌 문제 발전기 리스트
# ---------------------------------------------------------
PROBLEM_GENS = ["예천태양광", "고흥만수상태양광"]

# ---------------------------------------------------------
# 📌 데이터 로드
# ---------------------------------------------------------
df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
df = df[df["발전량(MWh)"] != 0].copy()

# ---------------------------------------------------------
# 📌 비선형 특징 생성 함수
# ---------------------------------------------------------
def add_non_linear_features(df):
    df = df.copy()

    # 사인/코사인으로 계절성 반영
    df["month"] = pd.to_datetime(df["날짜"]).dt.month
    df["sin_month"] = np.sin(2 * np.pi * df["month"] / 12)
    df["cos_month"] = np.cos(2 * np.pi * df["month"] / 12)

    # 제곱항
    df["일사량2"] = df["일사량"] ** 2
    df["평균기온2"] = df["평균기온"] ** 2
    df["평균풍속2"] = df["평균풍속"] ** 2

    # 상호작용 변수
    df["기온x습도"] = df["평균기온"] * df["평균습도"]
    df["풍속x일사"] = df["평균풍속"] * df["일사량"]

    return df


# ---------------------------------------------------------
# 📌 이상치 제거 (IQR)
# ---------------------------------------------------------
def remove_outliers_iqr(df, col="발전량(MWh)"):
    Q1 = df[col].quantile(0.25)
    Q3 = df[col].quantile(0.75)
    IQR = Q3 - Q1

    lower = Q1 - 1.5 * IQR
    upper = Q3 + 1.5 * IQR

    return df[(df[col] >= lower) & (df[col] <= upper)]


# ---------------------------------------------------------
# 📌 모델 학습 함수
# ---------------------------------------------------------
def train_and_evaluate(gen_name, data):

    print(f"\n🚀 {gen_name} 모델 재학습 시작")

    # 데이터 준비
    features = [
        "설비용량(MW)", "평균기온", "평균습도", "총강수량", "총적설량",
        "평균풍속", "일조시간", "일사량", "평균운량",
        "sin_month", "cos_month",
        "일사량2", "평균기온2", "평균풍속2",
        "기온x습도", "풍속x일사"
    ]

    X = data[features]
    y = data["발전량(MWh)"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=True, random_state=42
    )

    # ---------------------------------------------------------
    # 🔥 후보 모델 1: XGBoost
    # ---------------------------------------------------------
    xgb = XGBRegressor(
        objective="reg:squarederror",
        n_estimators=300,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.9,
        colsample_bytree=0.9
    )

    # ---------------------------------------------------------
    # 🔥 후보 모델 2: LightGBM
    # ---------------------------------------------------------
    lgbm = LGBMRegressor(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=-1,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="regression"
    )

    # ---------------------------------------------------------
    # 📌 XGB / LGBM 각각 학습
    # ---------------------------------------------------------
    xgb.fit(X_train, y_train)
    lgbm.fit(X_train, y_train)

    # ---------------------------------------------------------
    # 📌 예측 및 평가
    # ---------------------------------------------------------
    def evaluate_model(name, model):
        pred = model.predict(X_test)
        return {
            "model": name,
            "R2": r2_score(y_test, pred),
            "RMSE": np.sqrt(mean_squared_error(y_test, pred)),
            "MAE": mean_absolute_error(y_test, pred),
            "pred": pred
        }

    xgb_res = evaluate_model("XGBoost", xgb)
    lgbm_res = evaluate_model("LightGBM", lgbm)

    # ---------------------------------------------------------
    # 📌 Best Model 선택
    # ---------------------------------------------------------
    best = xgb_res if xgb_res["R2"] > lgbm_res["R2"] else lgbm_res
    best_model = xgb if best["model"] == "XGBoost" else lgbm

    print(f"✅ {gen_name} BEST MODEL = {best['model']} (R2={best['R2']:.4f})")

    # ---------------------------------------------------------
    # 📌 예측 그래프 저장
    # ---------------------------------------------------------
    plt.figure(figsize=(14, 5))
    plt.plot(y_test.values, label="Actual", alpha=0.8)
    plt.plot(best["pred"], label=f"Predicted ({best['model']})")
    plt.title(f"{gen_name} — 실제 vs 예측")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, f"{gen_name}_prediction.png"))
    plt.close()

    # ---------------------------------------------------------
    # 📌 모델 저장
    # ---------------------------------------------------------
    import joblib
    joblib.dump(best_model, os.path.join(MODEL_DIR, f"{gen_name}_best.pkl"))

    return {
        "발전기명": gen_name,
        "best_model": best["model"],
        "R2": best["R2"],
        "RMSE": best["RMSE"],
        "MAE": best["MAE"]
    }


# ---------------------------------------------------------
# 📌 실행 파트
# ---------------------------------------------------------
result_list = []

for gen, group in df.groupby("발전기명"):
    if gen not in PROBLEM_GENS:
        continue

    print(f"\n==========================")
    print(f"📌 {gen} 처리 시작")
    print(f"==========================")

    # 1) 비선형 특징 생성
    g = add_non_linear_features(group)

    # 2) 이상치 제거
    g = remove_outliers_iqr(g)

    # 3) 모델 학습 및 평가
    res = train_and_evaluate(gen, g)
    result_list.append(res)

# ---------------------------------------------------------
# 📌 최종 성능 CSV 저장
# ---------------------------------------------------------
result_df = pd.DataFrame(result_list)
result_df.to_csv(os.path.join(RESULT_DIR, "problem_generators_model_performance.csv"),
                 encoding="utf-8-sig", index=False)

print("\n🎉 모든 문제 발전기 맞춤 모델 재학습 완료!")

"""
🔁 XGBoost 후진제거법 (Backward Elimination)
────────────────────────────────────
① XGBoost + 반복적 변수 제거
② 중요하지 않은 피처 제거
③ 성능평가 결과 + 최종 변수목록 + 모델 저장
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
import seaborn as sns
from src.utils.model_utils import save_model

plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False

# --------------------------------------------------
BASE_DIR = "/Users/parkhyeji/Desktop/PV"
DATA_PATH = os.path.join(BASE_DIR, "data/outliers_removed/이상치제거_데이터.csv")

RESULT_DIR = os.path.join(BASE_DIR, "src/models/individual/xgboost/results/backward_elimination")
PLOT_DIR = os.path.join(BASE_DIR, "src/models/individual/xgboost/plots/backward_elimination")
MODEL_DIR = os.path.join(BASE_DIR, "outputs/models/individual/XGB/backward_elimination")

os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

# --------------------------------------------------
df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
df = df[df["발전량(MWh)"] != 0].copy()

results = []
for gen_name, group in df.groupby("발전기명"):
    if len(group) < 30:
        continue

    print(f"\n🔹 {gen_name} - 후진제거법 적용 중...")

    X = group[['설비용량(MW)', '평균기온', '평균습도', '총강수량', '총적설량',
               '평균풍속', '일조시간', '일사량', '평균운량']]
    y = group['발전량(MWh)']

    # 초기 모델
    model = XGBRegressor(n_estimators=300, learning_rate=0.05, random_state=42)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model.fit(X_train, y_train)

    # 변수 중요도 기준으로 반복 제거
    min_features = 3
    while len(X_train.columns) > min_features:
        fi = pd.Series(model.feature_importances_, index=X_train.columns)
        least_important = fi.idxmin()
        if fi[least_important] < 0.01:  # 중요도 임계값
            print(f"⚠️ 제거: {least_important} (중요도 {fi[least_important]:.4f})")
            X_train = X_train.drop(columns=[least_important])
            X_test = X_test.drop(columns=[least_important])
            model.fit(X_train, y_train)
        else:
            break

    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)

    results.append({
        "발전기명": gen_name,
        "R2": r2,
        "RMSE": rmse,
        "MAE": mae,
        "최종변수": ", ".join(X_train.columns)
    })

    # 모델 저장
    model_name = f"{gen_name}_XGB_backward_elimination"
    save_model(model, model_name, output_dir=MODEL_DIR)

    # 실제 vs 예측 그래프
    plt.figure(figsize=(6,6))
    sns.scatterplot(x=y_test, y=y_pred, alpha=0.7)
    sns.lineplot(x=y_test, y=y_test, color='red')
    plt.title(f"📈 {gen_name} - 후진제거 결과 (XGBoost)")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, f"{gen_name}_후진제거_결과.png"))
    plt.close()

# 통합 저장
pd.DataFrame(results).to_csv(os.path.join(RESULT_DIR, "XGB_backward_elimination_결과.csv"),
                             index=False, encoding="utf-8-sig")
print("✅ 후진제거법 적용 완료!")

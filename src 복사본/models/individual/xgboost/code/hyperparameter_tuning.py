"""
🎯 XGBoost 하이퍼파라미터 튜닝 (발전기별)
────────────────────────────────────
① GridSearchCV 기반 파라미터 탐색
② 최고 성능 모델 저장
③ 성능평가 결과 + 최적 하이퍼파라미터 CSV 저장
"""

import os
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from src.utils.model_utils import save_model

BASE_DIR = "/Users/parkhyeji/Desktop/PV"
DATA_PATH = os.path.join(BASE_DIR, "data/outliers_removed/이상치제거_데이터.csv")

RESULT_DIR = os.path.join(BASE_DIR, "src/models/individual/xgboost/results/hyperparameter_tuning")
MODEL_DIR = os.path.join(BASE_DIR, "outputs/models/individual/XGB/hyperparameter_tuning")

os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
df = df[df["발전량(MWh)"] != 0].copy()

param_grid = {
    'n_estimators': [200, 400],
    'max_depth': [4, 6, 8],
    'learning_rate': [0.01, 0.05, 0.1],
    'subsample': [0.7, 0.9],
    'colsample_bytree': [0.7, 0.9]
}

results = []
for gen_name, group in df.groupby("발전기명"):
    if len(group) < 30:
        continue

    print(f"\n🔹 {gen_name} - 하이퍼파라미터 튜닝 중...")

    X = group[['설비용량(MW)', '평균기온', '평균습도', '총강수량', '총적설량',
               '평균풍속', '일조시간', '일사량', '평균운량']]
    y = group['발전량(MWh)']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    base_model = XGBRegressor(random_state=42, n_jobs=-1)
    grid = GridSearchCV(base_model, param_grid, cv=3, scoring='r2', verbose=0)
    grid.fit(X_train, y_train)

    best_model = grid.best_estimator_
    y_pred = best_model.predict(X_test)

    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)

    results.append({
        "발전기명": gen_name,
        "R2": r2,
        "RMSE": rmse,
        "MAE": mae,
        "Best Params": grid.best_params_
    })

    model_name = f"{gen_name}_XGB_tuned"
    save_model(best_model, model_name, output_dir=MODEL_DIR)

pd.DataFrame(results).to_csv(os.path.join(RESULT_DIR, "XGB_hyperparameter_tuning_결과.csv"),
                             index=False, encoding="utf-8-sig")
print("✅ 하이퍼파라미터 튜닝 완료!")

# ==============================================================
# ✅ Linear Regression vs Random Forest vs XGBoost 성능 비교 + 결과 저장
# ==============================================================

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
import os
import warnings
warnings.filterwarnings("ignore")

# --------------------------------------------------------------
# 1️⃣ 경로 설정
# --------------------------------------------------------------
BASE_DIR = "/Users/parkhyeji/Desktop/PV"
DATA_PATH = os.path.join(BASE_DIR, "data/outliers_removed/이상치제거_데이터.csv")
RESULT_DIR = os.path.join(BASE_DIR, "src/models/individual/analysis")

os.makedirs(RESULT_DIR, exist_ok=True)
RESULT_PATH = os.path.join(
    RESULT_DIR, "LRvsRFvsXGB_model_performance_comparison.csv")

# --------------------------------------------------------------
# 2️⃣ 데이터 불러오기
# --------------------------------------------------------------
df = pd.read_csv(DATA_PATH, encoding='utf-8-sig')

# 발전량 0 제거
df = df[df['발전량(MWh)'] != 0].copy()

# 독립변수(X), 종속변수(y)
X = df[['설비용량(MW)', '평균기온', '평균습도', '총강수량', '총적설량',
        '평균풍속', '일조시간', '일사량', '평균운량']]
y = df['발전량(MWh)']

# --------------------------------------------------------------
# 3️⃣ 학습/검증 데이터 분리
# --------------------------------------------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42)

# --------------------------------------------------------------
# 4️⃣ 모델별 학습 및 예측 함수 정의
# --------------------------------------------------------------


def evaluate_model(model, name):
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    return {'모델': name, 'R²': r2, 'RMSE': rmse, 'MAE': mae}


# --------------------------------------------------------------
# 5️⃣ 모델별 평가
# --------------------------------------------------------------
models = [
    (LinearRegression(), "Linear Regression"),
    (RandomForestRegressor(n_estimators=200,
     random_state=42, n_jobs=-1), "Random Forest"),
    (XGBRegressor(n_estimators=300, learning_rate=0.05,
     max_depth=6, random_state=42, n_jobs=-1), "XGBoost")
]

results = []
for model, name in models:
    print(f"🚀 {name} 학습 중...")
    result = evaluate_model(model, name)
    results.append(result)

# --------------------------------------------------------------
# 6️⃣ 결과 비교 DataFrame 생성
# --------------------------------------------------------------
results_df = pd.DataFrame(results)

# --------------------------------------------------------------
# 7️⃣ 우수 모델 선택 (R² 기준)
# --------------------------------------------------------------
best_row = results_df.loc[results_df['R²'].idxmax()]
best_model_name = best_row['모델']
best_r2 = best_row['R²']

# 우수모델 표시
results_df['우수모델'] = ['✅' if m ==
                      best_model_name else '' for m in results_df['모델']]

# --------------------------------------------------------------
# 8️⃣ 결과 저장
# --------------------------------------------------------------
results_df.to_csv(RESULT_PATH, index=False, encoding='utf-8-sig')

print("\n📊 모델 성능 비교 결과")
print(results_df)
print("-" * 60)
print(f"🏆 최종 선택된 우수 모델: {best_model_name} (R²={best_r2:.4f})")
print(f"📁 결과 저장 완료: {RESULT_PATH}")

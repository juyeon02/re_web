"""
🌟 XGBoost 변수 중요도 분석 (발전기별)
────────────────────────────────────
① 발전기별 XGBoost 학습
② 변수 중요도 계산 및 시각화
③ 성능평가 결과 + 중요도 CSV/PNG + 모델 저장
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

# macOS 한글 폰트 설정
plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False

# --------------------------------------------------
BASE_DIR = "/Users/parkhyeji/Desktop/PV"
DATA_PATH = os.path.join(BASE_DIR, "data/outliers_removed/이상치제거_데이터.csv")

RESULT_DIR = os.path.join(BASE_DIR, "src/models/individual/xgboost/results/feature_importance")
PLOT_DIR = os.path.join(BASE_DIR, "src/models/individual/xgboost/plots/feature_importance")
MODEL_DIR = os.path.join(BASE_DIR, "outputs/models/individual/XGB/feature_importance")

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

    print(f"\n🔹 {gen_name} - 변수 중요도 분석 중...")

    X = group[['설비용량(MW)', '평균기온', '평균습도', '총강수량', '총적설량',
               '평균풍속', '일조시간', '일사량', '평균운량']]
    y = group['발전량(MWh)']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = XGBRegressor(
        n_estimators=400, learning_rate=0.05, max_depth=6,
        subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    # 성능지표
    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)

    results.append({"발전기명": gen_name, "R2": r2, "RMSE": rmse, "MAE": mae})

    # 변수 중요도 저장 및 시각화
    fi = pd.DataFrame({
        "변수명": X.columns,
        "중요도": model.feature_importances_
    }).sort_values("중요도", ascending=False)

    fi.to_csv(os.path.join(RESULT_DIR, f"{gen_name}_feature_importance.csv"),
              index=False, encoding="utf-8-sig")

    plt.figure(figsize=(7,4))
    sns.barplot(x="중요도", y="변수명", data=fi, palette="viridis")
    plt.title(f"🌟 {gen_name} - 변수 중요도 (XGBoost)")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, f"{gen_name}_변수중요도.png"), bbox_inches="tight")
    plt.close()

    # 모델 저장
    model_name = f"{gen_name}_XGB_feature_importance"
    save_model(model, model_name, output_dir=MODEL_DIR)

# 통합 결과 저장
pd.DataFrame(results).to_csv(os.path.join(RESULT_DIR, "XGB_feature_importance_결과.csv"),
                             index=False, encoding="utf-8-sig")
print("✅ 변수 중요도 분석 완료!")

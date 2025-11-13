import pandas as pd
import numpy as np
import os
from sklearn.linear_model import RidgeCV, LassoCV, ElasticNetCV
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import KFold
from src.utils.model_utils import save_model

BASE_DIR = "/Users/parkhyeji/Desktop/PV"
DATA_PATH = os.path.join(BASE_DIR, "data/outliers_removed/이상치제거_데이터.csv")

RESULT_DIR = os.path.join(BASE_DIR, "src/models/individual/linear_regression/results/hyperparameter_tuning")
MODEL_DIR = os.path.join(BASE_DIR, "outputs/models/individual/linear_regression/hyperparameter_tuning")

os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

df = pd.read_csv(DATA_PATH, encoding='utf-8-sig')
df = df[df['발전량(MWh)'] != 0].copy()

for gen_name, group in df.groupby('발전기명'):
    if len(group) < 10:
        continue
    X = group[['설비용량(MW)', '평균기온', '평균습도', '총강수량', '총적설량',
               '평균풍속', '일조시간', '일사량', '평균운량']]
    y = group['발전량(MWh)']
    X = X.dropna(); y = y.loc[X.index]

    X_scaled = StandardScaler().fit_transform(X)
    cv = KFold(n_splits=5, shuffle=True, random_state=42)

    ridge = RidgeCV(alphas=np.logspace(-3, 3, 50), cv=cv).fit(X_scaled, y)
    lasso = LassoCV(alphas=np.logspace(-3, 3, 50), cv=cv, max_iter=5000).fit(X_scaled, y)
    elastic = ElasticNetCV(alphas=np.logspace(-3, 3, 50), l1_ratio=[.1, .3, .5, .7, .9],
                           cv=cv, max_iter=5000).fit(X_scaled, y)
    
    # ----------------------------------------------------------
    # ✅ 모델 저장 (각 모델별)
    # ----------------------------------------------------------
    save_model(ridge, f"LR_{gen_name.replace('/', '_')}_Ridge_tuned", output_dir=MODEL_DIR)
    save_model(lasso, f"LR_{gen_name.replace('/', '_')}_Lasso_tuned", output_dir=MODEL_DIR)
    save_model(elastic, f"LR_{gen_name.replace('/', '_')}_ElasticNet_tuned", output_dir=MODEL_DIR)

    results = pd.DataFrame({
        "모델": ["Ridge", "Lasso", "ElasticNet"],
        "alpha": [ridge.alpha_, lasso.alpha_, elastic.alpha_],
        "R²": [ridge.score(X_scaled, y), lasso.score(X_scaled, y), elastic.score(X_scaled, y)]
    })
    results.to_csv(os.path.join(RESULT_DIR, f"{gen_name}_규제모델튜닝.csv"), index=False, encoding='utf-8-sig')
    print(f"✅ {gen_name}: 규제모델 튜닝 및 모델 저장 완료")

print("\n🎯 모든 발전기 규제모델 튜닝 완료 — 결과 및 모델 저장됨")
print(f"📄 결과 CSV 폴더: {RESULT_DIR}")
print(f"💾 모델 저장 폴더: {MODEL_DIR}")
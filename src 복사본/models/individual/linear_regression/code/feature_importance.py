import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from src.utils.model_utils import save_model

plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = "/Users/parkhyeji/Desktop/PV"
DATA_PATH = os.path.join(BASE_DIR, "data/outliers_removed/이상치제거_데이터.csv")

RESULT_DIR = os.path.join(BASE_DIR, "src/models/individual/linear_regression/results/feature_importance")
PLOT_DIR = os.path.join(BASE_DIR, "src/models/individual/linear_regression/plots/feature_importance")
MODEL_DIR = os.path.join(BASE_DIR, "outputs/models/individual/linear_regression/feature_importance")

os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)
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

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LinearRegression().fit(X_scaled, y)

    model_name = f"LR_{gen_name.replace('/', '_')}_feature_importance"
    save_model(model, model_name=model_name, output_dir=MODEL_DIR)

    importance = pd.Series(np.abs(model.coef_), index=X.columns).sort_values(ascending=False)
    importance.to_csv(os.path.join(RESULT_DIR, f"{gen_name}_변수중요도.csv"), encoding='utf-8-sig')

    plt.figure(figsize=(8, 4))
    importance.plot(kind='barh', color='teal')
    plt.title(f"[{gen_name}] 변수 중요도 (절댓값 기준)")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, f"{gen_name}_변수중요도.png"), dpi=300)
    plt.close()

print("✅ 변수 중요도 분석 완료")
print(f"📁 모델 저장 폴더: {MODEL_DIR}")
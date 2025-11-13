# -*- coding: utf-8 -*-
"""
🌞 XGBoost 단일 모델 학습 (발전기별 완전판 + 모델 저장)
────────────────────────────────────
① 발전기별 XGBoost 모델 학습
② 성능 평가 (R², RMSE, MAE, MAPE, NRMSE)
③ Feature Importance 분석
④ 실제 vs 예측 + 잔차 시각화
⑤ 모델(.pkl) 및 결과 CSV/PNG 저장
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

# ✅ macOS 한글 폰트 설정
plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False

# --------------------------------------------------
# 🔧 경로 설정
# --------------------------------------------------
BASE_DIR = "/Users/parkhyeji/Desktop/PV"
DATA_PATH = os.path.join(BASE_DIR, "data/outliers_removed/이상치제거_데이터.csv")

RESULT_DIR = os.path.join(BASE_DIR, "src/models/individual/xgboost/results/train")
PLOT_DIR = os.path.join(BASE_DIR, "src/models/individual/xgboost/plots/train")
FI_DIR = os.path.join(RESULT_DIR, "feature_importance")
MODEL_DIR = os.path.join(BASE_DIR, "outputs/models/individual/XGB/train")

os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)
os.makedirs(FI_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

# --------------------------------------------------
# 1️⃣ 데이터 로드
# --------------------------------------------------
df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
df = df[df["발전량(MWh)"] != 0].copy()

# --------------------------------------------------
# 2️⃣ 발전기별 모델 학습
# --------------------------------------------------
results = []
feature_importances = []

for gen_name, group in df.groupby("발전기명"):
    if len(group) < 30:
        print(f"⚠️ {gen_name}: 데이터 부족 → 건너뜀 ({len(group)}행)")
        continue

    print(f"\n🔹 {gen_name} 모델 학습 중...")

    # ✅ 입력 변수 (X), 타깃 변수 (y)
    X = group[[
        '설비용량(MW)', '평균기온', '평균습도', '총강수량', '총적설량',
        '평균풍속', '일조시간', '일사량', '평균운량'
    ]]
    y = group['발전량(MWh)']

    # 데이터 분할
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # --------------------------------------------------
    # 3️⃣ XGBoost 모델 정의 및 학습
    # --------------------------------------------------
    model = XGBRegressor(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1
    )

    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    # --------------------------------------------------
    # 4️⃣ 성능 지표 계산
    # --------------------------------------------------
    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    mape = np.mean(np.abs((y_test - y_pred) / y_test.replace(0, np.nan))) * 100
    nrmse = rmse / y_test.mean()

    results.append({
        "발전기명": gen_name,
        "R2": r2,
        "RMSE": rmse,
        "MAE": mae,
        "MAPE(%)": mape,
        "NRMSE": nrmse,
        "데이터수": len(group)
    })

    # --------------------------------------------------
    # 5️⃣ Feature Importance 저장
    # --------------------------------------------------
    fi = pd.DataFrame({
        "변수명": X.columns,
        "중요도": model.feature_importances_
    }).sort_values("중요도", ascending=False)
    fi["발전기명"] = gen_name
    feature_importances.append(fi)

    fi_path = os.path.join(FI_DIR, f"{gen_name}_feature_importance.csv")
    fi.to_csv(fi_path, index=False, encoding="utf-8-sig")

    # --------------------------------------------------
    # 6️⃣ 모델 저장 (.pkl)
    # --------------------------------------------------
    model_name = f"{gen_name}_XGB_model"
    save_model(model, model_name, output_dir=MODEL_DIR)
    print(f"💾 모델 저장 완료 → {os.path.join(MODEL_DIR, model_name)}.pkl")

    # --------------------------------------------------
    # 7️⃣ 시각화: (1) 실제 vs 예측
    # --------------------------------------------------
    plt.figure(figsize=(6,6))
    sns.scatterplot(x=y_test, y=y_pred, alpha=0.7)
    sns.lineplot(x=y_test, y=y_test, color='red', label='y=x')
    plt.xlabel("실제 발전량(MWh)")
    plt.ylabel("예측 발전량(MWh)")
    plt.title(f"📈 {gen_name} - 실제 vs 예측 (XGBoost)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    plot_path1 = os.path.join(PLOT_DIR, f"{gen_name}_실제vs예측.png")
    plt.savefig(plot_path1, bbox_inches="tight")
    plt.close()

    # --------------------------------------------------
    # 7️⃣ 시각화: (2) 잔차(residual) 플롯
    # --------------------------------------------------
    residuals = y_test - y_pred
    plt.figure(figsize=(6,4))
    sns.histplot(residuals, bins=20, kde=True)
    plt.title(f"📊 {gen_name} - 잔차 분포 (XGBoost)")
    plt.xlabel("잔차(실제 - 예측)")
    plt.tight_layout()

    plot_path2 = os.path.join(PLOT_DIR, f"{gen_name}_잔차분포.png")
    plt.savefig(plot_path2, bbox_inches="tight")
    plt.close()

    # --------------------------------------------------
    # 7️⃣ 시각화: (3) Feature Importance 막대그래프
    # --------------------------------------------------
    plt.figure(figsize=(7,4))
    sns.barplot(x="중요도", y="변수명", data=fi, palette="viridis")
    plt.title(f"🌟 {gen_name} - 변수 중요도 (XGBoost)")
    plt.tight_layout()

    plot_path3 = os.path.join(PLOT_DIR, f"{gen_name}_변수중요도.png")
    plt.savefig(plot_path3, bbox_inches="tight")
    plt.close()

    print(f"✅ {gen_name}: 결과 저장 완료")
    print(f"   ├─ 예측 그래프 → {plot_path1}")
    print(f"   ├─ 잔차 그래프 → {plot_path2}")
    print(f"   ├─ 중요도 그래프 → {plot_path3}")
    print(f"   ├─ 중요도 CSV → {fi_path}")
    print(f"   └─ 모델 파일 → {os.path.join(MODEL_DIR, model_name)}.pkl")

# --------------------------------------------------
# 8️⃣ 통합 결과 저장
# --------------------------------------------------
result_df = pd.DataFrame(results)
fi_full = pd.concat(feature_importances, ignore_index=True)

result_path = os.path.join(RESULT_DIR, "XGB_발전기별_성능평가결과.csv")
fi_path_full = os.path.join(FI_DIR, "XGB_전체_변수중요도.csv")

result_df.to_csv(result_path, index=False, encoding="utf-8-sig")
fi_full.to_csv(fi_path_full, index=False, encoding="utf-8-sig")

print("\n✅ 모든 발전기 XGBoost 학습 및 모델 저장 완료!")
print(f"📁 성능평가 결과: {result_path}")
print(f"📁 전체 변수 중요도: {fi_path_full}")
print(f"📁 모델 저장 폴더: {MODEL_DIR}")

import pandas as pd
import numpy as np
import os
import statsmodels.api as sm
from sklearn.preprocessing import StandardScaler
from src.utils.model_utils import save_model

# ----------------------------------------------------------
# ⚙️ 경로 설정
# ----------------------------------------------------------
BASE_DIR = "/Users/parkhyeji/Desktop/PV"
DATA_PATH = os.path.join(BASE_DIR, "data/outliers_removed/이상치제거_데이터.csv")

RESULT_DIR = os.path.join(BASE_DIR, "src/models/individual/linear_regression/results/backward_elimination")
MODEL_DIR = os.path.join(BASE_DIR, "outputs/models/individual/linear_regression/backward_elimination")

os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

# ----------------------------------------------------------
# 1️⃣ 데이터 로드
# ----------------------------------------------------------
df = pd.read_csv(DATA_PATH, encoding='utf-8-sig')
df = df[df['발전량(MWh)'] != 0].copy()

# ----------------------------------------------------------
# 2️⃣ 후진제거 함수
# ----------------------------------------------------------
def backward_elimination(X, y, significance_level=0.05):
    # ✅ 결측치 제거 후 인덱스 동기화
    valid_idx = X.dropna().index.intersection(y.dropna().index)
    X = X.loc[valid_idx].copy()
    y = y.loc[valid_idx].copy()

    # ✅ 표준화 후 DataFrame으로 복원 (인덱스 유지)
    scaler = StandardScaler()
    X_scaled = pd.DataFrame(
        scaler.fit_transform(X),
        columns=X.columns,
        index=X.index
    )

    # ✅ 상수항 추가
    X_with_const = sm.add_constant(X_scaled, has_constant='add')

    model = sm.OLS(y, X_with_const).fit()

    while True:
        pvals = model.pvalues.drop("const")  # 상수항 제외
        max_p = pvals.max()
        if max_p > significance_level:
            drop_col = pvals.idxmax()
            print(f"⚠️ 제거: {drop_col} (p={max_p:.4f})")
            X_with_const = X_with_const.drop(columns=[drop_col])
            model = sm.OLS(y, X_with_const).fit()
        else:
            break

    return model, X_with_const.columns

# ----------------------------------------------------------
# 3️⃣ 발전기별 실행
# ----------------------------------------------------------
for gen_name, group in df.groupby('발전기명'):
    if len(group) < 10:
        print(f"⏩ {gen_name}: 데이터 부족 → 스킵")
        continue

    X = group[['설비용량(MW)', '평균기온', '평균습도', '총강수량', '총적설량',
               '평균풍속', '일조시간', '일사량', '평균운량']]
    y = group['발전량(MWh)']

    try:
        model, selected = backward_elimination(X, y)
        result_txt = os.path.join(RESULT_DIR, f"{gen_name}_후진제거결과.txt")
        with open(result_txt, "w", encoding="utf-8") as f:
            f.write(model.summary().as_text())

        # ----------------------------------------------------------
        # ✅ 모델 저장 (.pkl)
        # ----------------------------------------------------------
        model_name = f"LR_{gen_name.replace('/', '_')}_BE"
        save_model(model, model_name=model_name, output_dir=MODEL_DIR)

        print(f"✅ {gen_name}: 후진제거 완료 → 남은 변수 {list(selected)}")


    except Exception as e:
        print(f"❌ {gen_name}: 오류 발생 — {e}")

print("🎯 전체 발전기 후진제거법 완료 — 결과 저장됨")
print(f"📄 결과 TXT 폴더: {RESULT_DIR}")
print(f"💾 모델 저장 폴더: {MODEL_DIR}")
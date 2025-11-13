# 전체 기상데이터 사용

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_squared_error

# ----------------------------------------------------------
# ✅ 모델 저장 유틸 임포트
# ----------------------------------------------------------
from src.utils.model_utils import save_model

# ----------------------------------------------------------
# ✅ macOS 한글 폰트 설정
# ----------------------------------------------------------
plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False


# ----------------------------------------------------------
# 🔧 경로 설정
# ----------------------------------------------------------
BASE_DIR = "/Users/parkhyeji/Desktop/PV"
DATA_PATH = os.path.join(BASE_DIR, "data/outliers_removed/이상치제거_데이터.csv")

RESULT_DIR = os.path.join(
    BASE_DIR, "src/models/individual/linear_regression/results/train")
PLOT_DIR = os.path.join(
    BASE_DIR, "src/models/individual/linear_regression/plots/train")

MODEL_DIR = os.path.join(BASE_DIR, "outputs/models/individual/linear_regression/train")

os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

OUTPUT_CSV = os.path.join(RESULT_DIR, "LR_results.csv")


# ----------------------------------------------------------
# 1️⃣ 데이터 로드
# ----------------------------------------------------------
df = pd.read_csv(DATA_PATH, encoding='utf-8-sig')

# ----------------------------------------------------------
# 2️⃣ 열별 결측치 개수 출력
# ----------------------------------------------------------
missing_summary = df.isnull().sum().reset_index()
missing_summary.columns = ['컬럼명', '결측치수']
missing_summary['결측치비율(%)'] = (missing_summary['결측치수'] / len(df) * 100).round(2)

print("\n📊 결측치 요약:")
print(missing_summary.to_string(index=False))

print(f"\n✅ 결측치 처리 완료 — 최종 데이터 {len(df):,}행 유지")


# 발전량 0 제거
df = df[df['발전량(MWh)'] != 0].copy()
print(f"✅ 발전량 0제거 후 데이터 로드 완료 ({len(df)}행)")

# ----------------------------------------------------------
# 2️⃣ 발전기별 다중선형회귀 학습
# ----------------------------------------------------------
results = []

for gen_name, group in df.groupby('발전기명'):
    if len(group) < 10:
        print(f"⚠️ {gen_name}: 데이터 부족 ({len(group)}개) → 스킵")
        continue

    X = group[['설비용량(MW)', '평균기온', '평균습도', '총강수량', '총적설량',
                '평균풍속', '일조시간', '일사량', '평균운량']]
    y = group['발전량(MWh)']

    X = X.dropna()
    y = y.loc[X.index]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42)

    model = LinearRegression()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    # ----------------------------------------------------------
    # 3️⃣ 평가 지표 계산
    # ----------------------------------------------------------
    r2 = r2_score(y_test, y_pred)
    rmse = mean_squared_error(y_test, y_pred) ** 0.5
    mape = np.mean(np.abs((y_test - y_pred) / y_test.replace(0, np.nan))) * 100
    mean_y = y_test.mean()
    nrmse = rmse / mean_y

    # 해석 레벨
    if nrmse < 0.1:
        level = "✅ 매우 우수"
    elif nrmse < 0.2:
        level = "👍 양호"
    elif nrmse < 0.3:
        level = "⚖️ 보통"
    else:
        level = "⚠️ 부정확"

    print(f"{gen_name}: R²={r2:.3f}, RMSE={rmse:.2f}, MAPE={mape:.1f}% → {level}")

    # ----------------------------------------------------------
    # 학습된 모델 저장 (발전기별로 개별 저장)
    # ----------------------------------------------------------
    # ✅ 파일명 안전하게
    model_name = f"linear_{gen_name.replace('/', '_').replace(' ', '_')}"
    save_model(model, model_name=model_name, output_dir=MODEL_DIR)

    # ----------------------------------------------------------
    # 4️⃣ 결과 저장용 딕셔너리 생성
    # ----------------------------------------------------------
    result = {
        "발전기명": gen_name,
        "데이터수": len(X),
        "R²": round(r2, 4),
        "RMSE": round(rmse, 4),
        "MAPE(%)": round(mape, 2),
        "NRMSE(평균)": round(nrmse, 3),
        "절편": round(model.intercept_, 4),
        "정확도 수준": level
    }

    for col, coef in zip(X.columns, model.coef_):
        result[col] = round(coef, 4)

    results.append(result)

    # ----------------------------------------------------------
    # 5️⃣ 시각화
    # ----------------------------------------------------------

    # (1) 실제 vs 예측 산점도
    plt.figure(figsize=(6, 6))
    plt.scatter(y_test, y_pred, color='royalblue', alpha=0.7)
    plt.plot([y_test.min(), y_test.max()], [
             y_test.min(), y_test.max()], 'r--', lw=2)
    plt.title(f"[{gen_name}] 실제 vs 예측 발전량")
    plt.xlabel("실제 발전량(MWh)")
    plt.ylabel("예측 발전량(MWh)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, f"{gen_name}_산점도.png"), dpi=300)
    plt.close()

    # (2) 잔차 분석
    residuals = y_test - y_pred
    plt.figure(figsize=(7, 4))
    plt.hist(residuals, bins=25, color='gray', alpha=0.8)
    plt.title(f"[{gen_name}] 잔차 분포")
    plt.xlabel("잔차(실제 - 예측)")
    plt.ylabel("빈도")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, f"{gen_name}_잔차분포.png"), dpi=300)
    plt.close()

    # (3) 예측 vs 실제 시계열 비교
    plt.figure(figsize=(10, 4))
    plt.plot(y_test.index, y_test.values, label='실제', color='black', lw=2)
    plt.plot(y_test.index, y_pred, label='예측',
             color='darkorange', lw=2, alpha=0.8)
    plt.title(f"[{gen_name}] 실제 vs 예측 추이")
    plt.xlabel("샘플(날짜순 아님)")
    plt.ylabel("발전량(MWh)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, f"{gen_name}_예측추이.png"), dpi=300)
    plt.close()

    # (4) 회귀계수 중요도 시각화
    plt.figure(figsize=(8, 4))
    plt.barh(X.columns, np.abs(model.coef_), color='teal', alpha=0.7)
    plt.title(f"[{gen_name}] 회귀계수 크기 (절댓값 기준)")
    plt.xlabel("계수 절댓값")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, f"{gen_name}_회귀계수.png"), dpi=300)
    plt.close()


# ----------------------------------------------------------
# 6️⃣ 전체 결과 저장 및 요약 그래프
# ----------------------------------------------------------
results_df = pd.DataFrame(results)
results_df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')

print(f"\n📁 발전기별 선형회귀 결과 저장 완료: {OUTPUT_CSV}")

# R² 비교 그래프
plt.figure(figsize=(10, 6))
plt.bar(results_df["발전기명"], results_df["R²"], color="seagreen")
plt.title("발전기별 R² (결정계수) 비교")
plt.ylabel("R²")
plt.xticks(rotation=45)
plt.grid(axis="y")
plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "전체_R2비교.png"), dpi=300)
plt.close()

# MAPE 비교 그래프
plt.figure(figsize=(10, 6))
plt.bar(results_df["발전기명"], results_df["MAPE(%)"], color="salmon")
plt.title("발전기별 MAPE(%) 비교")
plt.ylabel("MAPE(%)")
plt.xticks(rotation=45)
plt.grid(axis="y")
plt.tight_layout()
plt.savefig(os.path.join(PLOT_DIR, "전체_MAPE비교.png"), dpi=300)
plt.close()

print(f"🖼️ 시각화 결과 저장 완료: {PLOT_DIR}")
print(f"💾 개별 모델 저장 완료 경로: {MODEL_DIR}")
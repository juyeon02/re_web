import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score
from datetime import datetime
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

RESULT_DIR = os.path.join(BASE_DIR, "src/models/individual/random_forest/results/feature_importance")
DETAIL_DIR = os.path.join(RESULT_DIR, "details")
PLOT_DIR = os.path.join(BASE_DIR, "src/models/individual/random_forest/plots/feature_importance")
LOG_DIR = os.path.join(BASE_DIR, "src/models/individual/random_forest/logs/feature_importance")
MODEL_DIR = os.path.join(BASE_DIR, "outputs/models/individual/random_forest/feature_importance")

os.makedirs(RESULT_DIR, exist_ok=True)
os.makedirs(DETAIL_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

OUTPUT_CSV = os.path.join(RESULT_DIR, "RF_feature_importance.csv")

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

features = [
    '설비용량(MW)', '평균기온', '평균습도', '총강수량', '총적설량',
    '평균풍속', '일조시간', '일사량', '평균운량'
]

# ----------------------------------------------------------
# 2️⃣ 발전기별 변수 중요도 분석
# ----------------------------------------------------------
results = []

for gen_name, group in df.groupby('발전기명'):
    if len(group) < 10:
        print(f"⚠️ {gen_name}: 데이터 부족 → 스킵")
        continue

    print(f"\n[{gen_name}] 변수 중요도 분석 시작 ({len(group)}건)")

    X = group[features].dropna()
    y = group.loc[X.index, '발전량(MWh)']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestRegressor(n_estimators=500, random_state=42)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)

    importances = model.feature_importances_
    fi_df = pd.DataFrame({
        '변수': features,
        '중요도': importances
    }).sort_values('중요도', ascending=False)
    fi_df['누적 중요도'] = fi_df['중요도'].cumsum()
    fi_df.insert(0, '발전기명', gen_name)
    fi_df['R²'] = round(r2, 4)
    fi_df['순위'] = np.arange(1, len(fi_df)+1)
    results.append(fi_df)

    # ✅ 발전기별 상세 CSV 저장
    detail_path = os.path.join(DETAIL_DIR, f"{gen_name}_feature_importance.csv")
    fi_df.to_csv(detail_path, index=False, encoding='utf-8-sig')

    # ✅ 로그 저장
    log_path = os.path.join(LOG_DIR, f"{gen_name}_log.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"[{gen_name}] 변수 중요도 분석 로그 ({datetime.now()})\n")
        f.write(f"R²: {round(r2, 4)}\n\n")
        f.write(fi_df.to_string(index=False))

    # ✅ 그래프 1: 변수 중요도
    plt.figure(figsize=(8, 5))
    plt.barh(fi_df['변수'], fi_df['중요도'], color='teal')
    plt.title(f"[{gen_name}] 변수 중요도 (R²={r2:.4f})")
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, f"{gen_name}_변수중요도.png"), dpi=300)
    plt.close()

    # ✅ 그래프 2: 누적 중요도
    plt.figure(figsize=(8, 5))
    plt.plot(fi_df['변수'], fi_df['누적 중요도'], marker='o', color='darkorange')
    plt.title(f"[{gen_name}] 누적 중요도 (R²={r2:.4f})")
    plt.xlabel("변수명")
    plt.ylabel("누적 중요도")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, f"{gen_name}_누적중요도.png"), dpi=300)
    plt.close()

    # ✅ 모델 저장
    save_model(model, model_name=f"rf_full_{gen_name.replace('/', '_')}", output_dir=MODEL_DIR)

# ----------------------------------------------------------
# 3️⃣ 전체 요약 결과 저장
# ----------------------------------------------------------
if results:
    all_results = pd.concat(results, ignore_index=True)
    all_results.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')

    # ✅ 그래프 3: 발전기별 R² 비교
    plt.figure(figsize=(10, 6))
    r2_summary = all_results.groupby("발전기명")["R²"].mean().sort_values(ascending=False)
    plt.bar(r2_summary.index, r2_summary.values, color="seagreen")
    plt.title("발전기별 R² (결정계수) 비교")
    plt.xticks(rotation=45)
    plt.ylabel("R²")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, "전체_R2비교.png"), dpi=300)
    plt.close()

    # ✅ 그래프 4: 변수별 평균 중요도
    mean_importance = all_results.groupby("변수")["중요도"].mean().sort_values(ascending=False)
    plt.figure(figsize=(8, 5))
    plt.barh(mean_importance.index, mean_importance.values, color="steelblue")
    plt.title("전체 변수 평균 중요도")
    plt.xlabel("중요도 평균값")
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, "전체_변수평균중요도.png"), dpi=300)
    plt.close()

    print(f"\n✅ 변수 중요도 결과 저장 완료: {OUTPUT_CSV}")
    print(f"🖼️ 시각화 저장 폴더: {PLOT_DIR}")
    print(f"📁 상세 CSV 폴더: {DETAIL_DIR}")
    print(f"📜 로그 폴더: {LOG_DIR}")
    print(f"💾 모델 폴더: {MODEL_DIR}")
else:
    print("⚠️ 분석 가능한 데이터가 없습니다.")
import os
import joblib
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = "/Users/parkhyeji/Desktop/PV"

FEATURE_COLS = [
    '설비용량(MW)', '평균기온', '평균습도', '총강수량', '총적설량',
    '평균풍속', '일조시간', '일사량', '평균운량'
]

# 모든 발전기 모델 결과 저장 리스트
ALL_SCORES = []


# ------------------------------------------------------
# 📌 발전기별 Voting / Stacking / Blending 평가
# ------------------------------------------------------
def evaluate_models(df_sub, gen_name):

    print(f"\n🔍 {gen_name} - 모델 평가 시작")

    # ----------------------------------------------------
    # 1) 데이터 분리
    # ----------------------------------------------------
    X = df_sub[FEATURE_COLS]
    y = df_sub['발전량(MWh)']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # ----------------------------------------------------
    # 2) 모델 로드
    # ----------------------------------------------------
    model_paths = {
        "Voting": os.path.join(BASE_DIR, f"outputs/models/ensemble/voting/{gen_name}/VotingEnsemble_{gen_name}.pkl"),
        "Stacking": os.path.join(BASE_DIR, f"outputs/models/ensemble/stacking/{gen_name}/StackingEnsemble_{gen_name}.pkl"),
        "Blending": os.path.join(BASE_DIR, f"outputs/models/ensemble/blending/{gen_name}/BlendingEnsemble_{gen_name}.pkl"),
    }

    models = {}
    for name, path in model_paths.items():
        if os.path.exists(path):
            models[name] = joblib.load(path)
        else:
            print(f"⚠️ {name} 모델 없음 → {path}")

    if len(models) == 0:
        print(f"❌ {gen_name}: 모델 없음 → 스킵")
        return

    # ----------------------------------------------------
    # 3) 예측 수행 + 성능 저장
    # ----------------------------------------------------
    for model_name, model in models.items():

        # 🔹 Blending 구조
        if model_name == "Blending":
            base_models = model["models"]
            meta_model = model["meta_model"]

            blend_input = np.column_stack([m.predict(X_test) for m in base_models])
            pred = meta_model.predict(blend_input)
        else:
            pred = model.predict(X_test)

        # 🔹 평가 지표
        r2 = r2_score(y_test, pred)
        rmse = np.sqrt(mean_squared_error(y_test, pred))
        mae = mean_absolute_error(y_test, pred)

        # 전체 리스트에 누적 저장
        ALL_SCORES.append({
            "발전기명": gen_name,
            "Model": model_name,
            "R2": r2,
            "RMSE": rmse,
            "MAE": mae
        })

    print(f"✅ {gen_name} 평가 완료")


# ------------------------------------------------------
# 📌 전체 발전기 실행
# ------------------------------------------------------
if __name__ == "__main__":

    DATA_PATH = os.path.join(BASE_DIR, "data/outliers_removed/이상치제거_데이터.csv")
    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")

    # 발전기별 평가 진행
    for gen_name, subset in df.groupby("발전기명"):
        if len(subset) < 30:
            print(f"⚠️ {gen_name}: 데이터 부족 → 스킵")
            continue

        evaluate_models(subset, gen_name)

    # ------------------------------------------------------
    # 📌 전체 발전기 성능 통합 CSV 저장
    # ------------------------------------------------------
    ALL_SCORES_DF = pd.DataFrame(ALL_SCORES)

    SAVE_DIR = os.path.join(BASE_DIR, "src/models/ensemble/analysis/results/model_comparison")
    os.makedirs(SAVE_DIR, exist_ok=True)

    all_scores_path = os.path.join(SAVE_DIR, "all_generators_scores.csv")
    ALL_SCORES_DF.to_csv(all_scores_path, encoding="utf-8-sig", index=False)

    print(f"\n📄 전체 성능 CSV 저장 완료 → {all_scores_path}")

    # ------------------------------------------------------
    # 📌 전체 발전기 중 가장 우수한 모델 1개 선택
    # ------------------------------------------------------
    # 모델별 평균 성능 계산
    model_mean = ALL_SCORES_DF.groupby("Model").agg({
        "R2": "mean",
        "RMSE": "mean",
        "MAE": "mean"
    }).reset_index()

    # R2 높을수록 좋음 / RMSE & MAE 낮을수록 좋음
    best_model_row = model_mean.sort_values(
        by=["R2", "RMSE", "MAE"],
        ascending=[False, True, True]
    ).iloc[0]

    best_model = best_model_row["Model"]

    # 결과 저장
    best_path = os.path.join(SAVE_DIR, "best_model_overall.csv")
    model_mean.to_csv(os.path.join(SAVE_DIR, "model_mean_scores.csv"), encoding="utf-8-sig", index=False)

    pd.DataFrame([{"최적모델": best_model}]).to_csv(
        best_path, encoding="utf-8-sig", index=False
    )

    print(f"\n🏆 전체 발전기 공통 최적 모델 → {best_model}")
    print(f"📄 best_model_overall.csv 저장 완료 → {best_path}")

    print("\n🎉 전체 파이프라인 완료!")

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


# ------------------------------------------------------
# 📌 발전기명별 3개 앙상블 모델 비교 함수 (CSV 저장 기능 포함)
# ------------------------------------------------------
def compare_ensemble_models(df_sub, gen_name):

    print(f"\n🔍 {gen_name} - Voting/Stacking/Blending 비교 시작")

    RESULT_DIR = os.path.join(
        BASE_DIR, "src/models/ensemble/analysis/results/gen_model_comparison", gen_name
    )
    os.makedirs(RESULT_DIR, exist_ok=True)

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

    if len(models) < 2:
        print(f"❌ 모델 부족 → 비교 불가 ({gen_name})")
        return

    # ----------------------------------------------------
    # 3) Voting / Stacking / Blending 예측 수행
    # ----------------------------------------------------
    preds = {}
    for model_name, model in models.items():

        # 🔹 Blending 구조: {"models": base_models, "meta_model": meta_model}
        if model_name == "Blending":
            base_models = model["models"]
            meta_model = model["meta_model"]

            blend_input = np.column_stack([m.predict(X_test) for m in base_models])
            preds[model_name] = meta_model.predict(blend_input)

        else:
            preds[model_name] = model.predict(X_test)

    # ----------------------------------------------------
    # 📌 4) 예측값 & 오차 CSV 저장
    # ----------------------------------------------------
    pred_df = pd.DataFrame({"Actual": y_test.values})
    error_df = pd.DataFrame()

    for model_name, pred in preds.items():
        pred_df[f"{model_name}_Pred"] = pred
        error_df[f"{model_name}_Error"] = y_test.values - pred

    pred_df.to_csv(os.path.join(RESULT_DIR, "predictions.csv"), encoding="utf-8-sig", index=False)
    error_df.to_csv(os.path.join(RESULT_DIR, "errors.csv"), encoding="utf-8-sig", index=False)

    print(f"📄 예측값 및 오차 CSV 저장 완료 → {RESULT_DIR}")

    # ----------------------------------------------------
    # 📌 5) 모델별 성능 지표 계산 후 CSV 저장
    # ----------------------------------------------------
    score_list = []
    for model_name, pred in preds.items():
        r2 = r2_score(y_test, pred)
        rmse = np.sqrt(mean_squared_error(y_test, pred))
        mae = mean_absolute_error(y_test, pred)

        score_list.append({
            "Model": model_name,
            "R2": r2,
            "RMSE": rmse,
            "MAE": mae
        })

    score_df = pd.DataFrame(score_list)
    score_df.to_csv(os.path.join(RESULT_DIR, "model_scores.csv"), encoding="utf-8-sig", index=False)

    print(f"📊 모델 성능 지표 CSV 저장 완료 → {RESULT_DIR}")

    # ----------------------------------------------------
    # 6) 시각화 — 실제값 vs 3개 모델 예측 비교
    # ----------------------------------------------------
    plt.figure(figsize=(10, 6))
    plt.plot(y_test.values, label="실제값", linewidth=2)

    for model_name in preds:
        plt.plot(preds[model_name], label=f"{model_name} 예측값", alpha=0.8)

    plt.title(f"{gen_name} - 실제값 vs 앙상블 예측값 비교")
    plt.xlabel("Index")
    plt.ylabel("발전량(MWh)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULT_DIR, "compare_predictions.png"))
    plt.close()

    # ----------------------------------------------------
    # 7) 시각화 — 모델별 오차 비교
    # ----------------------------------------------------
    plt.figure(figsize=(10, 6))

    for model_name in preds:
        plt.plot(y_test.values - preds[model_name], label=f"{model_name} 오차", alpha=0.8)

    plt.title(f"{gen_name} - 모델별 예측 오차 비교")
    plt.xlabel("Index")
    plt.ylabel("Error")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULT_DIR, "compare_errors.png"))
    plt.close()

    print(f"✅ 완료: {gen_name} 비교 결과 저장됨 → {RESULT_DIR}")


# ------------------------------------------------------
# 🔥 전체 발전기에 대해 실행
# ------------------------------------------------------
if __name__ == "__main__":

    DATA_PATH = os.path.join(BASE_DIR, "data/outliers_removed/이상치제거_데이터.csv")
    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")

    for gen_name, subset in df.groupby("발전기명"):
        if len(subset) < 30:
            print(f"⚠️ {gen_name}: 데이터 부족 → 스킵")
            continue
        compare_ensemble_models(subset, gen_name)

    print("\n🎉 모든 발전기 비교 결과(이미지+CSV) 생성 완료!")

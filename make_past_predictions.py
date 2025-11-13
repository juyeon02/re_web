# make_past_predictions.py
import pandas as pd
import os
import joblib  # ❗️ [수정] Pickle 대신 Joblib 사용
import numpy as np # ❗️ [추가] 데이터 타입 변환용

# --- 1. 설정 ---
LOCATIONS_FILE = "data/locations_원본.csv"
PAST_WEATHER_FILE = "data/과거기상.csv"
MODELS_DIR = "models/"
OUTPUT_FILE = "data/최종_과거_예측_데이터.csv" # ❗️ 이 파일을 생성합니다.

# ❗️ 모델이 학습한 9개 변수 (순서 중요!)
MODEL_FEATURES = [
    '설비용량(MW)', '평균기온', '평균습도', '총강수량', '총적설량',
    '평균풍속', '일조시간', '일사량', '평균운량'
]

print("스크립트 실행 시작...")

# --- 2. 데이터 불러오기 ---
try:
    df_locations = pd.read_csv(LOCATIONS_FILE)
    df_locations = df_locations[['발전기명', '설비용량(MW)']].copy()
    df_locations['발전기명'] = df_locations['발전기명'].str.strip()

    df_past_weather = pd.read_csv(PAST_WEATHER_FILE)
    df_past_weather['날짜'] = pd.to_datetime(df_past_weather['날짜']) 
    df_past_weather['발전기명'] = df_past_weather['발전기명'].str.strip()
    
    print("파일 로드 성공.")
except FileNotFoundError as e:
    print(f"오류: 필수 파일 없음 - {e.filename}")
    exit()
except Exception as e:
    print(f"파일 로드 중 오류: {e}")
    exit()

# --- 3. '과거 날씨' + '설비용량' 병합 ---
df_merged = pd.merge(df_past_weather, df_locations, on='발전기명', how='left')

if df_merged['설비용량(MW)'].isnull().any():
    print("경고: '설비용량(MW)'이 매칭되지 않는 발전기명이 있습니다.")

# --- 4. [중요] 단위 변환 (제거) ---
# ❗️ 모델이 변환 안 한 원본 단위(km/h, s, W/m²)로 학습했으므로
# ❗️ 예측 시에도 단위 변환을 "하면 안 됩니다".

# --- 5. 발전소별 '과거 예측' 실행 ---
all_predictions_dfs = []
plant_list = df_merged['발전기명'].unique()

print(f"총 {len(plant_list)}개 발전소의 과거 예측을 시작합니다...")

for plant_name in plant_list:
    
    plant_data = df_merged[df_merged['발전기명'] == plant_name].copy()
    
    if plant_data.empty:
        continue

    # 모델 파일 경로 생성 (7일발전량예측api.py와 동일 로직)
    clean_name = plant_name.strip().replace(' ', '')
    model_path = f"models/rf_full_{clean_name}_step9.pkl" # .pkl 파일 경로

    if os.path.exists(model_path):
        try:
            # ❗️ [수정] joblib.load() 사용
            model = joblib.load(model_path)
            
            # 예측에 필요한 9개 변수 준비
            # ❗️ [수정] 모델 호환성을 위해 데이터 타입을 float32로 변환
            X_test = plant_data[MODEL_FEATURES].astype(np.float32)
            
            plant_data['발전량_예측(MWh)'] = model.predict(X_test)
            print(f"  ✅ '{plant_name}' 예측 완료.")
            
        except Exception as e:
            # ❗️ 여기서 STACK_GLOBAL 오류가 또 발생할 가능성이 높음
            print(f"  ⚠️ '{plant_name}' 예측 실패: {e}")
            plant_data['발전량_예측(MWh)'] = pd.NA
    else:
        print(f"  ⚠️ '{plant_name}' 모델 파일 없음: {model_path}")
        plant_data['발전량_예측(MWh)'] = pd.NA
        
    all_predictions_dfs.append(plant_data)

# --- 6. 최종 파일 저장 ---
final_output_df = pd.concat(all_predictions_dfs, ignore_index=True)

final_output_df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')

print(f"\n🎉 작업 완료! '{OUTPUT_FILE}' 파일이 생성되었습니다.")
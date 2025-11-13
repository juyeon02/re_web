import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry
import os # 파일 확인을 위해 import
import pickle # ❗️ Pickle(.pkl) 임포트

# --- 1. 로케이션 파일 먼저 불러오기 ---
location_file = "data/locations_원본.csv"
if not os.path.exists(location_file):
    print(f"오류: '{location_file}' 파일을 찾을 수 없습니다.")
    exit() # 파일 없으면 중지

print(f"'{location_file}' 파일 로드 중...")
location_df = pd.read_csv(location_file)
location_df.columns = location_df.columns.str.strip()

# '설비용량(MW)' 포함 필수 컬럼 확인
required_cols = ['발전기명', '위도', '경도', '설비용량(MW)']
if not all(col in location_df.columns for col in required_cols):
    print(f"오류: '{location_file}'에 필요한 컬럼({required_cols})이 모두 없습니다!")
    print(f"(현재 컬럼: {location_df.columns.tolist()})")
    exit() # 컬럼 없으면 중지

# ❗️ 모델 학습에 사용된 변수(컬럼) 9개 목록 (순서 중요!)
MODEL_FEATURES = [
    '설비용량(MW)',
    '평균기온', 
    '평균습도', 
    '총강수량', 
    '총적설량', 
    '평균풍속', 
    '일조시간', 
    '일사량', 
    '평균운량'
]
# ⚠️⚠️⚠️ 위 9개 순서가 실제 모델 학습 순서와 다르면 오류가 납니다 ⚠️⚠️⚠️


# --- 2. Open-Meteo API 설정 (Forecast API) ---
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600) 
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

url = "https://api.open-meteo.com/v1/forecast"

# ❗️ 'daily'(일별) 8개 기상 변수 요청
params = {
    "latitude": location_df['위도'].tolist(),
    "longitude": location_df['경도'].tolist(),
    "daily": [
        "temperature_2m_mean",       # 평균기온
        "relative_humidity_2m_mean", # 평균습도
        "precipitation_sum",         # 총강수량
        "snowfall_sum",              # 총적설량
        "wind_speed_10m_mean",       # 평균풍속
        "sunshine_duration_sum",     # 일조시간
        "shortwave_radiation_sum",   # 일사량
        "cloud_cover_mean"           # 평균운량
    ]
}
responses = openmeteo.weather_api(url, params=params)

# API 데이터를 담을 빈 리스트
all_dataframes = []

print("날씨 API (Forecast-Daily) 데이터 처리 중...")

# --- 3. 데이터 처리 (enumerate 사용) ---
for i, response in enumerate(responses):
    
    # ❗️ 'daily'(일별) 데이터 처리
    daily = response.Daily()
    daily_temperature_2m_mean = daily.Variables(0).ValuesAsNumpy()
    daily_relative_humidity_2m_mean = daily.Variables(1).ValuesAsNumpy()
    daily_precipitation_sum = daily.Variables(2).ValuesAsNumpy()
    daily_snowfall_sum = daily.Variables(3).ValuesAsNumpy()
    daily_wind_speed_10m_mean = daily.Variables(4).ValuesAsNumpy()
    daily_sunshine_duration_sum = daily.Variables(5).ValuesAsNumpy()
    daily_shortwave_radiation_sum = daily.Variables(6).ValuesAsNumpy()
    daily_cloud_cover_mean = daily.Variables(7).ValuesAsNumpy()
    
    date_range_utc = pd.date_range(
        start = pd.to_datetime(daily.Time(), unit = "s", utc = True),
        end = pd.to_datetime(daily.TimeEnd(), unit = "s", utc = True),
        freq = pd.Timedelta(seconds = daily.Interval()),
        inclusive = "left"
    )
    daily_data = {"날짜": date_range_utc.date}
    
    # ❗️ [기상 변수 8개] (MODEL_FEATURES 순서와 맞춤)
    daily_data["평균기온"] = daily_temperature_2m_mean
    daily_data["평균습도"] = daily_relative_humidity_2m_mean
    daily_data["총강수량"] = daily_precipitation_sum
    daily_data["총적설량"] = daily_snowfall_sum
    daily_data["평균풍속"] = daily_wind_speed_10m_mean / 3.6 # km/h -> m/s
    daily_data["일조시간"] = daily_sunshine_duration_sum / 3600.0 # s -> h
    daily_data["일사량"] = daily_shortwave_radiation_sum * 0.0036 # W/m² -> MJ/m²
    daily_data["평균운량"] = daily_cloud_cover_mean
    
    daily_dataframe = pd.DataFrame(data = daily_data)

    plant_name = location_df.iloc[i]['발전기명']
    daily_dataframe['발전기명'] = plant_name
    daily_dataframe['위도'] = location_df.iloc[i]['위도']
    daily_dataframe['경도'] = location_df.iloc[i]['경도']
    
    # ❗️ [필수 재료 1개] '설비용량(MW)'을 location_df에서 찾아서 추가
    capacity = location_df.iloc[i]['설비용량(MW)']
    daily_dataframe['설비용량(MW)'] = capacity 
    
    # ⬇️ --- Pickle(.pkl)로 모델 로드 및 발전량 예측 --- ⬇️
    model_path = f"models/{plant_name}_model.pkl" # ❗️ .pkl로 경로 수정

    if os.path.exists(model_path):
        try:
            # ❗️ pickle.load() 방식으로 수정
            with open(model_path, 'rb') as f:
                loaded_model = pickle.load(f)
            
            # 2. 모델 입력을 위해 [필수 재료 9개] 순서 맞추기
            X_test = daily_dataframe[MODEL_FEATURES]
            
            # 3. 예측 실행
            predictions = loaded_model.predict(X_test)
            daily_dataframe['발전량_예측(MWh)'] = predictions
            
        except Exception as e:
            print(f"⚠️ '{plant_name}' 모델 예측 중 오류 발생: {e}")
            daily_dataframe['발전량_예측(MWh)'] = pd.NA
    else:
        print(f"⚠️ 경고: '{model_path}' 모델 파일을 찾을 수 없습니다.")
        daily_dataframe['발전량_예측(MWh)'] = pd.NA
        
    all_dataframes.append(daily_dataframe)

# --- 4. 데이터 통합 및 저장 ---
print("날씨 API 데이터 처리 완료. 데이터 통합 및 저장 중...")

final_df = pd.concat(all_dataframes)

# --- 5. 최종 컬럼 선택 및 순서 정렬 ---
final_columns = [
    '날짜', 
    '발전기명', 
    '설비용량(MW)',
    '발전량_예측(MWh)', # 👈 최종 예측값
    '평균기온', 
    '평균습도', 
    '총강수량', 
    '총적설량',
    '평균풍속',
    '일조시간', 
    '일사량', 
    '평균운량',
    '위도',
    '경도'
]

final_output_columns = [col for col in final_columns if col in final_df.columns]
final_df = final_df[final_output_columns]

# --- 6. 최종 파일로 저장 ---
output_filename = "최종_일별_발전량_예측.csv" 
final_df.to_csv(output_filename, index=False, encoding='utf-8-sig')

print(f"\n🎉 작업 완료! {output_filename} 파일로 저장되었습니다.")
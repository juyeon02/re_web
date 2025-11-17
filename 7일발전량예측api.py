import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry
import os
import joblib  

location_file = "data/locations_원본.csv"
if not os.path.exists(location_file):
    print(f"오류: '{location_file}' 파일을 찾을 수 없습니다.")
    exit()

print(f"'{location_file}' 파일 로드 중...")
location_df = pd.read_csv(location_file)
location_df.columns = location_df.columns.str.strip()

# 필수 컬럼 확인
required_cols = ['발전기명', '위도', '경도', '설비용량(MW)']
if not all(col in location_df.columns for col in required_cols):
    print(f"오류: '{location_file}'에 필요한 컬럼({required_cols})이 모두 없습니다!")
    print(f"(현재 컬럼: {location_df.columns.tolist()})")
    exit()

# 모델 학습에 사용된 변수
MODEL_FEATURES = [
    '설비용량(MW)', '평균기온', '평균습도', '총강수량', '총적설량',
    '평균풍속', '일조시간', '일사량', '평균운량'
]

# Open-Meteo API 설정
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": location_df['위도'].tolist(),
    "longitude": location_df['경도'].tolist(),
    "daily": [
        "temperature_2m_mean", "relative_humidity_2m_mean", "precipitation_sum",
        "snowfall_sum", "wind_speed_10m_mean", "sunshine_duration",
        "shortwave_radiation_sum", "cloud_cover_mean"
    ]
}
responses = openmeteo.weather_api(url, params=params)
all_dataframes = []

print("날씨 API (Forecast-Daily) 데이터 처리 중...")

# 데이터 처리
for i, response in enumerate(responses):
    daily = response.Daily()
    daily_data = {
        "날짜": pd.date_range(
            start=pd.to_datetime(daily.Time(), unit="s", utc=True),
            end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=daily.Interval()),
            inclusive="left"
        ).date,
        "평균기온": daily.Variables(0).ValuesAsNumpy(),
        "평균습도": daily.Variables(1).ValuesAsNumpy(),
        "총강수량": daily.Variables(2).ValuesAsNumpy(),
        "총적설량": daily.Variables(3).ValuesAsNumpy(),
        "평균풍속": daily.Variables(4).ValuesAsNumpy() / 3.6,
        "일조시간": daily.Variables(5).ValuesAsNumpy() / 3600.0,
        "일사량": daily.Variables(6).ValuesAsNumpy() * 0.0036,
        "평균운량": daily.Variables(7).ValuesAsNumpy()
    }

    daily_df = pd.DataFrame(data=daily_data)

    plant_name = location_df.iloc[i]['발전기명']
    daily_df['발전기명'] = plant_name
    daily_df['위도'] = location_df.iloc[i]['위도']
    daily_df['경도'] = location_df.iloc[i]['경도']
    daily_df['설비용량(MW)'] = location_df.iloc[i]['설비용량(MW)']

    # 모델 파일 경로 설정
    clean_name = plant_name.strip().replace(' ', '')
    model_path = f"models/rf_full_{clean_name}_step9.pkl"

    # --- 모델 예측 ---
    if os.path.exists(model_path):
        try:

            loaded_model = joblib.load(model_path)

            X_test = daily_df[MODEL_FEATURES].apply(pd.to_numeric, errors='coerce').fillna(0)

            predictions = loaded_model.predict(X_test)
            daily_df['발전량_예측(MWh)'] = predictions

            print(f"✅ '{clean_name}' 모델 예측 성공.")

        except Exception as e:
            print(f"⚠️ '{plant_name}' 모델 예측 중 오류 발생: {e.__class__.__name__} → {e}")
            daily_df['발전량_예측(MWh)'] = pd.NA
    else:
        print(f"⚠️ 경고: '{model_path}' 모델 파일을 찾을 수 없습니다.")
        daily_df['발전량_예측(MWh)'] = pd.NA

    all_dataframes.append(daily_df)

# 데이터 통합 및 저장
print("날씨 API 데이터 처리 완료. 데이터 통합 및 저장 중...")

final_df = pd.concat(all_dataframes, ignore_index=True)

# 컬럼 정리
final_columns = [
    '날짜', '발전기명', '설비용량(MW)', '발전량_예측(MWh)',
    '평균기온', '평균습도', '총강수량', '총적설량', '평균풍속',
    '일조시간', '일사량', '평균운량', '위도', '경도'
]
final_df = final_df[[col for col in final_columns if col in final_df.columns]]

# 파일 저장
output_filename = "data/최종_일별_발전량_예측.csv"
final_df.to_csv(output_filename, index=False, encoding='utf-8-sig')

print(f"\n  '{output_filename}' 파일로 저장되었습니다.")

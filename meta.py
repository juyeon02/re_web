import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry
import os # 파일 확인을 위해 import

# --- 1. 로케이션 파일 먼저 불러오기 ---
location_file = "data/locations_원본.csv"
if not os.path.exists(location_file):
    print(f"오류: '{location_file}' 파일을 찾을 수 없습니다.")
    exit() # 파일 없으면 중지

print(f"'{location_file}' 파일 로드 중...")
location_df = pd.read_csv(location_file)
location_df.columns = location_df.columns.str.strip()

# 필수 컬럼 확인
required_cols = ['발전기명', '위도', '경도']
if not all(col in location_df.columns for col in required_cols):
    print(f"오류: '{location_file}'에 필요한 컬럼({required_cols})이 없습니다.")
    exit() # 컬럼 없으면 중지

# --- 2. Open-Meteo API 설정 ---
cache_session = requests_cache.CachedSession('.cache', expire_after = -1)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

url = "https://archive-api.open-meteo.com/v1/archive"

# ❗️ [수정] 21개 변수(daily)로 변경 (빠진 3개 추가)
params = {
    "latitude": location_df['위도'].tolist(),
    "longitude": location_df['경도'].tolist(),
    "start_date": "2022-01-01",
    "end_date": "2025-06-30",
    "daily": [
        # 기존 18개
        "weather_code", "temperature_2m_mean", "temperature_2m_max", "temperature_2m_min", 
        "apparent_temperature_max", "apparent_temperature_mean", "apparent_temperature_min", 
        "precipitation_sum", "rain_sum", "snowfall_sum", "precipitation_hours", 
        "daylight_duration", "sunshine_duration", "et0_fao_evapotranspiration", 
        "shortwave_radiation_sum", "wind_direction_10m_dominant", "wind_gusts_10m_max", 
        "wind_speed_10m_max",
        # ❗️ [추가] 3개
        "relative_humidity_2m_mean", # 평균습도
        "wind_speed_10m_mean",     # 평균풍속
        "cloud_cover_mean"         # 평균운량
    ],
}
responses = openmeteo.weather_api(url, params=params)

# API 데이터를 담을 빈 리스트
all_dataframes = []

print("날씨 API (Archive-Daily) 데이터 처리 중...")

# ❗️ [수정] 21개 변수 순서대로 받기
for i, response in enumerate(responses):
    
    daily = response.Daily()
    # 기존 18개
    daily_weather_code = daily.Variables(0).ValuesAsNumpy()
    daily_temperature_2m_mean = daily.Variables(1).ValuesAsNumpy()
    daily_temperature_2m_max = daily.Variables(2).ValuesAsNumpy()
    daily_temperature_2m_min = daily.Variables(3).ValuesAsNumpy()
    daily_apparent_temperature_max = daily.Variables(4).ValuesAsNumpy()
    daily_apparent_temperature_mean = daily.Variables(5).ValuesAsNumpy()
    daily_apparent_temperature_min = daily.Variables(6).ValuesAsNumpy()
    daily_precipitation_sum = daily.Variables(7).ValuesAsNumpy()
    daily_rain_sum = daily.Variables(8).ValuesAsNumpy()
    daily_snowfall_sum = daily.Variables(9).ValuesAsNumpy()
    daily_precipitation_hours = daily.Variables(10).ValuesAsNumpy()
    daily_daylight_duration = daily.Variables(11).ValuesAsNumpy()
    daily_sunshine_duration = daily.Variables(12).ValuesAsNumpy()
    daily_et0_fao_evapotranspiration = daily.Variables(13).ValuesAsNumpy()
    daily_shortwave_radiation_sum = daily.Variables(14).ValuesAsNumpy()
    daily_wind_direction_10m_dominant = daily.Variables(15).ValuesAsNumpy()
    daily_wind_gusts_10m_max = daily.Variables(16).ValuesAsNumpy()
    daily_wind_speed_10m_max = daily.Variables(17).ValuesAsNumpy()
    # ❗️ [추가] 3개
    daily_relative_humidity_2m_mean = daily.Variables(18).ValuesAsNumpy()
    daily_wind_speed_10m_mean = daily.Variables(19).ValuesAsNumpy()
    daily_cloud_cover_mean = daily.Variables(20).ValuesAsNumpy()

    
    daily_data = {"date": pd.date_range(
        start = pd.to_datetime(daily.Time(), unit = "s", utc = True),
        end = pd.to_datetime(daily.TimeEnd(), unit = "s", utc = True),
        freq = pd.Timedelta(seconds = daily.Interval()),
        inclusive = "left"
    )}
    
    # ❗️ [수정] 21개 변수 데이터 추가 (한글 컬럼명)
    # 기존 18개
    daily_data["날씨코드"] = daily_weather_code
    daily_data["평균기온"] = daily_temperature_2m_mean
    daily_data["최고기온"] = daily_temperature_2m_max
    daily_data["최저기온"] = daily_temperature_2m_min
    daily_data["최고체감온도"] = daily_apparent_temperature_max
    daily_data["평균체감온도"] = daily_apparent_temperature_mean
    daily_data["최저체감온도"] = daily_apparent_temperature_min
    daily_data["총강수량"] = daily_precipitation_sum
    daily_data["비(Rain)"] = daily_rain_sum
    daily_data["눈(Snow)"] = daily_snowfall_sum
    daily_data["강수시간"] = daily_precipitation_hours
    daily_data["낮시간"] = daily_daylight_duration
    daily_data["일조시간"] = daily_sunshine_duration
    daily_data["증발산량"] = daily_et0_fao_evapotranspiration
    daily_data["일사량"] = daily_shortwave_radiation_sum
    daily_data["주풍향"] = daily_wind_direction_10m_dominant
    daily_data["최대돌풍"] = daily_wind_gusts_10m_max
    daily_data["최대풍속"] = daily_wind_speed_10m_max
    # ❗️ [추가] 3개
    daily_data["평균습도"] = daily_relative_humidity_2m_mean
    daily_data["평균풍속"] = daily_wind_speed_10m_mean
    daily_data["평균운량"] = daily_cloud_cover_mean

    
    daily_dataframe = pd.DataFrame(data = daily_data)

    # '발전기명'과 '위도/경도' 추가
    daily_dataframe['발전기명'] = location_df.iloc[i]['발전기명']
    daily_dataframe['위도'] = location_df.iloc[i]['위도']
    daily_dataframe['경도'] = location_df.iloc[i]['경도']
    
    all_dataframes.append(daily_dataframe)

# --- 3. 데이터 통합 및 저장 ---
print("날씨 API 데이터 처리 완료. 데이터 통합 및 저장 중...")

final_df = pd.concat(all_dataframes)

# ❗️ [수정] 새 파일 이름으로 저장
output_filename = "과거기상_21변수.csv"
final_df.to_csv(output_filename, index=False, encoding='utf-8-sig')

print(f"\n🎉 작업 완료! {output_filename} 파일로 저장되었습니다.")
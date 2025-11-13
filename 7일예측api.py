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

# --- 2. Open-Meteo API 설정 (Forecast API) ---
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600) # 1시간 캐시
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

url = "https://api.open-Meteo.com/v1/forecast"

params = {
    "latitude": location_df['위도'].tolist(),
    "longitude": location_df['경도'].tolist(),
    "hourly": ["temperature_2m", "weather_code", "relative_humidity_2m", "precipitation", "snowfall", "sunshine_duration", "shortwave_radiation", "wind_speed_10m", "cloud_cover"],
}
responses = openmeteo.weather_api(url, params=params)

# API 데이터를 담을 빈 리스트
all_weather_dataframes = []

print("날씨 API (Forecast) 데이터 처리 중...")

# --- 3. 데이터 처리 (enumerate 사용) ---
for i, response in enumerate(responses):
    
    # Process hourly data (순서 중요)
    hourly = response.Hourly()
    hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
    hourly_weather_code = hourly.Variables(1).ValuesAsNumpy()
    hourly_relative_humidity_2m = hourly.Variables(2).ValuesAsNumpy()
    hourly_precipitation = hourly.Variables(3).ValuesAsNumpy()
    hourly_snowfall = hourly.Variables(4).ValuesAsNumpy()
    hourly_sunshine_duration = hourly.Variables(5).ValuesAsNumpy()
    hourly_shortwave_radiation = hourly.Variables(6).ValuesAsNumpy()
    hourly_wind_speed_10m = hourly.Variables(7).ValuesAsNumpy()
    hourly_cloud_cover = hourly.Variables(8).ValuesAsNumpy()
    
    # KST 변환
    date_range_utc = pd.date_range(
        start = pd.to_datetime(hourly.Time(), unit = "s", utc = True),
        end = pd.to_datetime(hourly.TimeEnd(), unit = "s", utc = True),
        freq = pd.Timedelta(seconds = hourly.Interval()),
        inclusive = "left"
    )
    date_range_kst = date_range_utc.tz_convert('Asia/Seoul')
    hourly_data = {"date": date_range_kst}
    
    
    hourly_data["temperature_2m"] = hourly_temperature_2m
    hourly_data["weather_code"] = hourly_weather_code
    hourly_data["relative_humidity_2m"] = hourly_relative_humidity_2m
    hourly_data["precipitation"] = hourly_precipitation
    hourly_data["snowfall"] = hourly_snowfall
    
    # ⬇️ --- [수정] 단위 변환 적용 --- ⬇️
    
    # 일조시간: s -> h (시간)
    hourly_data["sunshine_duration"] = hourly_sunshine_duration / 3600.0
    
    # 일사량: W/m² -> MJ/m² (1시간 누적 에너지)
    # (W/m² = J/s/m²) -> (J/s/m²) * 3600s/h = (J/m²/h) -> (J/m²/h) / 1,000,000 = (MJ/m²/h)
    hourly_data["shortwave_radiation"] = hourly_shortwave_radiation * 0.0036
    
    # 풍속: km/h -> m/s
    hourly_data["wind_speed_10m"] = hourly_wind_speed_10m / 3.6
    
    # ⬆️ --- [수정 완료] --- ⬆️
    
    hourly_data["cloud_cover"] = hourly_cloud_cover
    
    hourly_dataframe = pd.DataFrame(data = hourly_data)

    hourly_dataframe['발전기명'] = location_df.iloc[i]['발전기명']
    hourly_dataframe['위도 (요청)'] = location_df.iloc[i]['위도']
    hourly_dataframe['경도 (요청)'] = location_df.iloc[i]['경도']
    
    all_weather_dataframes.append(hourly_dataframe)

# --- 4. 데이터 통합 및 저장 ---
print("날씨 API 데이터 처리 완료. 데이터 통합 및 저장 중...")

final_df = pd.concat(all_weather_dataframes)

# --- 5. 컬럼명 한글로 번역 (Hourly 변수에 맞게 수정) ---
translation_map = {
    'date': '날짜',
    'weather_code': '날씨코드',
    'temperature_2m': '기온', 
    'relative_humidity_2m': '상대습도', 
    'precipitation': '강수량', 
    'snowfall': '적설량', 
    'sunshine_duration': '일조시간', # 단위: h
    'shortwave_radiation': '일사량', # 단위: MJ/m²
    'wind_speed_10m': '풍속', # 단위: m/s
    'cloud_cover': '운량(%)', 
    '위도 (요청)': '위도',
    '경도 (요청)': '경도'
}

final_df_renamed = final_df.rename(columns=translation_map)

# --- 6. 최종 컬럼 선택 및 순서 정렬 ---
final_columns = [
    '날짜', 
    '발전기명', 
    '기온', 
    '상대습도', 
    '강수량', 
    '적설량',
    '풍속',
    '일조시간', 
    '일사량', 
    '운량(%)',
    '날씨코드',
    '위도',
    '경도'
]

final_output_df = final_df_renamed[final_columns]

# --- 7. 최종 파일로 저장 (다른 이름으로) ---
output_filename = "최종_날씨_예측_데이터.csv" # '예측' (Forecast)
final_output_df.to_csv(output_filename, index=False, encoding='utf-8-sig')

print(f"\n🎉 작업 완료! {output_filename} 파일로 저장되었습니다.")
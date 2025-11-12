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

# ❗️ [수정] params를 location_df에서 동적으로 생성
params = {
    "latitude": location_df['위도'].tolist(),
    "longitude": location_df['경도'].tolist(),
    "start_date": "2022-01-01",
    "end_date": "2025-06-30",
    "daily": ["weather_code", "temperature_2m_mean", "sunshine_duration", "precipitation_sum", "snowfall_sum", "shortwave_radiation_sum", "relative_humidity_2m_mean", "wind_speed_10m_mean", "cloud_cover_mean"],
}
responses = openmeteo.weather_api(url, params=params)

# API 데이터를 담을 빈 리스트
all_weather_dataframes = []

print("날씨 API 데이터 처리 중...")

# ❗️ [수정] 'enumerate'를 사용해 순번(i)과 응답(response)을 함께 처리
for i, response in enumerate(responses):
    # i = 0일 때, location_df의 0번째 행(첫 번째 발전기) 정보 사용
    # i = 1일 때, location_df의 1번째 행(두 번째 발전기) 정보 사용
    
    # Process daily data
    daily = response.Daily()
    daily_weather_code = daily.Variables(0).ValuesAsNumpy()
    daily_temperature_2m_mean = daily.Variables(1).ValuesAsNumpy()
    daily_sunshine_duration = daily.Variables(2).ValuesAsNumpy()
    daily_precipitation_sum = daily.Variables(3).ValuesAsNumpy()
    daily_snowfall_sum = daily.Variables(4).ValuesAsNumpy()
    daily_shortwave_radiation_sum = daily.Variables(5).ValuesAsNumpy()
    daily_relative_humidity_2m_mean = daily.Variables(6).ValuesAsNumpy()
    daily_wind_speed_10m_mean = daily.Variables(7).ValuesAsNumpy()
    daily_cloud_cover_mean = daily.Variables(8).ValuesAsNumpy()
    
    daily_data = {"date": pd.date_range(
        start = pd.to_datetime(daily.Time(), unit = "s", utc = True),
        end = pd.to_datetime(daily.TimeEnd(), unit = "s", utc = True),
        freq = pd.Timedelta(seconds = daily.Interval()),
        inclusive = "left"
    )}
    
    daily_data["weather_code"] = daily_weather_code
    daily_data["temperature_2m_mean"] = daily_temperature_2m_mean
    daily_data["sunshine_duration"] = daily_sunshine_duration
    daily_data["precipitation_sum"] = daily_precipitation_sum
    daily_data["snowfall_sum"] = daily_snowfall_sum
    daily_data["shortwave_radiation_sum"] = daily_shortwave_radiation_sum
    daily_data["relative_humidity_2m_mean"] = daily_relative_humidity_2m_mean
    daily_data["wind_speed_10m_mean"] = daily_wind_speed_10m_mean
    daily_data["cloud_cover_mean"] = daily_cloud_cover_mean
    
    daily_dataframe = pd.DataFrame(data = daily_data)

    # ❗️ [수정] merge 대신, 현재 순번(i)에 맞는 '발전기명'과 '위도/경도'를 바로 추가
    daily_dataframe['발전기명'] = location_df.iloc[i]['발전기명']
    daily_dataframe['위도 (요청)'] = location_df.iloc[i]['위도']
    daily_dataframe['경도 (요청)'] = location_df.iloc[i]['경도']
    
    all_weather_dataframes.append(daily_dataframe)

# --- 3. 데이터 통합 및 저장 ---
print("날씨 API 데이터 처리 완료. 데이터 통합 및 저장 중...")

# 모든 날씨 데이터를 하나로 합침
final_df = pd.concat(all_weather_dataframes)

# --- 4. 컬럼명 한글로 번역 (사용자님 버전) ---
translation_map = {
    'date': '날짜',
    'weather_code': '날씨코드',
    'temperature_2m_mean': '평균기온',
    'sunshine_duration': '일조시간',
    'precipitation_sum': '총강수량',
    'snowfall_sum': '총적설량',
    'shortwave_radiation_sum': '일사량',
    'relative_humidity_2m_mean': '평균습도',
    'wind_speed_10m_mean': '평균풍속',
    'cloud_cover_mean': '평균운량',
    '위도 (요청)': '위도', # 컬럼명 '위도'로 통일
    '경도 (요청)': '경도'  # 컬럼명 '경도'로 통일
}

final_df_renamed = final_df.rename(columns=translation_map)

# --- 5. 최종 컬럼 선택 및 순서 정렬 (사용자님 버전) ---
final_columns = [
    '날짜', 
    '발전기명', 
    '평균기온', 
    '평균습도', 
    '총강수량', 
    '총적설량',
    '평균풍속',
    '일조시간', 
    '일사량', 
    '평균운량',
    '날씨코드',
    '위도',
    '경도'
]

final_output_df = final_df_renamed[final_columns]

# --- 6. 최종 파일로 저장 ---
output_filename = "최종_날씨_발전기_데이터.csv"
final_output_df.to_csv(output_filename, index=False, encoding='utf-8-sig')

print(f"\n🎉 작업 완료! {output_filename} 파일로 저장되었습니다.")
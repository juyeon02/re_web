# 예측api.py (GitHub Actions 로봇이 실행할 파일)

import pandas as pd
import requests
import time
import datetime
import os
from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

AUTH_KEY = os.getenv("MY_API_KEY")
INPUT_FILE = "locations_원본.csv"
OUTPUT_FILE = "today_forecast_3hourly_final.csv" # 최종 저장 파일
BASE_URL = "https://apihub.kma.go.kr/api/typ01/cgi-bin/url/nph_sun_nwp_txt"
CONVERSION_FACTOR = (3 * 3600) / 1000000 
VARIABLES_TO_FETCH = {
    "DSWRF": "일사", "TMP": "기온", "RH": "습도"
}
time_periods = [
    {"name": "Part 1", "start_time": "0000", "end_time": "1500"},
    {"name": "Part 2", "start_time": "1800", "end_time": "2100"}
]

# --- 2. API 모델 시간 설정 ---
# (이 스크립트는 '내일' 날씨를 예측합니다)
try:
    TODAY = datetime.datetime.now()
    TOMORROW = TODAY + datetime.timedelta(days=1)
    
    TOMORROW_STR = TOMORROW.strftime('%Y%m%d')    # 예: "20251111" (예측할 날짜)
    TODAY_STR = TODAY.strftime('%Y%m%d')          # 예: "20251110"
    
    # 가장 최근에 완성된 '오늘 18시 UTC' 모델 사용
    MODEL_RUN_TIME = TODAY_STR + "1800"

except Exception as e:
    print(f"날짜 생성 중 오류: {e}")
    # 오류 시 대체 (오늘 18시, 내일 날짜)
    MODEL_RUN_TIME = datetime.datetime.now().strftime('%Y%m%d') + "1800"
    TOMORROW_STR = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y%m%d')

all_parsed_data = []

# --- 3. API 파서 함수 (UTC -> KST 변환 포함) ---
def parse_nwp_response(text_data, location_name, variable_name_korean):
    # (이전 web.py에 있던 parse_nwp_response 함수와 동일)
    try:
        lines = text_data.strip().split('\n')
        table_lines = [line.strip() for line in lines if line.strip().startswith('|')]
        if len(table_lines) < 2: return None
        header_line = table_lines[0]
        headers = [h.strip() for h in header_line.split('|') if h.strip()]
        data_line = table_lines[1]
        values = [v.strip() for v in data_line.split('|') if v.strip()]
        time_headers = headers[4:]
        time_values = values[4:]
        if len(time_headers) != len(time_values): return None
        
        parsed_data = []
        for dt_str, val_str in zip(time_headers, time_values):
            try:
                dt_utc = pd.to_datetime(dt_str, format='%Y%m%d%H').tz_localize('UTC')
                dt_obj = dt_utc.tz_convert('Asia/Seoul') # KST
                value = float(val_str.replace('-nan', 'NaN'))
            except ValueError:
                continue
            parsed_data.append({
                "발전기명": location_name, "DATETIME": dt_obj,
                "변수명": variable_name_korean, "값": value
            })
        return pd.DataFrame(parsed_data) if parsed_data else None
    except Exception as e:
        print(f"   -> [파싱 함수 오류] {location_name} ({variable_name_korean}): {e}")
        return None

# --- 4. 메인 스크립트 실행 ---
print(f"--- '내일({TOMORROW_STR})' 예측 데이터 수집 및 변환 시작 ---")
print(f"'{MODEL_RUN_TIME}' 모델 (오늘 18시 UTC) 기준\n")

try:
    # 1. (수정!) locations.csv를 'UTF-8'로 읽습니다.
    df_locations = pd.read_csv(INPUT_FILE)
    
    for row in df_locations.itertuples():
        lat = row.위도
        lon = row.경도
        location_name = row.발전기명.strip()
        
        print(f"--- 📍'{location_name}' (위도:{lat}, 경도:{lon}) 처리 중 ---")
    
        for var_code, var_name_korean in VARIABLES_TO_FETCH.items():
            for period in time_periods:
                
                forecast_start_time = TOMORROW_STR + period['start_time']
                forecast_end_time = TOMORROW_STR + period['end_time']
                
                params = {
                    'authKey': AUTH_KEY, 'nwp': 'KIMG', 'varn': var_code,
                    'tm': MODEL_RUN_TIME,
                    'tmef1': forecast_start_time,
                    'tmef2': forecast_end_time, 'int': 3, 'lat': lat, 'lon': lon
                }

                try:
                    response = requests.get(BASE_URL, params=params, timeout=60) 

                    if response.status_code == 200:
                        data_text = response.text.strip()
                        if data_text and not data_text.startswith("#ERROR") and not data_text.startswith("<Error>"):
                            df_temp = parse_nwp_response(data_text, location_name, var_name_korean)
                            if df_temp is not None and not df_temp.empty:
                                all_parsed_data.append(df_temp)
                        else:
                            print(f"   -> [API 오류] {period['name']} ({var_name_korean}) 응답: {data_text}")
                    else:
                        print(f"   -> [HTTP 오류] {period['name']} ({var_name_korean}): 상태 코드 {response.status_code}")

                except requests.exceptions.Timeout:
                    print(f"   -> [네트워크 오류] {period['name']} ({var_name_korean}) 요청 시간 초과.")
                except requests.exceptions.RequestException as e:
                    print(f"   -> [네트워크 오류] {period['name']} ({var_name_korean}) 요청 중 예외: {e}")
                
                time.sleep(0.5) # (안정성) 0.5초 대기
        print(f"--- ✔️ '{location_name}' 처리 완료 ---\n")

    # --- 5. [합본] 최종 변환 및 저장 ---
    if all_parsed_data:
        print(f"\n--- ✨ 모든 위치 데이터 취합 및 최종 변환 시작 ---")
        
        final_df = pd.concat(all_parsed_data, ignore_index=True)
        final_pivot_df = final_df.pivot_table(
            index=['발전기명', 'DATETIME'], columns='변수명', values='값'
        ).reset_index()
        final_pivot_df = final_pivot_df.sort_values(by=['발전기명', 'DATETIME'])
        
        final_pivot_df['일사'] = final_pivot_df['일사'].fillna(0)
        final_pivot_df['기온'] = final_pivot_df['기온'].fillna(0)
        final_pivot_df['습도'] = final_pivot_df['습도'].fillna(0)
        final_pivot_df['일사량(MJ/m²)'] = final_pivot_df['일사'] * CONVERSION_FACTOR
        final_pivot_df = final_pivot_df.drop(columns=['일사'])
        final_pivot_df['DATETIME'] = final_pivot_df['DATETIME'].dt.tz_localize(None)
        
        final_pivot_df = final_pivot_df.rename(columns={
            'DATETIME': '날짜', '기온': '기온(°C)', '습도': '습도(%)'
        })
        df_final_output = final_pivot_df[['발전기명', '날짜', '일사량(MJ/m²)', '기온(°C)', '습도(%)']]

        # 7-10. (수정!) 'UTF-8'로 CSV 파일 저장
        df_final_output.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
        
        print(f"\n--- ✨ 최종 변환 완료 ✨ ---")
        print(f"'{OUTPUT_FILE}' 파일로 저장했습니다.")
    else:
        print("\n--- 작업 완료 ---")
        print("성공적으로 가져온 데이터가 없습니다.")

except FileNotFoundError:
    print(f"오류: 입력 파일 '{INPUT_FILE}'을(를) 찾을 수 없습니다. (UTF-8 변환 필요)")
except Exception as e:
    print(f"[오류] 스크립트 실행 중 치명적인 오류가 발생했습니다: {e}")
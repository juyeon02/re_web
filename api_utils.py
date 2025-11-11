# api_utils.py

import streamlit as st
import pandas as pd
import requests
import time
import datetime

# -----------------------------------------------------------------
# ✨ 1시간 캐시가 적용된 API 호출 함수
# -----------------------------------------------------------------
@st.cache_data(ttl=3600)  # 3600초 = 1시간 동안 API 결과 캐시(저장)
def get_today_forecast(df_locations_for_api):
    """
    locations.csv의 위치를 기반으로 기상청 API를 호출하여
    오늘의 3시간 단위 날씨 예보(일사, 기온, 습도)를 DataFrame으로 반환합니다.
    (수정됨: time.sleep(0.5) 및 timeout=60 적용)
    """
    
    # --- 1. 파라미터 설정 ---
    AUTH_KEY = "vLfGjQIPTia3xo0CD94muA" # 사용자 API 키
    BASE_URL = "https://apihub.kma.go.kr/api/typ01/cgi-bin/url/nph_sun_nwp_txt"
    CONVERSION_FACTOR = (3 * 3600) / 1000000 
    VARIABLES_TO_FETCH = {
        "DSWRF": "일사", "TMP": "기온", "RH": "습도"
    }
    time_periods = [
        {"name": "Part 1", "start_time": "0000", "end_time": "1500"},
        {"name": "Part 2", "start_time": "1800", "end_time": "2100"}
    ]

    # --- 2. API 모델 시간 설정 (어제 18시 UTC) ---
    try:
        TODAY = datetime.datetime.now()
        YESTERDAY = TODAY - datetime.timedelta(days=1)
        TODAY_STR = TODAY.strftime('%Y%m%d')
        YESTERDAY_STR = YESTERDAY.strftime('%Y%m%d')
        MODEL_RUN_TIME = YESTERDAY_STR + "1800"
    except Exception as e:
        print(f"날짜 생성 중 오류: {e}")
        MODEL_RUN_TIME = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y%m%d') + "1800"
        TODAY_STR = datetime.datetime.now().strftime('%Y%m%d')
        
    all_parsed_data = []

    # --- 3. API 파서 함수 (UTC -> KST 변환 포함) ---
    def parse_nwp_response(text_data, location_name, variable_name_korean):
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

    # --- 4. 메인 API 요청 로직 ---
    print(f"--- '오늘({TODAY_STR})' 예측 데이터 수집 및 변환 시작 (캐시 실행) ---")

    try:
        for row in df_locations_for_api.itertuples():
            lat = row.위도
            lon = row.경도
            location_name = row.발전기명.strip()
            
            print(f"--- 📍'{location_name}' (위도:{lat}, 경도:{lon}) 처리 중 ---")
    
            for var_code, var_name_korean in VARIABLES_TO_FETCH.items():
                for period in time_periods:
                    forecast_start_time = TODAY_STR + period['start_time']
                    forecast_end_time = TODAY_STR + period['end_time']
                    
                    params = {
                        'authKey': AUTH_KEY, 'nwp': 'KIMG', 'varn': var_code,
                        'tm': MODEL_RUN_TIME, 'tmef1': forecast_start_time,
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
                                 print(f"   -> [API 응답 오류] {location_name} ({var_name_korean}): {data_text}")
                        else:
                             print(f"   -> [HTTP 오류] {location_name} ({var_name_korean}): 상태 코드 {response.status_code}")
                             
                    except requests.exceptions.Timeout:
                        print(f"   -> [네트워크 오류] {location_name} ({var_name_korean}) 요청 시간 초과 (60초).")
                    except Exception as e:
                        print(f"   -> [네트워크 오류] {location_name} ({var_name_korean}): {e}")
                    
                    time.sleep(0.5) 
        
        # --- 5. [합본] 최종 변환 ---
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
            
            print(f"\n--- ✨ API 호출 및 데이터 변환 완료 (캐시 저장) ---")
            
            return df_final_output

    except Exception as e:
        print(f"[오류] API 스크립트 실행 중 치명적인 오류가 발생했습니다: {e}")
        return pd.DataFrame() 

    return pd.DataFrame()
import pandas as pd
import requests
import io
import time
import datetime

# --- 1. 파라미터 설정 ---
AUTH_KEY = "vLfGjQIPTia3xo0CD94muA"
INPUT_FILE = "locations.csv"
INPUT_ENCODING = "cp949" 
OUTPUT_FILE = "today_forecast_3hourly_final.csv" # 최종 저장 파일
OUTPUT_ENCODING = "utf-8-sig"
BASE_URL = "https://apihub.kma.go.kr/api/typ01/cgi-bin/url/nph_sun_nwp_txt"

# [변환 계수]
# (3시간 * 3600초/시간) / (1,000,000 J/MJ) = 0.0108
CONVERSION_FACTOR = (3 * 3600) / 1000000 

# [API 요청 변수]
VARIABLES_TO_FETCH = {
    "DSWRF": "일사",   # 일사
    "TMP": "기온",   # 기온
    "RH": "습도"    # 상대습도
}

# [API 6개 제한 우회 시간대]
time_periods = [
    {"name": "Part 1", "start_time": "0000", "end_time": "1500"}, # 6개
    {"name": "Part 2", "start_time": "1800", "end_time": "2100"}  # 2개
]

# --- 2. API 모델 시간 설정 (어제 18시 UTC) ---
try:
    TODAY = datetime.datetime.now()
    YESTERDAY = TODAY - datetime.timedelta(days=1)
    
    TODAY_STR = TODAY.strftime('%Y%m%d')         # 예: "20251110" (예측할 날짜)
    YESTERDAY_STR = YESTERDAY.strftime('%Y%m%d') # 예: "20251109"
    
    # 가장 최근에 완성된 '어제 18시 UTC' 모델 사용
    MODEL_RUN_TIME = YESTERDAY_STR + "1800"

except Exception as e:
    print(f"날짜 생성 중 오류: {e}")
    MODEL_RUN_TIME = "202511091800" # 오류 시 대체 (어제 18시)
    TODAY_STR = "20251110"        # 오류 시 대체 (오늘)

# 최종 결과를 담을 리스트
all_parsed_data = []

# -----------------------------------------------------------------
# --- 3. API 파서 함수 (UTC -> KST 변환 포함) ---
# -----------------------------------------------------------------
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
                # [KST 변환]
                dt_utc = pd.to_datetime(dt_str, format='%Y%m%d%H').tz_localize('UTC')
                dt_obj = dt_utc.tz_convert('Asia/Seoul') # KST로 변환
                
                value = float(val_str.replace('-nan', 'NaN'))
            except ValueError:
                continue
                
            parsed_data.append({
                "발전기명": location_name,
                "DATETIME": dt_obj, # KST로 변환된 시간 (예: ...09:00:00+09:00)
                "변수명": variable_name_korean,
                "값": value
            })
        return pd.DataFrame(parsed_data) if parsed_data else None
    except Exception as e:
        print(f"     -> [파싱 함수 오류] {location_name} ({variable_name_korean}): {e}")
        return None
# -----------------------------------------------------------------
# --- 4. 메인 스크립트 실행 ---
# -----------------------------------------------------------------
print(f"--- '오늘({TODAY_STR})' 예측 데이터 수집 및 변환 시작 ---")
print(f"'{MODEL_RUN_TIME}' 모델 (어제 18시 UTC) 기준\n")

try:
    # 1. CSV (cp949) 읽기
    df_locations = pd.read_csv(INPUT_FILE, encoding=INPUT_ENCODING)
    
    # 2. 'locations.csv'의 모든 위치 반복
    for row in df_locations.itertuples():
        lat = row.위도
        lon = row.경도
        location_name = row.발전기명.strip()
        
        print(f"--- 📍'{location_name}' (위도:{lat}, 경도:{lon}) 처리 중 ---")
    
        # 3. 변수 리스트(DSWRF, TMP, RH) 반복
        for var_code, var_name_korean in VARIABLES_TO_FETCH.items():
            print(f"  -> 변수 '{var_name_korean}' (코드: {var_code}) 요청 중...")
            
            # 4. 시간 분할(Part 1, Part 2) 반복
            for period in time_periods:
                
                forecast_start_time = TODAY_STR + period['start_time']
                forecast_end_time = TODAY_STR + period['end_time']
                
                params = {
                    'authKey': AUTH_KEY, 'nwp': 'KIMG', 'varn': var_code,
                    'tm': MODEL_RUN_TIME,
                    'tmef1': forecast_start_time,
                    'tmef2': forecast_end_time,
                    'int': 3, 'lat': lat, 'lon': lon
                }

                try:
                    # 5. API 요청
                    response = requests.get(BASE_URL, params=params, timeout=30) 

                    if response.status_code == 200:
                        data_text = response.text.strip()
                        if data_text and not data_text.startswith("#ERROR") and not data_text.startswith("<Error>"):
                            # 6. KST 파서 호출
                            df_temp = parse_nwp_response(data_text, location_name, var_name_korean)
                            if df_temp is not None and not df_temp.empty:
                                all_parsed_data.append(df_temp) # 메모리에 추가
                            else:
                                 print(f"     -> [파싱 실패] {period['name']} ({var_name_korean}) 응답이 알 수 없는 형식입니다.")
                        elif data_text.count('\n') < 2:
                             print(f"     -> [알림] {period['name']} ({var_name_korean}) 데이터가 없습니다 (API가 빈 응답 반환).")
                        else:
                            print(f"     -> [API 오류] {period['name']} ({var_name_korean}) 응답: {data_text}")
                    else:
                        print(f"     -> [HTTP 오류] {period['name']} ({var_name_korean}): 상태 코드 {response.status_code}")

                except requests.exceptions.Timeout:
                    print(f"     -> [네트워크 오류] {period['name']} ({var_name_korean}) 요청 시간 초과.")
                except requests.exceptions.RequestException as e:
                    print(f"     -> [네트워크 오류] {period['name']} ({var_name_korean}) 요청 중 예외: {e}")
                
                time.sleep(0.1) 
        print(f"--- ✔️ '{location_name}' 처리 완료 ---\n")

    # --- 5. [합본] 최종 변환 및 저장 ---
    if all_parsed_data:
        print(f"\n--- ✨ 모든 위치 데이터 취합 및 최종 변환 시작 ---")
        
        # 7-1. 모든 데이터를 하나로 합치기
        final_df = pd.concat(all_parsed_data, ignore_index=True)
        
        # 7-2. 피벗(Pivot) 테이블: '변수명'을 컬럼으로 변경
        final_pivot_df = final_df.pivot_table(
            index=['발전기명', 'DATETIME'], 
            columns='변수명', 
            values='값'
        ).reset_index()
        
        # 7-3. 정렬
        final_pivot_df = final_pivot_df.sort_values(by=['발전기명', 'DATETIME'])
        
        print("     -> 피벗 테이블 생성 완료 (KST 시간 적용됨)")

        # 7-4. 결측값(NaN)을 0으로 처리 (계산을 위해)
        final_pivot_df['일사'] = final_pivot_df['일사'].fillna(0)
        final_pivot_df['기온'] = final_pivot_df['기온'].fillna(0)
        final_pivot_df['습도'] = final_pivot_df['습도'].fillna(0)
    
        # 7-5. [MJ/m² 변환]
        final_pivot_df['일사량(MJ/m²)'] = final_pivot_df['일사'] * CONVERSION_FACTOR
        
        # 7-6. 원본 '일사 (W/m²)' 컬럼은 삭제
        final_pivot_df = final_pivot_df.drop(columns=['일사'])
        
        print("     -> 일사량 단위 변환 (W/m² -> 3시간 누적 MJ/m²) 완료")
        
        # 7-7. [날짜 형식 수정] +09:00 시간대 정보 제거
        final_pivot_df['DATETIME'] = final_pivot_df['DATETIME'].dt.tz_localize(None)
        
        print("     -> 날짜 형식 정리 (시간대 정보 +09:00 제거) 완료")
        
        # 7-8. [컬럼명 수정]
        final_pivot_df = final_pivot_df.rename(columns={
            'DATETIME': '날짜',
            '기온': '기온(°C)',
            '습도': '습도(%)'
        })
        
        # 7-9. 컬럼 순서 재배치
        df_final_output = final_pivot_df[['발전기명', '날짜', '일사량(MJ/m²)', '기온(°C)', '습도(%)']]

        # 7-10. CSV 파일로 저장
        df_final_output.to_csv(OUTPUT_FILE, index=False, encoding=OUTPUT_ENCODING)
        
        print(f"\n--- ✨ 최종 변환 완료 ✨ ---")
        print(f"'{OUTPUT_FILE}' 파일로 저장했습니다.")

        print("\n--- 최종 데이터 미리보기 (처음 10행) ---")
        print(df_final_output.head(10))

    else:
        print("\n--- 작업 완료 ---")
        print("성공적으로 가져온 데이터가 없습니다.")

except FileNotFoundError:
    print(f"오류: 입력 파일 '{INPUT_FILE}'을(를) 찾을 수 없습니다.")
except Exception as e:
    print(f"[오류] 스크립트 실행 중 치명적인 오류가 발생했습니다: {e}")
import pandas as pd
import requests
import io
import time

# --- 파라미터 ---
AUTH_KEY = "vLfGjQIPTia3xo0CD94muA"
INTERVAL = 30 
INPUT_FILE = "locations.csv"
INPUT_ENCODING = "cp949" 
OUTPUT_FILE = "solar_data_2024_total.csv" 
OUTPUT_ENCODING = "utf-8-sig"
BASE_URL = "https://apihub.kma.go.kr/api/typ01/cgi-bin/url/nph_sun_sat_ana_txt"

START_DATE = "20240101" 
END_DATE = "20241231"   
# -----------------------------
all_dataframes = []
def parse_wide_format_response(text_data, location_name):
    try:
        lines = text_data.strip().split('\n')
        table_lines = [line.strip() for line in lines if line.strip().startswith('|')]
        
        if len(table_lines) < 2:
            return None

        header_line = table_lines[0]
        headers = [h.strip() for h in header_line.split('|') if h.strip()]
        
        data_line = table_lines[1]
        values = [v.strip() for v in data_line.split('|') if v.strip()]
        
        time_headers = headers[4:]
        time_values = values[4:]
        
        if len(time_headers) != len(time_values):
            return None

        parsed_data = []
        for dt_str, si_val in zip(time_headers, time_values):
            try:
                dt_obj = pd.to_datetime(dt_str, format='%Y%m%d%H%M')
                si = float(si_val.replace('-nan', 'NaN'))
            except ValueError:
                continue
                
            parsed_data.append({
                "발전기명": location_name,
                "DATETIME": dt_obj,
                "SI": si
            })
            
        if not parsed_data:
            return None
            
        return pd.DataFrame(parsed_data)
        
    except Exception as e:
        print(f"     -> [파싱 함수 오류] {location_name}: {e}")
        return None
# -----------------------------------------------------------------
try:
    # 1. CSV (cp949) 읽기
    df_locations = pd.read_csv(INPUT_FILE, encoding=INPUT_ENCODING)
    
    print(f"'{INPUT_FILE}' (인코딩: {INPUT_ENCODING}) 파일 로드 성공.")
    print(f"총 {len(df_locations)}개 위치에 대해 데이터 수집을 시작합니다.")
    print(f"데이터 기간: {START_DATE} 부터 {END_DATE} 까지\n")

    # START_DATE부터 END_DATE까지 하루 단위로 날짜 리스트 생성
    date_range = pd.date_range(start=START_DATE, end=END_DATE, freq='D')
    
    for current_day in date_range:
        current_day_str = current_day.strftime('%Y%m%d')
        print(f"--- [날짜 루프] {current_day_str} 데이터 수집 시작 ---")

        # [수정됨] 24개 제한 우회를 위한 시간대를 '현재 날짜' 기준으로 동적 생성
        time_periods = [
            {"name": "오전", "start": current_day_str + "0000", "end": current_day_str + "1130"},
            {"name": "오후", "start": current_day_str + "1200", "end": current_day_str + "2330"}
        ]
        
        for row in df_locations.itertuples():
            lat = row.위도
            lon = row.경도
            location_name = row.발전기명.strip() 
            
            print(f"--- 📍'{location_name}' (위도:{lat}, 경도:{lon}) 처리 중 ---")

            # 3. 오전/오후 2번 분할 요청
            for period in time_periods:
                print(f"     -> {period['name']} ({period['start']}~{period['end']}) 요청...")
                params = {
                    'authKey': AUTH_KEY,
                    'tm1': period['start'],
                    'tm2': period['end'],
                    'int': INTERVAL,
                    'lat': lat,
                    'lon': lon
                }

                try:
                    response = requests.get(BASE_URL, params=params, timeout=30) 

                    if response.status_code == 200:
                        data_text = response.text.strip()
                        
                        if data_text and not data_text.startswith("#ERROR") and not data_text.startswith("<Error>"):
                            
                            # 5. Wide 포맷 파서 호출
                            df_temp = parse_wide_format_response(data_text, location_name)
                            
                            if df_temp is not None and not df_temp.empty:
                                all_dataframes.append(df_temp)
                                print(f"     -> {period['name']} 데이터 파싱 성공 (데이터 {len(df_temp)}개)")
                            else:
                                # [예외 처리] Long 포맷이 올 경우
                                try:
                                    df_long = pd.read_csv(io.StringIO(data_text), delim_whitespace=True, comment='#')
                                    if 'SI' in df_long.columns:
                                        print(f"     -> [알림] {period['name']} 'Long' 포맷 데이터 파싱 성공 (데이터 {len(df_long)}개)")
                                        df_long['발전기명'] = location_name
                                        all_dataframes.append(df_long)
                                    else:
                                        print(f"     -> [파싱 실패] {period['name']} 응답이 알 수 없는 형식입니다: {data_text[:50]}...")
                                except Exception:
                                     print(f"     -> [파싱 실패] {period['name']} 응답이 알 수 없는 형식입니다: {data_text[:50]}...")

                        elif data_text.count('\n') < 2:
                             print(f"     -> [알림] {period['name']} 데이터가 없습니다 (API가 빈 응답 반환).")
                        else:
                            print(f"     -> [API 오류] {period['name']} 응답: {data_text}")
                
                
                    elif response.status_code == 429: # [중요] 429: Too Many Requests (트래픽 제한)
                        print(f"     -> [!!! API 트래픽 제한 감지 !!!] (HTTP 429)")
                        print("     -> 30초간 대기 후 재시도합니다...")
                        time.sleep(30)
                
                    else:
                        print(f"     -> [HTTP 오류] {period['name']}: 상태 코드 {response.status_code}")

                except requests.exceptions.Timeout:
                    print(f"     -> [네트워크 오류] {period['name']} 요청 시간 초과 (Timeout=30s).")
                except requests.exceptions.RequestException as e:
                    print(f"     -> [네트워크 오류] {period['name']} 요청 중 예외 발생: {e}")
                
                time.sleep(0.2)

            print(f"--- ✔️ '{location_name}' ({current_day_str}) 처리 완료 ---\n")
        
        print(f"--- [날짜 루프] {current_day_str} 데이터 수집 완료 ---\n" + "="*50 + "\n")


    # 데이터 취합 및 최종 파일 생성
    if all_dataframes:        
        final_df = pd.concat(all_dataframes, ignore_index=True)
        
        if 'DATETIME' not in final_df.columns:
            try:
                final_df['DATETIME'] = pd.to_datetime(final_df[['YEAR', 'MON', 'DAY', 'HR', 'MIN']])
            except Exception as e:
                print(f"날짜 변환 실패: {e}.")
        
        final_columns = ['발전기명', 'DATETIME', 'SI']
        existing_final_columns = [col for col in final_columns if col in final_df.columns]
        
        if 'SI' not in final_df.columns or '발전기명' not in final_df.columns:
             print("최종 데이터에 'SI' 또는 '발전기명' 컬럼이 없습니다.")
        
        else:
            final_output_df = final_df[existing_final_columns]
            final_output_df = final_output_df.sort_values(by=['발전기명', 'DATETIME'])
            final_output_df = final_output_df.drop_duplicates(subset=['발전기명', 'DATETIME'], keep='first')
            
            final_output_df.to_csv(OUTPUT_FILE, index=False, encoding=OUTPUT_ENCODING)
            
            print(f"모든 데이터를 '{OUTPUT_FILE}' 파일로 저장했습니다.")

            print("\n데이터 미리보기")
            print(final_output_df.head())

    else:
        print("\n--- 작업 완료 ---")
        print("모든 요청에서 유효한 데이터를 수집하지 못했습니다.")

except FileNotFoundError:
    print(f"오류 '{INPUT_FILE}'을 찾을 수 없습니다")
except Exception as e:
    print(f"스크립트 실행 중 오류 발생 {e}")
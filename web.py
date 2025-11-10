# 실행 명령어: streamlit run web.py

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px


# '예측api.py'에 필요했던 라이브러리들
import requests
import io
import time
import datetime

# -----------------------------------------------------------------
# ✨ 1. '예측api.py' 코드를 함수로 통합 (1시간 캐시 적용)
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
                        # --- 🚀 [수정됨 1] timeout=60으로 변경 ---
                        response = requests.get(BASE_URL, params=params, timeout=60) 
                        
                        if response.status_code == 200:
                            data_text = response.text.strip()
                            if data_text and not data_text.startswith("#ERROR") and not data_text.startswith("<Error>"):
                                df_temp = parse_nwp_response(data_text, location_name, var_name_korean)
                                if df_temp is not None and not df_temp.empty:
                                    all_parsed_data.append(df_temp)
                            else:
                                 # --- 🚀 [수정됨 2] API가 에러(#ERROR)를 보낼 때 ---
                                 print(f"   -> [API 응답 오류] {location_name} ({var_name_korean}): {data_text}")
                        else:
                             # --- 🚀 [수정됨 2] HTTP 상태 코드가 200이 아닐 때 ---
                             print(f"   -> [HTTP 오류] {location_name} ({var_name_korean}): 상태 코드 {response.status_code}")
                             
                    except requests.exceptions.Timeout:
                        # --- 🚀 [수정됨 2] 60초간 응답이 없을 때 ---
                        print(f"   -> [네트워크 오류] {location_name} ({var_name_korean}) 요청 시간 초과 (60초).")
                    except Exception as e:
                        print(f"   -> [네트워크 오류] {location_name} ({var_name_korean}): {e}")
                    
                    # --- 🚀 [수정됨 3] 0.5초 대기 ---
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

# -----------------------------------------------------------------
# ✨ 2. Streamlit 대시보드 본문 (기존 web.py)
# -----------------------------------------------------------------

# 1. 웹페이지 제목
st.set_page_config(layout="wide")
st.title("☀️ 태양광 발전량 대시보드 ☀️")

# 2. 데이터 파일 불러오기
try:
    # (로컬 실행을 위해 cp949 유지)
    df_locations = pd.read_csv("locations.csv", encoding='cp949') 
except FileNotFoundError:
    st.error("`locations.csv` 파일을 찾을 수 없습니다.")
    st.stop()
except Exception as e:
    st.error(f"locations.csv 로딩 오류: {e}.")
    st.stop()

try:
    df_generation = pd.read_csv("동서+중부(이상치제거).csv")
except FileNotFoundError:
    st.error("`동서+중부(이상치제거).csv` 파일을 찾을 수 없습니다.")
    st.stop()


# 3. (신규) '오늘 날씨 예보' 데이터 불러오기 (캐시된 함수 호출)
weather_data_available = False
df_current_weather = pd.DataFrame()

try:
    with st.spinner('오늘의 날씨 예보를 불러오는 중입니다... (최초 1회 몇 분 소요)'):
        # 1단계에서 만든 캐시 함수를 호출
        df_today_forecast = get_today_forecast(df_locations) 

    if not df_today_forecast.empty:
        # KST(한국 표준시) 기준 현재 시간 (시간대 정보 제거)
        now_kst = pd.to_datetime(datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))).tz_localize(None)
        
        df_today_forecast['날짜'] = pd.to_datetime(df_today_forecast['날짜'])

        # '날짜'와 'now_kst'의 시간 차이 계산
        df_today_forecast['time_diff'] = abs(df_today_forecast['날짜'] - now_kst)
        
        # '발전기명'별로 가장 가까운 시간대의 데이터(행)만 남김
        df_current_weather = df_today_forecast.loc[df_today_forecast.groupby('발전기명')['time_diff'].idxmin()]
        
        # 위치 정보(위도/경도/발전사)를 다시 합치기
        df_current_weather = pd.merge(df_current_weather, df_locations, on='발전기명')
        
        weather_data_available = True
    else:
        st.warning("날씨 예보 데이터를 불러오는 데 실패했거나 데이터가 없습니다.")
        
except Exception as e:
    st.error(f"날씨 API 데이터를 처리하는 중 오류가 발생했습니다: {e}")


# 4. 과거 발전량 데이터 전처리
df_generation['날짜'] = pd.to_datetime(df_generation['날짜'])
df_generation['연도'] = df_generation['날짜'].dt.year
df_generation['월'] = df_generation['날짜'].dt.month

company_colors = {
    '한국동서발전': 'blue',
    '한국중부발전': 'green',
    '한국남동발전': 'red',
}

# 5. 사이드바 필터
st.sidebar.title("필터")
company_list = ['전체'] + list(df_locations['발전사'].unique())
company = st.sidebar.selectbox(
    '발전사를 선택하세요:',
    company_list
)

# 6. 본문 지도 띄우기 (✨ 핵심 수정 ✨)
if company == '전체':
    # --- 6-1. '전체' 선택 시: 날씨 지도 ---
    map_center = [36.5, 127.5]
    zoom_level = 7
    m = folium.Map(location=map_center, zoom_start=zoom_level)

    if weather_data_available and not df_current_weather.empty:
        st.subheader(f"오늘의 발전소별 날씨 예보 (현재 기준)")
        
        for idx, row in df_current_weather.iterrows():
            temp = row['기온(°C)']
            insolation = row['일사량(MJ/m²)'] # 3시간 누적 일사량
            
            html = f"""
            <div style="font-family: 'Arial', sans-serif;
                        background-color: rgba(255, 255, 255, 0.85); 
                        border: 1px solid #777; 
                        border-radius: 5px; 
                        padding: 5px 8px; 
                        font-size: 11px; 
                        text-align: center;
                        box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
                        width: 90px;
                        white-space: nowrap;
                        overflow: hidden;
                        text-overflow: ellipsis;">
                <strong style="font-size: 13px; color: #333;">{row['발전기명']}</strong><br>
                <span style="color: #E67E22;">☀️ {insolation:.2f} MJ</span><br>
                <span style="color: #C0392B;">🌡️ {temp:.1f} °C</span>
            </div>
            """
            
            icon = folium.features.DivIcon(
                icon_size=(100, 50), 
                icon_anchor=(50, 25), 
                html=html
            )
            
            folium.Marker(
                location=[row['위도'], row['경도']],
                icon=icon,
                tooltip=f"{row['발전기명']} (날씨)"
            ).add_to(m)
    
    else:
        # 날씨 로딩 실패 시
        st.subheader("전체 발전소 위치 (날씨 정보 로드 실패)")
        for idx, row in df_locations.iterrows():
            folium.Marker(
                location=[row['위도'], row['경도']],
                popup=row['발전기명'],
                icon=folium.Icon(color='gray')
            ).add_to(m)
else:
    # --- 6-2. 특정 발전사 선택 시: 기존 로직 (발전소 마커) ---
    filtered_locations = df_locations[df_locations['발전사'] == company]
    
    if filtered_locations.empty:
        st.warning("해당 발전사의 위치 데이터가 없습니다.")
        st.stop() 
        
    map_center = [filtered_locations['위도'].mean(), filtered_locations['경도'].mean()]
    zoom_level = 8
    m = folium.Map(location=map_center, zoom_start=zoom_level)

    for idx, row in filtered_locations.iterrows():
        marker_color = company_colors.get(row['발전사'], 'gray')
        folium.Marker(
            location=[row['위도'], row['경도']],
            popup=f"<strong>{row['발전기명']}</strong><br>{row['발전사']}",
            tooltip=row['발전기명'],
            icon=folium.Icon(color=marker_color)
        ).add_to(m)

# 7. 지도 출력
map_data = st_folium(m, width=1200, height=500)


# 8. 그래프 그리기
st.header(f"📊 {company} 발전량 그래프")

if company == '전체':
    merged_data = pd.merge(df_generation, df_locations, on='발전기명')
else:
    plant_names = df_locations[df_locations['발전사'] == company]['발전기명'].tolist()
    merged_data = df_generation[df_generation['발전기명'].isin(plant_names)]


clicked_plant_name = map_data.get('last_object_clicked_tooltip')
graph_title_name = company

if clicked_plant_name and clicked_plant_name.endswith("(날씨)"):
    st.info("날씨 마커는 발전량 그래프와 연동되지 않습니다.")
    clicked_plant_name = None 
elif clicked_plant_name:
    merged_data = merged_data[merged_data['발전기명'] == clicked_plant_name]
    graph_title_name = clicked_plant_name
    st.subheader(f"➡️ {clicked_plant_name}")
else:
    st.subheader("전체 발전소 합계")

# 사이드바에 연도/월 필터 추가
st.sidebar.title("기간 필터")

year_list = ['전체'] + sorted(list(merged_data['연도'].unique()))
selected_year = st.sidebar.selectbox(
    '연도를 선택하세요:',
    year_list
)

if selected_year == '전체':
    month_list = ['전체'] + sorted(list(merged_data['월'].unique()))
else:
    month_list = ['전체'] + sorted(list(merged_data[merged_data['연도'] == selected_year]['월'].unique()))

selected_month = st.sidebar.selectbox(
    '월을 선택하세요:',
    month_list
)

# 기간 필터 적용
if selected_year != '전체':
    merged_data = merged_data[merged_data['연도'] == selected_year]
if selected_month != '전체':
    merged_data = merged_data[merged_data['월'] == selected_month]

# 9. 본문에 그래프 띄우기
if merged_data.empty:
    st.warning("선택한 조건의 발전량 데이터가 없습니다.")
else:
    daily_gen = merged_data.groupby('날짜')['발전량(MWh)'].sum().reset_index()

    if selected_year == '전체' and selected_month == '전체':
        title_suffix = "전체 기간"
    elif selected_year != '전체' and selected_month == '전체':
        title_suffix = f"{selected_year}년"
    elif selected_year != '전체' and selected_month != '전체':
        title_suffix = f"{selected_year}년 {selected_month}월"
    else: 
        title_suffix = f"매년 {selected_month}월"

    fig = px.line(daily_gen, x='날짜', y='발전량(MWh)',
                  title=f"{graph_title_name} {title_suffix} 발전량 합계 추이",
                  markers=True)

    st.plotly_chart(fig, use_container_width=True)
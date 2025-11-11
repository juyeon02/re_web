import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import datetime 

# 1. 웹페이지 제목
st.set_page_config(layout="wide")
st.title("태양광 발전량 대시보드")

# 2. 데이터 파일 불러오기
try:
    # (수정!) 'locations.csv'를 'UTF-8'로 읽습니다.
    df_locations = pd.read_csv("locations_원본.csv") 
except FileNotFoundError:
    st.error("`locations.csv` 파일을 찾을 수 없습니다. (UTF-8 변환 필요)")
    st.stop()

try:
    df_generation = pd.read_csv("동서+중부(이상치제거).csv")
except FileNotFoundError:
    st.error("`동서+중부(이상치제거).csv` 파일을 찾을 수 없습니다.")
    st.stop()


# 3. (✨ 핵심 수정 ✨) '오늘 날씨 예보' CSV 파일 바로 읽기
weather_data_available = False
df_current_weather = pd.DataFrame()

try:
    # (수정!) 미리 만들어진 예보 CSV 파일을 'UTF-8'로 읽습니다.
    df_today_forecast = pd.read_csv("today_forecast_3hourly_final.csv")
    
    if not df_today_forecast.empty:
        # KST(한국 표준시) 기준 현재 시간 (시간대 정보 제거)
        now_kst = pd.to_datetime(datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))).tz_localize(None)
        
        # (중요) CSV에서 읽은 '날짜'는 문자열이므로 datetime으로 변환
        df_today_forecast['날짜'] = pd.to_datetime(df_today_forecast['날짜'])

        # '날짜'와 'now_kst'의 시간 차이 계산
        df_today_forecast['time_diff'] = abs(df_today_forecast['날짜'] - now_kst)
        
        # '발전기명'별로 가장 가까운 시간대의 데이터(행)만 남김
        df_current_weather = df_today_forecast.loc[df_today_forecast.groupby('발전기명')['time_diff'].idxmin()]
        
        # 위치 정보(위도/경도/발전사)를 다시 합치기
        df_current_weather = pd.merge(df_current_weather, df_locations, on='발전기명')
        
        weather_data_available = True
    else:
        st.warning("날씨 예보 데이터가 없습니다. (CSV 파일이 비어있음)")
        
except FileNotFoundError:
    st.warning("`today_forecast_3hourly_final.csv` 파일을 찾을 수 없습니다. (자동 실행 대기 중)")
except Exception as e:
    st.error(f"날씨 예보 CSV 파일을 처리하는 중 오류가 발생했습니다: {e}")


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

# 6. 본문 지도 띄우기 (이전과 동일)
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


# 8. 그래프 그리기 (이전과 동일)
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
    
    st.plotly_chart(fig, width='stretch')
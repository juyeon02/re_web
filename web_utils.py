import streamlit as st
import pandas as pd
import folium
import json
import datetime
import copy
import plotly.express as px
import glob
import os
from datetime import date 

# -----------------------------------------------------------------
# 2. 데이터 로드 (모든 파일)
# -----------------------------------------------------------------
@st.cache_data
def load_data():
    try:
        df_locations = pd.read_csv("data/locations_원본.csv")
        df_locations['발전기명'] = df_locations['발전기명'].str.strip()

        # "실제" 과거 발전량 (타임존 없음 - Naive)
        generation_file = "data/발전량.csv"
        df_generation = pd.read_csv(generation_file)
        df_generation['날짜'] = pd.to_datetime(df_generation['날짜'], format='%Y.%m.%d')
        
        # --- (solar_analysis ... 기존과 동일 ... ) ---
        path = "solar_analysis/"
        file_list = glob.glob(os.path.join(path, "*_solar_utf8.csv"))
        if not file_list:
            st.error(f"'{path}' 폴더에서 태양광 CSV 파일을 찾을 수 없습니다.")
            st.stop()
        all_solar_data = []
        for file_path in file_list:
            filename = os.path.basename(file_path)
            try: year = int(filename.split('_')[0])
            except: continue
            df = pd.read_csv(file_path)
            df = df.rename(columns={'구분': '광역지자체'})
            month_cols = [f'{i}월' for i in range(1, 13)]
            for col in month_cols:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace(',', '')
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            df_long = df.melt(id_vars=['광역지자체'], value_vars=month_cols, var_name='월', value_name='태양광')
            df_long['연도'] = year
            df_long['월'] = df_long['월'].str.replace('월', '').astype(int)
            all_solar_data.append(df_long)
        df_region_solar_monthly = pd.concat(all_solar_data, ignore_index=True)
        df_region_solar_monthly['광역지자체'] = df_region_solar_monthly['광역지자체'].str.strip()
        df_region_solar_annual = df_region_solar_monthly.groupby(['연도', '광역지자체'])['태양광'].sum().reset_index()
        # --- ( ... 여기까지 동일 ... ) ---
        
        with open('data/korea_geojson.json', 'r', encoding='utf-8') as f:
            korea_geojson = json.load(f)

    except FileNotFoundError as e:
        st.error(f"필수 파일을 찾을 수 없습니다: {e.filename}. (data/ 폴더에 있는지 확인하세요)")
        st.stop()

    # "미래 7일" 예측 파일 로드
    try:
        df_today_forecast = pd.read_csv("최종_일별_발전량_예측.csv", parse_dates=['날짜'])
        # ❗️ [수정] 타임존 정보 제거
        if '날짜' in df_today_forecast.columns:
            df_today_forecast['날짜'] = df_today_forecast['날짜'].dt.tz_localize(None)
    except FileNotFoundError:
        st.warning("`최종_일별_발전량_예측.csv` 파일이 없습니다. (GitHub Actions가 실행되었는지 확인하세요)")
        df_today_forecast = pd.DataFrame()

    # "과거 예측" 파일 로드
    try:
        df_past_forecast = pd.read_csv(
            "data/최종_과거_예측_데이터.csv", 
            parse_dates=['날짜']
        )
        # ❗️ [수정] 타임존 정보 제거
        if '날짜' in df_past_forecast.columns:
            df_past_forecast['날짜'] = df_past_forecast['날짜'].dt.tz_localize(None)
    except FileNotFoundError:
        st.warning("`data/최종_과거_예측_데이터.csv` 파일이 없습니다. (make_past_predictions.py 실행 필요)")
        df_past_forecast = pd.DataFrame()

    return df_locations, df_generation, df_region_solar_annual, korea_geojson, df_today_forecast, df_region_solar_monthly, df_past_forecast

# -----------------------------------------------------------------
# 3. 날씨 데이터 처리 (공통)
# -----------------------------------------------------------------
def process_weather_data(df_today_forecast, df_locations):
    weather_data_available = False
    df_current_weather = pd.DataFrame()

    if not df_today_forecast.empty:
        try:
            # [수정] df_today_forecast가 타임존이 없으므로, KST 대신 일반 today 사용
            today = pd.Timestamp.now().date() 
            
            df_current_weather = df_today_forecast[
                df_today_forecast['날짜'].dt.date == today
            ].copy()

            if df_current_weather.empty:
                st.warning(f"오늘({today}) 날짜의 예측 데이터가 없습니다.")
            else:
                location_info = df_locations[['발전기명', '발전사']]
                df_current_weather = pd.merge(df_current_weather, location_info, on='발전기명', how='left')
                weather_data_available = True
                
        except Exception as e:
            st.error(f"일별 예보 처리 중 오류: {e}")
            
    return df_current_weather, weather_data_available

# -----------------------------------------------------------------
# 4. 헬퍼 함수 (지도 그리기용)
# -----------------------------------------------------------------
# (이하 create_weather_icon, draw_choropleth_map, draw_plant_weather_map 함수는
#  이전과 100% 동일합니다. 수정할 필요 없습니다.)

def create_weather_icon(row):
    temp = row.get('평균기온', 0)
    prediction = row.get('발전량_예측(MWh)', 0)

    html = f"""
    <div style="font-family: 'Arial', sans-serif;
                background-color: rgba(255, 255, 255, 0.85); 
                border: 1px solid #777; 
                border-radius: 5px; 
                padding: 5px 8px; 
                font-size: 11px; 
                text-align: center;
                box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
                width: 110px; 
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;">
        <strong style="font-size: 13px; color: #333;">{row['발전기명']}</strong><br>
        <span style="color: #E67E22; font-weight: bold;">⚡ {prediction:.2f} MWh</span><br>
        <span style="color: #C0392B;">🌡️ {temp:.1f} °C (평균)</span>
    </div>
    """
    return folium.features.DivIcon(
        icon_size=(120, 60), icon_anchor=(60, 30), html=html
    )

def draw_choropleth_map(korea_geojson, map_data, legend_title):
    m = folium.Map(location=[36.5, 127.5], zoom_start=7, tiles="OpenStreetMap")
    local_korea_geojson = copy.deepcopy(korea_geojson)

    if map_data.empty:
        st.warning(f"선택한 조건의 지도 데이터가 없습니다.")
        return m

    name_mapping = {
        '서울': 'Seoul', '부산': 'Busan', '대구': 'Daegu', '인천': 'Incheon',
        '광주': 'Gwangju', '대전': 'Daejeon', '울산': 'Ulsan', '세종': 'Sejong',
        '경기': 'Gyeonggi-do', '경기도': 'Gyeonggi-do', '강원': 'Gangwon-do',
        '강원도': 'Gangwon-do', '강원특별자치도': 'Gangwon-do', '충북': 'Chungcheongbuk-do',
        '충청북도': 'Chungcheongbuk-do', '충남': 'Chungcheongnam-do',
        '충청남도': 'Chungcheongnam-do', '전북': 'Jeollabuk-do',
        '전라북도': 'Jeollabuk-do', '전남': 'Jeollanam-do',
        '전라남도': 'Jeollanam-do', '경북': 'Gyeongsangbuk-do',
        '경상북도': 'Gyeongsangbuk-do', '경남': 'Gyeongsangnam-do',
        '경상남도': 'Gyeongsangnam-do', '제주': 'Jeju', '제주특별자치도': 'Jeju'
    }
    
    map_data = map_data.copy()
    map_data['geojson_name'] = map_data['광역지자체'].map(name_mapping)

    if map_data['geojson_name'].isnull().any():
        st.warning(f"일부 지역 이름이 지도와 매칭되지 않습니다: {map_data[map_data['geojson_name'].isnull()]['광역지자체'].unique()}")

    data_dict = map_data.set_index('geojson_name')['태양광']
    korean_name_dict = map_data.set_index('geojson_name')['광역지자체']

    for feature in local_korea_geojson['features']:
        name = feature['properties']['NAME_1'] # (영어 이름)
        feature['properties']['태양광'] = float(data_dict.get(name, 0))
        feature['properties']['KOREAN_NAME'] = str(korean_name_dict.get(name, 'N/A'))

    c = folium.Choropleth(
        geo_data=local_korea_geojson,
        name="choropleth",
        data=map_data,
        columns=["geojson_name", "태양광"],
        key_on="feature.properties.NAME_1",
        fill_color="YlOrRd",
        fill_opacity=0.7,
        line_opacity=0.3,
        legend_name=legend_title,
        highlight=True,
    ).add_to(m)

    folium.GeoJsonTooltip(
        fields=['KOREAN_NAME', '태양광'],
        aliases=['지역:', '발전량(MWh):'],
        localize=True, sticky=False, labels=True,
        style="""
            background-color: #F0EFEF;
            border: 2px solid black;
            border-radius: 3px;
            box-shadow: 3px;
            font-weight: bold; 
        """,
        max_width=800,
    ).add_to(c.geojson)

    return m

def draw_plant_weather_map(df_current_weather, weather_data_available, company_filter):
    m = folium.Map(location=[36.5, 127.5], zoom_start=7)

    if company_filter == '전체':
        data_to_draw = df_current_weather
        if not data_to_draw.empty:
            m.location = [36.5, 127.5]
            m.zoom_start = 7
    else:
        data_to_draw = df_current_weather[df_current_weather['발전사'] == company_filter]
        if not data_to_draw.empty:
            m.location = [data_to_draw['위도'].mean(), data_to_draw['경도'].mean()]
            m.zoom_start = 8

    if not weather_data_available or data_to_draw.empty:
        st.warning(f"'{company_filter}'의 오늘 날씨 예보 정보가 없습니다.")
        return m, None

    for idx, row in data_to_draw.iterrows():
        icon = create_weather_icon(row) 
        folium.Marker(
            location=[row['위도'], row['경도']],
            icon=icon,
            tooltip=row['발전기명']
        ).add_to(m)

    return m, data_to_draw
import streamlit as st
import pandas as pd
import folium
import json
import datetime
import copy
import plotly.express as px
import glob  # 파일 검색을 위해 추가
import os    # 파일 경로/이름 처리를 위해 추가

# -----------------------------------------------------------------
# 2. 데이터 로드 (모든 파일)
# -----------------------------------------------------------------
@st.cache_data
def load_data():
    try:
        # 발전소 위치 (UTF-8)
        df_locations = pd.read_csv("data/locations_원본.csv")
        df_locations['발전기명'] = df_locations['발전기명'].str.strip()

        # 과거 발전량
        df_generation = pd.read_csv("data/동서+중부(이상치제거).csv")

        # --- [수정] solar_analysis 폴더의 모든 CSV 읽기 ---
        path = "solar_analysis/"
        file_list = glob.glob(os.path.join(path, "*_solar_utf8.csv"))
        
        if not file_list:
            st.error(f"'{path}' 폴더에서 태양광 CSV 파일을 찾을 수 없습니다.")
            st.stop()
            
        all_solar_data = []
        
        for file_path in file_list:
            filename = os.path.basename(file_path)
            # 파일 이름에서 연도 추출 (e.g., "2020_solar_utf8.csv" -> 2020)
            try:
                year = int(filename.split('_')[0])
            except:
                st.warning(f"파일 이름 형식이 잘못되었습니다: {filename}. (예: 2020_solar_utf8.csv)")
                continue
                
            df = pd.read_csv(file_path)
            df = df.rename(columns={'구분': '광역지자체'})
            
            # 월별 컬럼(1월~12월)의 쉼표 제거 및 숫자 변환
            month_cols = [f'{i}월' for i in range(1, 13)]
            for col in month_cols:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace(',', '')
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # (Wide -> Long) Tidy 데이터로 변환
            df_long = df.melt(id_vars=['광역지자체'], 
                              value_vars=month_cols, 
                              var_name='월', 
                              value_name='태양광')
            
            df_long['연도'] = year
            # '월' 컬럼을 숫자로 변경 (e.g., "1월" -> 1)
            df_long['월'] = df_long['월'].str.replace('월', '').astype(int)
            
            all_solar_data.append(df_long)

        # 모든 연도 데이터를 하나의 DataFrame으로 합치기
        df_region_solar_monthly = pd.concat(all_solar_data, ignore_index=True)
        df_region_solar_monthly['광역지자체'] = df_region_solar_monthly['광역지자체'].str.strip()
        
        # [중요] 기존 코드를 위한 '연간' 합계 데이터 생성
        df_region_solar_annual = df_region_solar_monthly.groupby(
            ['연도', '광역지자체']
        )['태양광'].sum().reset_index()

        # ---------------------------------------------------
        
        # (신규) 한국 지도 경계선
        with open('data/korea_geojson.json', 'r', encoding='utf-8') as f:
            korea_geojson = json.load(f)

    except FileNotFoundError as e:
        st.error(f"필수 파일을 찾을 수 없습니다: {e.filename}. (data/ 폴더에 있는지 확인하세요)")
        st.stop()

    # ❗️ [수정 1] 날씨 예보 파일명 변경 및 KST 날짜 파싱
    try:
        # 'data/' 경로 제거, '날짜' 컬럼을 파싱하도록 parse_dates 추가
        df_today_forecast = pd.read_csv(
            "최종_날씨_예측_데이터.csv", 
            parse_dates=['날짜'] # KST 타임존이 포함된 datetime 객체로 읽어옴
        )
    except FileNotFoundError:
        st.warning("`최종_날씨_예측_데이터.csv` 파일이 없습니다. (GitHub Actions가 실행되었는지 확인하세요)")
        df_today_forecast = pd.DataFrame()

    # [수정] '연간' 데이터와 '월간' 데이터를 모두 반환
    return df_locations, df_generation, df_region_solar_annual, korea_geojson, df_today_forecast, df_region_solar_monthly


# -----------------------------------------------------------------
# 3. 날씨 데이터 처리 (공통)
# -----------------------------------------------------------------
def process_weather_data(df_today_forecast, df_locations):
    weather_data_available = False
    df_current_weather = pd.DataFrame()

    if not df_today_forecast.empty:
        try:
            # ❗️ [수정 2] 현재 시간을 타임존(KST)을 포함하여 가져옴
            now_kst = pd.Timestamp.now(tz='Asia/Seoul')
            
            # '날짜' 컬럼은 load_data에서 이미 타임존이 적용된 datetime 객체임
            
            # 타임존이 일치하므로 time_diff 계산이 올바르게 작동함
            df_today_forecast['time_diff'] = abs(df_today_forecast['날짜'] - now_kst)
            
            # 현재 시간과 가장 가까운 예보 데이터를 발전소별로 선택
            df_current_weather = df_today_forecast.loc[df_today_forecast.groupby('발전기명')['time_diff'].idxmin()]
            
            # ❗️ [수정] '발전사' 정보만 df_locations에서 가져옴 (좌표 중복 방지)
            # '최종_날씨_예측_데이터.csv'에 이미 '위도', '경도'가 있으므로 '발전사' 컬럼만 필요함
            location_info = df_locations[['발전기명', '발전사']]
            df_current_weather = pd.merge(df_current_weather, location_info, on='발전기명', how='left')
            
            weather_data_available = True
        except Exception as e:
            st.error(f"날씨 예보 CSV 처리 중 오류: {e}")
            
    return df_current_weather, weather_data_available

# -----------------------------------------------------------------
# 4. 헬퍼 함수 (지도 그리기용)
# -----------------------------------------------------------------

# ⬇️ --- [수정] 단위 변경 (MJ/m²) --- ⬇️
def create_weather_icon(row):
    # 새 CSV의 한글 컬럼명('기온', '일사량')으로 변경
    temp = row.get('기온', 0)
    insolation = row.get('일사량', 0) # 단위: MJ/m²

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
        <span style="color: #E67E22;">☀️ {insolation:.2f} MJ/m²</span><br>
        <span style="color: #C0392B;">🌡️ {temp:.1f} °C</span>
    </div>
    """
    return folium.features.DivIcon(
        icon_size=(100, 50), icon_anchor=(50, 25), html=html
    )
# ⬆️ --- [수정 완료] --- ⬆️

# (신규) 색칠 지도(Choropleth) 그리는 함수
def draw_choropleth_map(korea_geojson, map_data, legend_title):
    
    # (안정적인 OpenStreetMap 사용)
    m = folium.Map(
        location=[36.5, 127.5], 
        zoom_start=7, 
        tiles="OpenStreetMap"
    )

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

    # --- GeoJSON에 한글 이름도 추가 (툴팁용) ---
    data_dict = map_data.set_index('geojson_name')['태양광']
    
    # -----------------------------------------------------------------
    # ✨ [KeyError 오타 수정] 광역지_자체 -> 광역지자체
    # -----------------------------------------------------------------
    korean_name_dict = map_data.set_index('geojson_name')['광역지자체']
    # -----------------------------------------------------------------

    for feature in local_korea_geojson['features']:
        name = feature['properties']['NAME_1'] # (영어 이름)
        feature['properties']['태양광'] = float(data_dict.get(name, 0))
        # (JSON 오류 방지) str()로 감싸서 NaN 값도 안전하게 처리
        feature['properties']['KOREAN_NAME'] = str(korean_name_dict.get(name, 'N/A'))
    # --- ---

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

    # --- 툴팁이 KOREAN_NAME을 보도록 변경 ---
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

# (기존) 날씨 지도 그리는 함수
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
        st.warning(f"'{company_filter}'의 날씨 정보가 없습니다.")
        return m, None

    for idx, row in data_to_draw.iterrows():
        icon = create_weather_icon(row)
        folium.Marker(
            location=[row['위도'], row['경도']],
            icon=icon,
            tooltip=row['발전기명']
        ).add_to(m)

    return m, data_to_draw
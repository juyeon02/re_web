# web_utils.py
import streamlit as st
import pandas as pd
import folium
import json
import datetime
import copy
import glob
import os

# ---------------------------------------------------------------
# 1. 데이터 로드 (캐싱)
# ---------------------------------------------------------------
@st.cache_data
def load_data():
    try:
        # 위치 정보
        df_locations = pd.read_csv("data/locations_원본.csv")
        df_locations['발전기명'] = df_locations['발전기명'].str.strip()

        # 실제 발전량
        df_generation = pd.read_csv("data/발전량.csv")
        df_generation['날짜'] = pd.to_datetime(df_generation['날짜'], format='%Y.%m.%d')

        # ------------------------------------------
        # 지역별 연도·월 태양광 데이터 로드
        # ------------------------------------------
        path = "solar_analysis/"
        file_list = glob.glob(os.path.join(path, "*_solar_utf8.csv"))

        if not file_list:
            st.error("⚠ solar_analysis 폴더에서 태양광 파일을 찾을 수 없습니다.")
            st.stop()

        all_solar_data = []

        for file_path in file_list:
            filename = os.path.basename(file_path)

            try:
                year = int(filename.split('_')[0])
            except:
                continue

            df = pd.read_csv(file_path)
            df = df.rename(columns={'구분': '광역지자체'})
            df['광역지자체'] = df['광역지자체'].str.strip()

            month_cols = [f"{i}월" for i in range(1, 12 + 1)]

            for col in month_cols:
                if col in df.columns:
                    df[col] = (
                        df[col]
                        .astype(str)
                        .str.replace(",", "")
                        .replace("", "0")
                    )
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            df_long = df.melt(
                id_vars=['광역지자체'],
                value_vars=month_cols,
                var_name='월',
                value_name='태양광'
            )

            df_long['연도'] = year
            df_long['월'] = df_long['월'].str.replace("월", "").astype(int)

            all_solar_data.append(df_long)

        df_region_solar_monthly = pd.concat(all_solar_data, ignore_index=True)

        df_region_solar_annual = df_region_solar_monthly.groupby(
            ['연도', '광역지자체']
        )['태양광'].sum().reset_index()

        # ------------------------------------------
        # GeoJSON 로드
        # ------------------------------------------
        with open('data/korea_geojson.json', 'r', encoding='utf-8') as f:
            korea_geojson = json.load(f)

    except Exception as e:
        st.error(f"❌ 데이터 로드 오류: {e}")
        st.stop()

    # ------------------------------------------
    # 7일 예측 데이터 로드
    # ------------------------------------------
    try:
        df_today_forecast = pd.read_csv("최종_일별_발전량_예측.csv", parse_dates=['날짜'])

        if '날짜' in df_today_forecast.columns:
            # timezone 제거
            df_today_forecast['날짜'] = df_today_forecast['날짜'].dt.tz_localize(None)

    except FileNotFoundError:
        st.warning("⚠ '최종_일별_발전량_예측.csv' 파일 없음")
        df_today_forecast = pd.DataFrame()

    # ------------------------------------------
    # 과거 예측 데이터 (예측 vs 실제 비교용)
    # ------------------------------------------
    try:
        df_past_forecast = pd.read_csv(
            "data/최종_과거_예측_데이터.csv", parse_dates=['날짜']
        )
        if '날짜' in df_past_forecast.columns:
            df_past_forecast['날짜'] = df_past_forecast['날짜'].dt.tz_localize(None)

    except:
        st.warning("⚠ '최종_과거_예측_데이터.csv' 파일 없음")
        df_past_forecast = pd.DataFrame()

    # ------------------------------------------
    return (
        df_locations,
        df_generation,
        df_region_solar_annual,
        korea_geojson,
        df_today_forecast,
        df_region_solar_monthly,
        df_past_forecast
    )


# ---------------------------------------------------------------
# 2. 날씨 데이터 처리
# ---------------------------------------------------------------
def process_weather_data(df_today_forecast, df_locations):
    weather_data_available = False
    df_current_weather = pd.DataFrame()

    if not df_today_forecast.empty:
        try:
            today = pd.Timestamp.now().date()

            df_current_weather = df_today_forecast[
                df_today_forecast['날짜'].dt.date == today
            ].copy()

            if not df_current_weather.empty:
                df_current_weather = pd.merge(
                    df_current_weather,
                    df_locations[['발전기명', '발전사']],
                    on='발전기명',
                    how='left'
                )
                weather_data_available = True

        except Exception as e:
            st.error(f"❌ 날씨 데이터 처리 오류: {e}")

    return df_current_weather, weather_data_available


# ---------------------------------------------------------------
# 3. 발전소 라벨 디자인 (지도용)
# ---------------------------------------------------------------
def create_weather_icon(row):
    temp = row.get("평균기온", 0)
    predict = row.get("발전량_예측(MWh)", 0)

    html = f"""
    <div style="
        font-family: 'Noto Sans KR', sans-serif;
        background-color: rgba(255, 255, 255, 0.85);
        border-radius: 8px;
        padding: 6px 8px;
        border: 1px solid #666;
        box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
        text-align: center;
        width: 120px;">
        <b style="font-size:13px;">{row['발전기명']}</b><br>
        ⚡ {predict:.2f} MWh<br>
        🌡 {temp:.1f} °C
    </div>
    """

    return folium.DivIcon(
        html=html,
        icon_size=(120, 60),
        icon_anchor=(60, 30)
    )


# ---------------------------------------------------------------
# 4. 지역 Choropleth 지도
# ---------------------------------------------------------------
def draw_choropleth_map(korea_geojson, map_data, legend_title):
    m = folium.Map(location=[36.5, 127.5], zoom_start=7)

    if map_data.empty:
        st.warning("⚠ 지도에 표시할 데이터가 없습니다.")
        return m

    name_map = {
        '서울': 'Seoul', '부산': 'Busan', '대구': 'Daegu',
        '인천': 'Incheon', '광주': 'Gwangju', '대전': 'Daejeon',
        '울산': 'Ulsan', '세종': 'Sejong',
        '경기': 'Gyeonggi-do', '경기도': 'Gyeonggi-do',
        '강원': 'Gangwon-do', '강원특별자치도': 'Gangwon-do',
        '충북': 'Chungcheongbuk-do', '충청북도': 'Chungcheongbuk-do',
        '충남': 'Chungcheongnam-do', '충청남도': 'Chungcheongnam-do',
        '전북': 'Jeollabuk-do', '전라북도': 'Jeollabuk-do',
        '전남': 'Jeollanam-do', '전라남도': 'Jeollanam-do',
        '경북': 'Gyeongsangbuk-do', '경상북도': 'Gyeongsangbuk-do',
        '경남': 'Gyeongsangnam-do', '경상남도': 'Gyeongsangnam-do',
        '제주': 'Jeju', '제주특별자치도': 'Jeju'
    }

    df = map_data.copy()
    df['geojson_name'] = df['광역지자체'].map(name_map)

    data_dict = df.set_index('geojson_name')['태양광']

    gjson = copy.deepcopy(korea_geojson)
    for feature in gjson['features']:
        name = feature['properties']['NAME_1']
        feature['properties']['value'] = float(data_dict.get(name, 0))

    folium.Choropleth(
        geo_data=gjson,
        data=df,
        columns=['geojson_name', '태양광'],
        key_on="feature.properties.NAME_1",
        fill_color="YlOrRd",
        fill_opacity=0.8,
        line_opacity=0.2,
        legend_name=legend_title
    ).add_to(m)

    return m


# ---------------------------------------------------------------
# 5. 발전소별 날씨 지도
# ---------------------------------------------------------------
def draw_plant_weather_map(df_current_weather, available, company_filter):
    m = folium.Map(location=[36.5, 127.5], zoom_start=7)

    if not available:
        st.warning("⚠ 오늘 예측 데이터가 없습니다.")
        return m, None

    if company_filter != "전체":
        df_draw = df_current_weather[df_current_weather['발전사'] == company_filter]
    else:
        df_draw = df_current_weather

    if df_draw.empty:
        st.info("⚠ 해당 발전사 데이터 없음")
        return m, None

    for _, row in df_draw.iterrows():
        icon = create_weather_icon(row)
        folium.Marker(
            location=[row['위도'], row['경도']],
            tooltip=row['발전기명'],
            icon=icon
        ).add_to(m)

    return m, df_draw

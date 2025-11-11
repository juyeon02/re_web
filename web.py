import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import datetime
import json
import copy  # GeoJSON을 복사하기 위해 import

# -----------------------------------------------------------------
# 1. 웹페이지 설정
# -----------------------------------------------------------------
st.set_page_config(layout="wide")
st.title("☀️ 태양광 발전량 대시보드 ☀️")

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

        # (신규) 지역별 연도별 발전량 (UTF-8)
        df_region_solar = pd.read_csv("data/지역별_연도별_태양광.csv")
        df_region_solar['광역지자체'] = df_region_solar['광역지자체'].str.strip()

        # 쉼표(,) 제거 및 숫자로 변환
        df_region_solar['태양광'] = df_region_solar['태양광'].astype(str).str.replace(',', '')
        df_region_solar['태양광'] = pd.to_numeric(df_region_solar['태양광'])

        # (신규) 한국 지도 경계선
        with open('data/korea_geojson.json', 'r', encoding='utf-8') as f:
            korea_geojson = json.load(f)

    except FileNotFoundError as e:
        st.error(f"필수 파일을 찾을 수 없습니다: {e.filename}. (UTF-8로 저장했는지 확인하세요)")
        st.stop()

    # 날씨 예보 (파일이 없어도 앱이 멈추지 않도록)
    try:
        df_today_forecast = pd.read_csv("data/today_forecast_3hourly_final.csv")
        df_today_forecast['발전기명'] = df_today_forecast['발전기명'].str.strip()
    except FileNotFoundError:
        st.warning("`today_forecast_3hourly_final.csv` 파일이 없습니다. (날씨 정보가 표시되지 않습니다)")
        df_today_forecast = pd.DataFrame()

    return df_locations, df_generation, df_region_solar, korea_geojson, df_today_forecast


# 모든 데이터 로드
df_locations, df_generation, df_region_solar, korea_geojson, df_today_forecast = load_data()


# -----------------------------------------------------------------
# 3. 날씨 데이터 처리 (공통)
# -----------------------------------------------------------------
weather_data_available = False
df_current_weather = pd.DataFrame()

if not df_today_forecast.empty:
    try:
        now_kst = pd.to_datetime(datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=9)))).tz_localize(None)
        df_today_forecast['날짜'] = pd.to_datetime(df_today_forecast['날짜'])
        df_today_forecast['time_diff'] = abs(df_today_forecast['날짜'] - now_kst)
        df_current_weather = df_today_forecast.loc[df_today_forecast.groupby('발전기명')['time_diff'].idxmin()]
        df_current_weather = pd.merge(df_current_weather, df_locations, on='발전기명')
        weather_data_available = True
    except Exception as e:
        st.error(f"날씨 예보 CSV 처리 중 오류: {e}")

# -----------------------------------------------------------------
# 4. 헬퍼 함수 (지도 그리기용)
# -----------------------------------------------------------------

# (공통) 날씨 아이콘 그리는 함수


def create_weather_icon(row):
    temp = row.get('기온(°C)', 0)
    insolation = row.get('일사량(MJ/m²)', 0)

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
    return folium.features.DivIcon(
        icon_size=(100, 50), icon_anchor=(50, 25), html=html
    )

# (신규) 색칠 지도(Choropleth) 그리는 함수


def draw_choropleth_map(data, year):
    map_data = data[data['연도'] == year].copy()
    m = folium.Map(location=[36.5, 127.5], zoom_start=7, tiles="CartoDB positron")

    # 원본 GeoJSON이 훼손되지 않도록 깊은 복사 (중요)
    local_korea_geojson = copy.deepcopy(korea_geojson)

    if map_data.empty:
        st.warning(f"{year}년도 데이터가 없습니다.")
        return m

    # --- CSV(한글) -> GeoJSON(영어) 이름 매칭 ---
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

    map_data['geojson_name'] = map_data['광역지자체'].map(name_mapping)

    if map_data['geojson_name'].isnull().any():
        st.warning(f"일부 지역 이름이 지도와 매칭되지 않습니다: {map_data[map_data['geojson_name'].isnull()]['광역지자체'].unique()}")

    # Tooltip에 발전량 데이터를 표시하기 위해 GeoJSON에 데이터 추가
    data_dict = map_data.set_index('geojson_name')['태양광']
    for feature in local_korea_geojson['features']:
        name = feature['properties']['NAME_1']
        
        # [JSON 오류 수정] NumPy/pandas 타입을 표준 float으로 변환
        feature['properties']['태양광'] = float(data_dict.get(name, 0))

    # Choropleth 그리기 (c 변수에 저장)
    c = folium.Choropleth(
        geo_data=local_korea_geojson,  # 데이터가 추가된 local_korea_geojson 사용
        name="choropleth",
        data=map_data,
        columns=["geojson_name", "태양광"],
        key_on="feature.properties.NAME_1",
        fill_color="YlOrRd",
        fill_opacity=0.7,
        line_opacity=0.3,
        legend_name=f"{year}년 태양광 발전량",
        highlight=True,
    ).add_to(m)

    # 마우스 호버 시(Tooltip) 지역명과 발전량 표시
    folium.GeoJsonTooltip(
        fields=['NAME_1', '태양광'],
        aliases=['지역:', '발전량(MWh):'],
        localize=True,
        sticky=False,
        labels=True,
        style="""
            background-color: #F0EFEF;
            border: 2px solid black;
            border-radius: 3px;
            box-shadow: 3px;
        """,
        max_width=800,
    ).add_to(c.geojson)  # Choropleth 객체(c)의 geojson 속성에 Tooltip 추가

    return m

# (기존) 날씨 지도 그리는 함수


def draw_plant_weather_map(company_filter):
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


# -----------------------------------------------------------------
# 5. 사이드바 필터
# -----------------------------------------------------------------
st.sidebar.title("필터")

view_mode = st.sidebar.radio(
    "조회 모드 선택",
    ["종합 현황 (기본)", "지역별 상세 (색상 지도)", "발전소별 상세 (날씨 지도)"]
)

# -----------------------------------------------------------------
# 6. 메인 화면 (선택된 모드에 따라 다름)
# -----------------------------------------------------------------

if view_mode == "종합 현황 (기본)":
    st.header("종합 현황 (2023년 지역별 + 현재 발전소별)")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("2023년 지역별 태양광 발전량")
        m_choro = draw_choropleth_map(df_region_solar, 2023)
        st_folium(m_choro, width=600, height=500)

    with col2:
        st.subheader("발전소별 현재 날씨 예보 (전체)")
        m_weather, _ = draw_plant_weather_map('전체')
        st_folium(m_weather, width=600, height=500)

elif view_mode == "지역별 상세 (색상 지도)":
    st.header("지역별 상세 (색상 지도)")

    year_list = sorted(list(df_region_solar['연도'].unique()), reverse=True)
    selected_year = st.sidebar.selectbox(
        '연도를 선택하세요:',
        year_list
    )

    st.subheader(f"{selected_year}년 지역별 태양광 발전량")
    m_choro = draw_choropleth_map(df_region_solar, selected_year)
    st_folium(m_choro, width=1200, height=600)

elif view_mode == "발전소별 상세 (날씨 지도)":
    st.header("발전소별 상세 (날씨 지도 및 그래프)")

    company_list = ['전체'] + list(df_locations['발전사'].unique())
    company = st.sidebar.selectbox(
        '발전사를 선택하세요:',
        company_list
    )

    # -----------------------------------------------------------------
    # ✨ [KeyError 오류 수정] '주소' 대신 '위도', '경도'를 표시
    # -----------------------------------------------------------------
    if company != '전체':
        # 1. 해당 발전사의 발전소 목록 필터링
        # (오류 수정) '주소' 컬럼이 없을 수 있으므로 '위도', '경도'로 대체
        
        # 표시할 컬럼 목록 (발전기명은 필수)
        display_columns = ['발전기명']
        
        # 'locations_원본.csv' 파일에 '위도', '경도'가 있는지 확인
        if '위도' in df_locations.columns and '경도' in df_locations.columns:
            display_columns.extend(['위도', '경도'])
        
        # (만약 '주소' 컬럼이 있다면 '주소'를 추가 - 선택 사항)
        # if '주소' in df_locations.columns:
        #     display_columns.append('주소')

        plant_list_df = df_locations[df_locations['발전사'] == company][display_columns]
        plant_list_df = plant_list_df.reset_index(drop=True)
        plant_list_df.index += 1  # 목록 번호를 1부터 시작하게

        # 2. st.expander를 사용해 목록 표시
        with st.expander(f"✅ {company} 소속 발전소 목록 (총 {len(plant_list_df)}개)"):
            st.dataframe(plant_list_df, use_container_width=True)
    # -----------------------------------------------------------------
    # ✨ [수정] (여기까지)
    # -----------------------------------------------------------------

    m_weather, filtered_weather_data = draw_plant_weather_map(company)
    map_data = st_folium(m_weather, width=1200, height=500)

    st.header(f"📊 {company} 발전량 그래프")

    if company == '전체':
        merged_data = pd.merge(df_generation, df_locations, on='발전기명')
    else:
        plant_names = df_locations[df_locations['발전사'] == company]['발전기명'].tolist()
        merged_data = df_generation[df_generation['발전기명'].isin(plant_names)]

    clicked_plant_name = map_data.get('last_object_clicked_tooltip')
    graph_title_name = company

    if clicked_plant_name:
        merged_data = merged_data[merged_data['발전기명'] == clicked_plant_name]
        graph_title_name = clicked_plant_name
        st.subheader(f"➡️ {clicked_plant_name}")
    else:
        st.subheader("전체 발전소 합계")

    st.sidebar.title("기간 필터")

    # 원본 df_generation에 날짜 컬럼 생성
    df_generation['날짜'] = pd.to_datetime(df_generation['날짜'])
    df_generation['연도'] = df_generation['날짜'].dt.year
    df_generation['월'] = df_generation['날짜'].dt.month

    # 필터링된 merged_data에도 날짜 컬럼 생성 (이미 생성되었을 수 있음)
    if '연도' not in merged_data.columns:
        merged_data['날짜'] = pd.to_datetime(merged_data['날짜'])
        merged_data['연도'] = merged_data['날짜'].dt.year
        merged_data['월'] = merged_data['날짜'].dt.month

    # 연도 필터
    year_list_gen = ['전체'] + sorted(list(merged_data['연도'].unique()))
    selected_year_gen = st.sidebar.selectbox('연도를 선택하세요:', year_list_gen)

    # 연도에 따라 월 필터 생성
    if selected_year_gen == '전체':
        month_list = ['전체'] + sorted(list(merged_data['월'].unique()))
    else:
        merged_data = merged_data[merged_data['연도'] == selected_year_gen]
        month_list = ['전체'] + sorted(list(merged_data['월'].unique()))

    # 월 필터
    selected_month = st.sidebar.selectbox('월을 선택하세요:', month_list)

    if selected_month != '전체':
        merged_data = merged_data[merged_data['월'] == selected_month]

    # --- 동적 그래프 집계 로직 ---
    if merged_data.empty:
        st.warning("선택한 조건의 발전량 데이터가 없습니다.")
    else:
        # 필터 조건에 따라 집계 기준(agg_data)과 차트 X축(x_axis)을 동적으로 변경
        
        # 1. 연도와 월 모두 선택: '일별' 집계
        if selected_year_gen != '전체' and selected_month != '전체':
            agg_data = merged_data.groupby('날짜')['발전량(MWh)'].sum().reset_index()
            x_axis = '날짜'
            title_suffix = f"{selected_year_gen}년 {selected_month}월 (일별)"
            stat_prefix = "일"  # 통계 라벨

        # 2. 연도만 선택: '월별' 집계
        elif selected_year_gen != '전체' and selected_month == '전체':
            agg_data = merged_data.groupby('월')['발전량(MWh)'].sum().reset_index()
            x_axis = '월'
            title_suffix = f"{selected_year_gen}년 (월별)"
            stat_prefix = "월"  # 통계 라벨

        # 3. 연도 미선택 (월만 선택 or 둘 다 미선택): '연도별' 집계
        else:  # selected_year_gen == '전체'
            agg_data = merged_data.groupby('연도')['발전량(MWh)'].sum().reset_index()
            x_axis = '연도'
            stat_prefix = "연"  # 통계 라벨
            
            if selected_month != '전체':
                title_suffix = f"매년 {selected_month}월 (연도별)"
            else:
                title_suffix = "전체 기간 (연도별)"

        # --- 그래프 그리기 ---
        fig = px.line(agg_data, x=x_axis, y='발전량(MWh)',
                        title=f"{graph_title_name} {title_suffix} 발전량 합계 추이",
                        markers=True)

        # x축이 '월' 또는 '연도'일 경우, 소수점이 나오지 않도록 카테고리 타입으로 변경
        if x_axis in ['월', '연도']:
            fig.update_xaxes(type='category')

        st.plotly_chart(fig, use_container_width=True)

        # --- 요약 통계 표시 (동적 라벨 적용) ---
        st.subheader(f"📈 {stat_prefix}별 요약 통계")

        total_gen = agg_data['발전량(MWh)'].sum()
        avg_gen = agg_data['발전량(MWh)'].mean()
        max_gen = agg_data['발전량(MWh)'].max()
        min_gen = agg_data['발전량(MWh)'].min()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("총 발전량 (MWh)", f"{total_gen:,.2f}")
        col2.metric(f"{stat_prefix}평균 발전량 (MWh)", f"{avg_gen:,.2f}")
        col3.metric(f"{stat_prefix}최대 발전량 (MWh)", f"{max_gen:,.2f}")
        col4.metric(f"{stat_prefix}최소 발전량 (MWh)", f"{min_gen:,.2f}")

        # --- 상세 데이터 표 (동적 제목 적용) ---
        with st.expander(f"상세 데이터 표 보기 ({stat_prefix}별 합계)"):
            display_df = agg_data.copy()
            
            # '날짜' 컬럼일 경우 포맷 변경
            if x_axis == '날짜':
                display_df['날짜'] = display_df['날짜'].dt.strftime('%Y-%m-%d')
            
            display_df['발전량(MWh)'] = display_df['발전량(MWh)'].round(2)
            
            st.dataframe(
                display_df.sort_values(by=x_axis, ascending=False),
                use_container_width=True
            )
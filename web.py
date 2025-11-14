# web.py (메인 페이지 - 종합 현황)
import streamlit as st
from streamlit_folium import st_folium
import web_utils
import pandas as pd
import plotly.express as px

# --------------------------------------------------
# 0. 공통 CSS
# --------------------------------------------------
st.markdown("""
<style>

/* 전체 배경 */
.main {
    background-color: #fafafa;
}

/* 제목 스타일 */
h1, h2, h3, h4 {
    color: #004E66 !important;
    font-family: 'Noto Sans KR', sans-serif;
    font-weight: 700;
}

/* 카드 스타일 */
.card {
    background-color: #ffffff;
    padding: 20px;
    border-radius: 15px;
    box-shadow: 2px 2px 8px rgba(0,0,0,0.10);
    margin-bottom: 20px;
}

/* metric 카드 */
[data-testid="metric-container"] {
    background-color: white;
    padding: 15px;
    border-radius: 12px;
    box-shadow: 1px 1px 8px rgba(0,0,0,0.08);
    margin: 5px;
}

/* 사이드바 */
section[data-testid="stSidebar"] {
    background-color: #f0f4f5;
}

</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# 1. 웹페이지 설정 및 데이터 로드
# --------------------------------------------------
st.set_page_config(layout="wide")
st.title("☀️ 태양광 발전량 대시보드")

# load_data() ← 7개 값 반환하도록 수정된 버전 사용
(
    df_locations, 
    df_generation, 
    df_region_solar, 
    korea_geojson, 
    df_today_forecast, 
    df_region_solar_monthly,
    df_past_forecast
) = web_utils.load_data()

# 오늘 날씨 기반 발전량 예측 데이터 준비
df_current_weather, weather_data_available = web_utils.process_weather_data(
    df_today_forecast, df_locations
)

# --------------------------------------------------
# 2. 종합 현황
# --------------------------------------------------
st.header("종합 현황 (2023년 지역별 + 오늘 발전량 예측)")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📌 2023년 지역별 태양광 발전량")
    data_2023 = df_region_solar[df_region_solar['연도'] == 2023]
    map_choro = web_utils.draw_choropleth_map(
        korea_geojson, data_2023, "2023년 연간 태양광 발전량"
    )
    st_folium(map_choro, width="100%", height=500)

with col2:
    st.subheader("⚡ 발전소별 오늘 발전량 예측")
    map_weather, _ = web_utils.draw_plant_weather_map(
        df_current_weather, weather_data_available, "전체"
    )
    st_folium(map_weather, width="100%", height=500)

# --------------------------------------------------
# 3. 7일 발전량 예측
# --------------------------------------------------
st.divider()
st.header("📈 7일 발전량 예측")

if not df_today_forecast.empty:

    plant_list = sorted(df_today_forecast['발전기명'].unique())
    selected_plant = st.selectbox("발전소 선택", plant_list)

    df_plant = df_today_forecast[
        df_today_forecast["발전기명"] == selected_plant
    ].copy()

    st.subheader(f"📊 '{selected_plant}' 7일 요약")

    total_7d = df_plant['발전량_예측(MWh)'].sum()
    max_day = df_plant.loc[df_plant['발전량_예측(MWh)'].idxmax()]
    min_day = df_plant.loc[df_plant['발전량_예측(MWh)'].idxmin()]

    c1, c2, c3 = st.columns(3)
    c1.metric("7일 총 예측 발전량", f"{total_7d:,.2f} MWh")
    c2.metric(f"최대 발전일 ({max_day['날짜'].strftime('%m-%d')})", f"{max_day['발전량_예측(MWh)']:.2f} MWh")
    c3.metric(f"최저 발전일 ({min_day['날짜'].strftime('%m-%d')})", f"{min_day['발전량_예측(MWh)']:.2f} MWh")

    # 그래프
    df_plant['날짜_str'] = df_plant['날짜'].dt.strftime('%m-%d')
    fig = px.line(
        df_plant,
        x='날짜_str',
        y='발전량_예측(MWh)',
        title=f"{selected_plant} 7일간 발전량 예측",
        markers=True,
    )
    st.plotly_chart(fig, use_container_width=True)

    # 상세 데이터
    with st.expander("🔎 상세 데이터 보기"):
        df_show = df_plant.copy()
        df_show['날짜'] = df_show['날짜'].dt.strftime('%Y-%m-%d')
        st.dataframe(df_show.set_index('날짜'), use_container_width=True)

else:
    st.warning("⚠️ 예보 데이터를 불러올 수 없습니다.")

# --------------------------------------------------
# 4. 사이드 안내
# --------------------------------------------------
st.sidebar.info("📌 왼쪽 메뉴에서 지역별·발전소별 상세 페이지를 확인하세요.")

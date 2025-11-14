# pages/지역별.py
import streamlit as st
import web_utils
from streamlit_folium import st_folium
import plotly.express as px

st.set_page_config(layout="wide")
st.title("🌍 지역별 태양광 발전량 분석")

# 공통 CSS 적용
st.markdown("""
<style>
.block-container { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)

# --------------------------
# 데이터 로드
# --------------------------
(
    df_locations,
    df_generation,
    df_region_solar,
    korea_geojson,
    df_today_forecast,
    df_region_solar_monthly,
    df_past_forecast
) = web_utils.load_data()

# --------------------------
# 사이드바 필터
# --------------------------
st.sidebar.header("📌 필터")

year_list = sorted(df_region_solar['연도'].unique(), reverse=True)
selected_year = st.sidebar.selectbox("연도 선택", year_list)

month_list = ['전체'] + [f"{i}월" for i in range(1, 13)]
selected_month = st.sidebar.selectbox("월 선택", month_list)

# --------------------------
# 데이터 선택
# --------------------------
if selected_month == '전체':
    df_map = df_region_solar[df_region_solar['연도'] == selected_year]
    title = f"{selected_year}년 연간 발전량"
else:
    month_num = int(selected_month.replace("월", ""))
    df_map = df_region_solar_monthly[
        (df_region_solar_monthly['연도'] == selected_year)
        & (df_region_solar_monthly['월'] == month_num)
    ]
    title = f"{selected_year}년 {selected_month} 발전량"

st.subheader(title)

# --------------------------
# 지도 출력
# --------------------------
m = web_utils.draw_choropleth_map(korea_geojson, df_map, title)
st_folium(m, width='stretch', height=550)

# --------------------------
# 상세 데이터
# --------------------------
with st.expander("📊 상세 데이터 보기"):
    df_sorted = df_map.sort_values(by="태양광", ascending=False)

    fig = px.bar(
        df_sorted,
        x="광역지자체",
        y="태양광",
        title=f"{title} - 지역 비교",
        color="태양광",
        color_continuous_scale="YlOrRd"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        df_sorted[['광역지자체', '태양광']].round(2),
        height=350,
        use_container_width=True
    )

import streamlit as st
st.set_page_config(layout="wide")
import web_utils
from streamlit_folium import st_folium
import plotly.express as px

st.title("🌍 지역별 태양광 발전량 분석")
(
    df_locations,
    df_generation,
    df_region_solar,
    korea_geojson,
    df_today_forecast,
    df_region_solar_monthly,
    df_past_forecast,
) = web_utils.load_data()

st.sidebar.title("필터")

year_list = sorted(df_region_solar["연도"].unique(), reverse=True)
selected_year = st.sidebar.selectbox("연도 선택", year_list)

month_list = ["전체 (연간)"] + [f"{i}월" for i in range(1, 13)]
selected_month = st.sidebar.selectbox("월 선택", month_list)

# ---------------------------------------------------
# 데이터 준비
# ---------------------------------------------------
if selected_month == "전체 (연간)":
    map_data = df_region_solar[df_region_solar["연도"] == selected_year]
    legend = f"{selected_year}년 연간 태양광 발전량"
else:
    m = int(selected_month.replace("월", ""))
    map_data = df_region_solar_monthly[
        (df_region_solar_monthly["연도"] == selected_year)
        & (df_region_solar_monthly["월"] == m)
    ]
    legend = f"{selected_year}년 {selected_month} 태양광 발전량"

# 지도 출력
st.subheader(legend)

m_choro = web_utils.draw_choropleth_map(korea_geojson, map_data, legend)
st_folium(m_choro, width="100%", height=600)

# 상세 데이터
with st.expander("📊 상세 데이터 보기"):
    sorted_data = map_data.sort_values("태양광", ascending=False)

    fig = px.bar(
        sorted_data,
        x="광역지자체",
        y="태양광",
        title=legend,
        color="태양광",
        color_continuous_scale="YlOrRd",
    )
    st.plotly_chart(fig, width='stretch')

    st.dataframe(sorted_data, width='stretch')


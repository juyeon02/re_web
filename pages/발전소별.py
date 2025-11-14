# pages/발전소별.py
import streamlit as st
import web_utils
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("🏭 발전소별 상세 분석")

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

df_current_weather, available = web_utils.process_weather_data(df_today_forecast, df_locations)

# --------------------------
# 발전사 선택
# --------------------------
st.sidebar.header("📌 발전사 필터")
company_list = ['전체'] + sorted(df_locations['발전사'].unique())
selected_company = st.sidebar.selectbox("발전사 선택", company_list)

# 발전소 목록 출력
if selected_company != "전체":
    st.subheader(f"🔍 {selected_company} 소속 발전소 목록")
    df_plants = df_locations[df_locations['발전사'] == selected_company][['발전기명', '위도', '경도']]
    st.dataframe(df_plants, use_container_width=True)

# --------------------------
# 지도 출력
# --------------------------
st.subheader("📍 오늘 발전량 예측 지도")
m, filtered_weather = web_utils.draw_plant_weather_map(df_current_weather, available, selected_company)
map_click = st_folium(m, width='stretch', height=500)

# --------------------------
# 예측 vs 실제 발전량 비교
# --------------------------
clicked_plant = map_click.get("last_object_clicked_tooltip", None)

if clicked_plant:
    st.subheader(f"📊 {clicked_plant} — 실제 vs 예측 발전량 비교")
    plant_filter_list = [clicked_plant]
else:
    st.subheader(f"📊 {selected_company} — 실제 vs 예측 발전량 비교")
    if selected_company == "전체":
        plant_filter_list = df_locations['발전기명'].unique()
    else:
        plant_filter_list = df_locations[df_locations['발전사'] == selected_company]['발전기명']

# --------------------------
# 실제 발전량 데이터
# --------------------------
actual = df_generation[df_generation['발전기명'].isin(plant_filter_list)].copy()
actual["연도"] = actual["날짜"].dt.year
actual["월"] = actual["날짜"].dt.month

# --------------------------
# 사이드바 기간 필터
# --------------------------
st.sidebar.header("📅 기간 필터")

year_filter = ['전체'] + sorted(actual['연도'].unique())
selected_year = st.sidebar.selectbox("연도 선택", year_filter)

if selected_year != "전체":
    actual = actual[actual['연도'] == selected_year]

month_filter = ['전체'] + sorted(actual['월'].unique())
selected_month = st.sidebar.selectbox("월 선택", month_filter)

if selected_month != "전체":
    actual = actual[actual['월'] == selected_month]

# --------------------------
# 집계
# --------------------------
if selected_year != "전체" and selected_month != "전체":
    xcol = '날짜'
    agg_actual = actual.groupby('날짜')['발전량(MWh)'].sum().reset_index()
elif selected_year != "전체":
    xcol = '월'
    agg_actual = actual.groupby('월')['발전량(MWh)'].sum().reset_index()
else:
    xcol = '연도'
    agg_actual = actual.groupby('연도')['발전량(MWh)'].sum().reset_index()

agg_actual = agg_actual.rename(columns={'발전량(MWh)': '실제 발전량'})

# --------------------------
# 과거 예측 데이터 필터링
# --------------------------
forecast = df_past_forecast[df_past_forecast['발전기명'].isin(plant_filter_list)].copy()

if not forecast.empty:
    forecast["연도"] = forecast["날짜"].dt.year
    forecast["월"] = forecast["날짜"].dt.month

    if selected_year != "전체":
        forecast = forecast[forecast["연도"] == selected_year]
    if selected_month != "전체":
        forecast = forecast[forecast["월"] == selected_month]

    if xcol == "날짜":
        agg_fc = forecast.groupby('날짜')['발전량_예측(MWh)'].sum().reset_index()
    elif xcol == "월":
        agg_fc = forecast.groupby('월')['발전량_예측(MWh)'].sum().reset_index()
    else:
        agg_fc = forecast.groupby('연도')['발전량_예측(MWh)'].sum().reset_index()

    agg_fc = agg_fc.rename(columns={'발전량_예측(MWh)': '예측 발전량'})

    merged = pd.merge(agg_actual, agg_fc, on=xcol, how='outer')
else:
    merged = agg_actual.copy()

# --------------------------
# 그래프 출력
# --------------------------
df_melted = merged.melt(id_vars=[xcol], var_name="구분", value_name="발전량(MWh)")
fig = px.line(
    df_melted, x=xcol, y="발전량(MWh)",
    color="구분", markers=True,
    title=f"{selected_company if clicked_plant is None else clicked_plant} 발전량 비교"
)
st.plotly_chart(fig, use_container_width=True)

# --------------------------
# 데이터 테이블
# --------------------------
with st.expander("📄 상세 데이터"):
    st.dataframe(merged, use_container_width=True)

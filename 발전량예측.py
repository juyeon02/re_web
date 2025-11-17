import streamlit as st
st.set_page_config(page_title="발전량 예측", layout="wide")
from streamlit_folium import st_folium
import web_utils
import plotly.express as px
import pandas as pd

# ------------------ CSS ------------------
st.markdown("""
<style>
h1, h2, h3 {
    color:#004E66;
    font-weight:700;
}

.stSelectbox label {
    font-size:20px !important;
    font-weight:600 !important;
}

.st-emotion-cache-1kyxreq p {
    font-size:18px !important;
}
</style>
""", unsafe_allow_html=True)

st.title("☀️ 태양광 발전량 대시보드")

(
    df_locations, df_generation, df_region_solar,
    korea_geojson, df_today_forecast, df_region_solar_monthly,
    df_past_forecast
) = web_utils.load_data()

df_today, available = web_utils.process_weather_data(df_today_forecast, df_locations)


# 1. 오늘 발전량 지도
st.header("오늘 발전량 예측")
with st.expander("대시보드 설명 및 데이터 안내", expanded=False):
    st.markdown("""
        ### 지도 마커 색상 (발전사 구분)
        지도에 표시되는 마커는 발전소의 소속 발전사를 나타냅니다.
        
        | 발전사 | 색상 |
        | :--- | :--- |
        | **한국동서발전** | 🟦 파랑색 |
        | **한국남동발전** | 🟥 빨간색 |
        | **한국중부발전** | 🟩 초록색 |

        ### 마커 정보 (오늘 예측 데이터)
        마커를 클릭하거나 툴팁에 마우스를 올리면, AI 모델이 예측한 **오늘의 일별 발전량(MWh)**과 평균 기온 정보가 표시됩니다.

        ---
        **데이터 출처:** Open-Meteo API (기상), 자체 Random Forest 모델 (발전량 예측)
    """)


map_weather, _ = web_utils.draw_plant_weather_map(df_today, available, "전체")
st_folium(map_weather, width="100%", height=500)


# 7일 예측
st.divider()
st.header("📈 7일 발전량 예측")

if df_today_forecast.empty:
    st.warning("예측 데이터를 불러올 수 없습니다.")
else:
    plant_list = sorted(df_today_forecast["발전기명"].unique())
    selected = st.selectbox("발전소 선택", plant_list)

    df_p = df_today_forecast[df_today_forecast["발전기명"] == selected].copy()
    df_p["날짜_str"] = df_p["날짜"].dt.strftime("%m-%d")

    st.subheader(f"'{selected}' – 7일 예측 요약")
    c1, c2, c3 = st.columns(3)

    c1.metric("총 발전량", f"{df_p['발전량_예측(MWh)'].sum():,.2f} MWh")
    c2.metric("최대 발전", f"{df_p['발전량_예측(MWh)'].max():.2f} MWh")
    c3.metric("최소 발전", f"{df_p['발전량_예측(MWh)'].min():.2f} MWh")

    fig = px.line(
        df_p, x="날짜_str", y="발전량_예측(MWh)",
        markers=True, title=f"{selected} – 7일간 예측 추이"
    )
    st.plotly_chart(fig, width='stretch')

    with st.expander("상세 데이터 보기"):
        df_show = df_p.copy()
        df_show["날짜"] = df_show["날짜"].dt.strftime("%Y-%m-%d")
        st.dataframe(df_show.set_index("날짜"),width='stretch')

st.sidebar.info("왼쪽 메뉴에서 지역별 · 발전소별 상세 페이지를 확인하세요.")

# pages/1_🌍_지역별_상세.py
import streamlit as st
import utils  # (✨ 우리 헬퍼 함수 임포트)
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("🌍 지역별 상세 (색상 지도)")

# (✨ utils.py에서 데이터 로드)
df_locations, df_generation, df_region_solar, korea_geojson, df_today_forecast = utils.load_data()

# -----------------------------------------------------------------
# 6. 메인 화면 (지역별 상세)
# -----------------------------------------------------------------
year_list = sorted(list(df_region_solar['연도'].unique()), reverse=True)
selected_year = st.sidebar.selectbox(
    '연도를 선택하세요:',
    year_list
)

st.subheader(f"{selected_year}년 지역별 태양광 발전량")
# (✨ utils 함수 호출)
m_choro = utils.draw_choropleth_map(korea_geojson, df_region_solar, selected_year)
st_folium(m_choro, width=1200, height=600)
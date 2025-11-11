# web.py (메인 페이지 - 종합 현황)
import streamlit as st
from streamlit_folium import st_folium # ✨ [오류 수정] st_folium을 임포트
import utils  

# -----------------------------------------------------------------
# 1. 웹페이지 설정 및 데이터 로드
# -----------------------------------------------------------------
st.set_page_config(layout="wide")
st.title("☀️ 태양광 발전량 대시보드 ☀️")

# ( '월간' 데이터프레임도 받도록 변수 추가)
df_locations, df_generation, df_region_solar, korea_geojson, df_today_forecast, df_region_solar_monthly = utils.load_data()

# ( utils.py에서 날씨 데이터 처리)
df_current_weather, weather_data_available = utils.process_weather_data(df_today_forecast, df_locations)

# -----------------------------------------------------------------
# 6. 메인 화면 (종합 현황)
# -----------------------------------------------------------------
st.header("종합 현황 (2023년 지역별 + 현재 발전소별)")

col1, col2 = st.columns(2)

with col1:
    st.subheader("2023년 지역별 태양광 발전량 (연간)")
    
    # 2023년 '연간' 데이터만 필터링
    data_2023 = df_region_solar[df_region_solar['연도'] == 2023]
    
    # (지도json, 지도데이터, 범례제목) 전달
    m_choro = utils.draw_choropleth_map(korea_geojson, data_2023, "2023년 연간 태양광 발전량")
    
    # ✨ [오류 수정] st.folium -> st_folium
    st_folium(m_choro, width=600, height=500)

with col2:
    st.subheader("발전소별 현재 날씨 예보 (전체)")
    # ( utils 함수 호출)
    m_weather, _ = utils.draw_plant_weather_map(df_current_weather, weather_data_available, '전체')
    
    # ✨ [오류 수정] st.folium -> st_folium
    st_folium(m_weather, width=600, height=500)

st.sidebar.title(" ") # 사이드바 영역 확보
st.sidebar.info("다른 페이지에서 상세 현황을 확인하세요.")
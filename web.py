# web.py (메인 페이지 - 종합 현황)
import streamlit as st
from streamlit_folium import st_folium # ✨ [오류 수정] st_folium을 임포트
import web_utils  
import pandas as pd # 👈 [추가] 날짜 처리를 위해 pandas 임포트

# -----------------------------------------------------------------
# 1. 웹페이지 설정 및 데이터 로드
# -----------------------------------------------------------------
st.set_page_config(layout="wide")
st.title("☀️ 태양광 발전량 대시보드 ☀️")

# ( '월간' 데이터프래임도 받도록 변수 추가)
df_locations, df_generation, df_region_solar, korea_geojson, df_today_forecast, df_region_solar_monthly = web_utils.load_data()

# ( utils.py에서 날씨 데이터 처리) - '현재' 날씨 지도용
df_current_weather, weather_data_available = web_utils.process_weather_data(df_today_forecast, df_locations)

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
    m_choro = web_utils.draw_choropleth_map(korea_geojson, data_2023, "2023년 연간 태양광 발전량")
    
    # (경고 수정) use_container_width=True
    st_folium(m_choro, use_container_width=True, height=500)

with col2:
    st.subheader("발전소별 현재 날씨 예보 (전체)")
    # ( utils 함수 호출)
    m_weather, _ = web_utils.draw_plant_weather_map(df_current_weather, weather_data_available, '전체')
    
    # (경고 수정) use_container_width=True
    st_folium(m_weather, use_container_width=True, height=500)

# --- ⬇️ [신규] 시간대별 상세 예보 섹션 --- ⬇️
st.divider() # 구분선
st.header("🗓️ 시간대별 상세 예보 (7일)")

# df_today_forecast (전체 예보 데이터)가 정상적으로 로드되었는지 확인
if not df_today_forecast.empty:
    
    # 1. 발전소 선택 (사이드바가 아닌 메인 화면에)
    plant_list = sorted(df_today_forecast['발전기명'].unique())
    selected_plant = st.selectbox(
        '발전소를 선택하세요:',
        plant_list,
        key='main_plant_select' # 사이드바와 겹치지 않게 key 지정
    )
    
    # 2. 선택된 발전소의 데이터만 필터링
    df_plant_forecast = df_today_forecast[df_today_forecast['발전기명'] == selected_plant].copy()
    
    # 3. 날짜 선택 (YYYY-MM-DD 형식으로)
    date_list = df_plant_forecast['날짜'].dt.strftime('%Y-%m-%d').unique()
    selected_date_str = st.selectbox(
        '날짜를 선택하세요:',
        date_list,
        key='main_date_select'
    )
    
    # 4. 선택된 날짜의 데이터만 필터링
    df_display = df_plant_forecast[
        df_plant_forecast['날짜'].dt.strftime('%Y-%m-%d') == selected_date_str
    ].copy()

    # 5. 표(테이블) 표시
    if not df_display.empty:
        st.subheader(f"'{selected_plant}'의 {selected_date_str} 시간별 예보")
        
        # 표시할 컬럼 순서 지정
        display_columns = [
            '시간', '기온', '상대습도', '일사량', '풍속', 
            '운량(%)', '강수량', '적설량', '날씨코드'
        ]
        
        # '시간' 컬럼 생성 (HH:MM 형식)
        df_display['시간'] = df_display['날짜'].dt.strftime('%H:%M')
        
        # 원본 '날짜' 및 중복 컬럼 삭제
        df_display = df_display.drop(columns=['날짜', '발전기명', '위도', '경도'], errors='ignore')
        
        # 컬럼 순서 재정렬 (파일에 컬럼이 없어도 오류 방지)
        final_cols_to_show = [col for col in display_columns if col in df_display.columns]
        
        # '시간'을 인덱스로 설정하여 표시
        st.dataframe(
            df_display[final_cols_to_show].set_index('시간'),
            use_container_width=True
        )
    else:
        st.info("해당 날짜의 예보 데이터가 없습니다.")
        
else:
    st.warning("날씨 예보 데이터를 불러오지 못했습니다. (`최종_날씨_예측_데이터.csv` 파일 확인)")

# --- ⬆️ [신규 섹션 완료] --- ⬆️


# (기존 사이드바 코드)
st.sidebar.title(" ") # 사이드바 영역 확보
st.sidebar.info("다른 페이지에서 상세 현황을 확인하세요.")
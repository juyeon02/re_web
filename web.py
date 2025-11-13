# web.py (메인 페이지 - 종합 현황)
import streamlit as st
from streamlit_folium import st_folium
import web_utils
import pandas as pd
import plotly.express as px

# -----------------------------------------------------------------
# 1. 웹페이지 설정 및 데이터 로드
# -----------------------------------------------------------------
st.set_page_config(layout="wide")
st.title("☀️ 태양광 발전량 대시보드 ☀️")

# web_utils.load_data() 호출
df_locations, df_generation, df_region_solar, korea_geojson, df_today_forecast, df_region_solar_monthly = web_utils.load_data()

# '오늘 날짜'의 예측 데이터를 찾음
df_current_weather, weather_data_available = web_utils.process_weather_data(df_today_forecast, df_locations)

# -----------------------------------------------------------------
# 6. 메인 화면 (종합 현황)
# -----------------------------------------------------------------
st.header("종합 현황 (2023년 지역별 + 오늘 발전량 예측)")

col1, col2 = st.columns(2)

with col1:
    st.subheader("2023년 지역별 태양광 발전량 (연간)")
    data_2023 = df_region_solar[df_region_solar['연도'] == 2023]
    m_choro = web_utils.draw_choropleth_map(korea_geojson, data_2023, "2023년 연간 태양광 발전량")
    st_folium(m_choro, width='stretch', height=500)

with col2:
    st.subheader("발전소별 오늘 발전량 예측 (전체)")
    m_weather, _ = web_utils.draw_plant_weather_map(df_current_weather, weather_data_available, '전체')
    st_folium(m_weather, width='stretch', height=500)

# -----------------------------------------------------------------
# 7. "7일 발전량 예측" 섹션
# -----------------------------------------------------------------
st.divider() 
st.header("📈 7일 발전량 예측")

if not df_today_forecast.empty:
    
    plant_list = sorted(df_today_forecast['발전기명'].unique())
    selected_plant = st.selectbox(
        '발전소를 선택하세요:',
        plant_list,
        key='main_plant_select'
    )
    
    df_plant_forecast = df_today_forecast[
        df_today_forecast['발전기명'] == selected_plant
    ].copy()

    if not df_plant_forecast.empty:
        st.subheader(f"📊 '{selected_plant}' 7일 예측 요약")
        
        total_pred_7d = df_plant_forecast['발전량_예측(MWh)'].sum()
        max_pred_day = df_plant_forecast.loc[df_plant_forecast['발전량_예측(MWh)'].idxmax()]
        min_pred_day = df_plant_forecast.loc[df_plant_forecast['발전량_예측(MWh)'].idxmin()]

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("7일 총 예측 발전량", f"{total_pred_7d:,.2f} MWh")
        col_m2.metric(f"최대 발전일 ({max_pred_day['날짜'].strftime('%m-%d')})", 
                      f"{max_pred_day['발전량_예측(MWh)']:,.2f} MWh")
        col_m3.metric(f"최저 발전일 ({min_pred_day['날짜'].strftime('%m-%d')})", 
                      f"{min_pred_day['발전량_예측(MWh)']:,.2f} MWh")

        st.subheader("🗓️ 7일 예측 추이 (일별)")
        
        df_plant_forecast['날짜_str'] = df_plant_forecast['날짜'].dt.strftime('%m-%d')
        
        fig = px.line(
            df_plant_forecast, 
            x='날짜_str', 
            y='발전량_예측(MWh)',
            title=f"'{selected_plant}' 7일 발전량 예측 그래프",
            markers=True,
            labels={'날짜_str': '날짜', '발전량_예측(MWh)': '예측 발전량 (MWh)'}
        )
        fig.update_xaxes(type='category')
        st.plotly_chart(fig, width='stretch')

        with st.expander("날씨 + 예측 상세 데이터 보기 (7일)"):
            display_columns = [
                '날짜', '발전량_예측(MWh)', '일사량', '평균운량', '평균기온', 
                '총강수량', '일조시간', '평균풍속', '총적설량'
            ]
            rename_map = {
                '일사량': '일사량(MJ/m²)',
                '평균운량': '평균운량(%)',
                '평균기온': '평균기온(°C)',
                '총강수량': '총강수량(mm)',
                '일조시간': '일조시간(h)',
                '평균풍속': '평균풍속(m/s)',
                '총적설량': '총적설량(cm)'
            }
            df_display = df_plant_forecast[display_columns].copy()
            df_display['날짜'] = df_display['날짜'].dt.strftime('%Y-%m-%d')
            df_display.rename(columns=rename_map, inplace=True)
            
            st.dataframe(df_display.set_index('날짜'), width='stretch')
            
    else:
        st.info("해당 발전소의 예보 데이터가 없습니다.")
        
else:
    st.warning("일별 발전량 예보 데이터를 불러오지 못했습니다. (`최종_일별_발전량_예측.csv` 파일 확인)")

# (기존 사이드바 코드)
st.sidebar.title(" ") 
st.sidebar.info("다른 페이지에서 상세 현황을 확인하세요.")
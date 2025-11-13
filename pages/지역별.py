# pages/지역별.py
import streamlit as st
import web_utils  # (우리 헬퍼 함수 임포트)
from streamlit_folium import st_folium # ✨ [오류 수정] st_folium을 임포트
import plotly.express as px 

st.set_page_config(layout="wide")
st.title("🌍 지역별 상세 (색상 지도)")

# ( '월간' 데이터프레임도 받도록 변수 추가)
df_locations, df_generation, df_region_solar, korea_geojson, df_today_forecast, df_region_solar_monthly = web_utils.load_data()

# -----------------------------------------------------------------
# 6. 메인 화면 (지역별 상세)
# -----------------------------------------------------------------

st.sidebar.title("지도 필터")

# 연도 필터
year_list = sorted(list(df_region_solar['연도'].unique()), reverse=True)
selected_year = st.sidebar.selectbox(
    '연도를 선택하세요:',
    year_list
)

# '월' 필터 추가
month_list = ['전체 (연간 합계)'] + [f'{i}월' for i in range(1, 13)]
selected_month = st.sidebar.selectbox(
    '월을 선택하세요:',
    month_list
)

# --- 필터 조건에 따라 지도 데이터 준비 ---
if selected_month == '전체 (연간 합계)':
    # '연간' 데이터를 사용
    data_to_map = df_region_solar[df_region_solar['연도'] == selected_year]
    legend_title = f"{selected_year}년 연간 태양광 발전량"
    st.subheader(legend_title)
else:
    # '월간' 데이터를 사용
    month_num = int(selected_month.replace('월', '')) # '5월' -> 5
    data_to_map = df_region_solar_monthly[
        (df_region_solar_monthly['연도'] == selected_year) &
        (df_region_solar_monthly['월'] == month_num)
    ]
    legend_title = f"{selected_year}년 {selected_month} 태양광 발전량"
    st.subheader(legend_title)

# ( 동적으로 준비된 데이터와 제목으로 지도 그리기)
m_choro = web_utils.draw_choropleth_map(korea_geojson, data_to_map, legend_title)

# ✨ [오류/경고 수정] st.folium -> st_folium, width='stretch'
st_folium(m_choro, width='stretch', height=600)


# -----------------------------------------------------------------
#  막대 그래프 및 크기 조절된 표 추가
# -----------------------------------------------------------------
with st.expander("📊 상세 데이터 보기 (그래프 및 표)"):
    
    # 1. 데이터 정렬 (그래프와 표에서 공통 사용)
    data_sorted = data_to_map.sort_values(by='태양광', ascending=False)

    # 2. 막대 그래프 추가
    st.subheader("지역별 발전량 비교 (막대 그래프)")
    fig = px.bar(data_sorted, 
                 x='광역지자체', 
                 y='태양광',
                 title=f"{legend_title} 비교",
                 color='태양광', # 색상 스케일 적용
                 color_continuous_scale='YlOrRd') # 지도와 동일한 색상 테마
    fig.update_layout(xaxis_title="지역", yaxis_title="발전량(MWh)")
    
    # ✨ [경고 수정] use_container_width=True -> width='stretch'
    st.plotly_chart(fig, width='stretch')

    # 3. 상세 데이터 표 (높이 400px로 고정)
    st.subheader("상세 데이터 표")
    display_df = data_sorted[['광역지자체', '태양광']].copy()
    display_df['태양광'] = display_df['태양광'].round(2)
    
    st.dataframe(
        display_df,
        # ✨ [경고 수정] use_container_width=True -> width='stretch'
        width='stretch', 
        height=400  # <-- 표의 높이를 400px로 고정
    )
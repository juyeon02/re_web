# 실행 명령어(?) streamlit run web.py
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px

# 1. 웹페이지 제목
st.set_page_config(layout="wide")
st.title("태양광 발전량 대시보드")

# 파일 불러오기
df_locations = pd.read_csv("locations.csv", encoding='cp949')
df_generation = pd.read_csv("동서+중부(이상치제거).csv")

# '날짜' 컬럼을 datetime 객체로 변환
df_generation['날짜'] = pd.to_datetime(df_generation['날짜'])

# 날짜 필터링을 위해 '연도'와 '월' 컬럼을 미리 추가
df_generation['연도'] = df_generation['날짜'].dt.year
df_generation['월'] = df_generation['날짜'].dt.month

company_colors = {
    '한국동서발전': 'blue',
    '한국중부발전': 'green',
    '한국남동발전': 'red',
}

# 2. 사이드바에 필터 만들기
st.sidebar.title("필터")

# CSV 파일의 '발전사' 컬럼에서 고유한 이름들을 뽑아서 리스트로 만듭니다.
company_list = ['전체'] + list(df_locations['발전사'].unique())
company = st.sidebar.selectbox(
    '발전사를 선택하세요:',
    company_list
)


# 3. 선택된 발전사 데이터만 필터링하기
if company == '전체':
    filtered_locations = df_locations
else:
    filtered_locations = df_locations[df_locations['발전사'] == company]

# 3. 본문에 지도 띄우기 (서울 중심으로)
if company == '전체':
    map_center = [36.5, 127.5]
    zoom_level = 7
else:
    # 특정 발전사 선택 시, 해당 발전소들의 평균 위치
    map_center = [filtered_locations['위도'].mean(), filtered_locations['경도'].mean()]
    zoom_level = 7

m = folium.Map(location=map_center, zoom_start=zoom_level)

# 4. 필터링된 발전소들만 'for' 루프를 돌며 마커(핀)를 추가
for idx, row in filtered_locations.iterrows():
    marker_color = company_colors.get(row['발전사'], 'gray')

    folium.Marker(
        location=[row['위도'], row['경도']],
        popup=f"<strong>{row['발전기명']}</strong><br>{row['발전사']}",
        tooltip=row['발전기명'],
        icon=folium.Icon(color=marker_color)
    ).add_to(m)

map_data = st_folium(m, width=1200, height=500)


# 5. 그래프 그리기
st.header(f"{company} 발전량 그래프")

if company == '전체':
    merged_data = pd.merge(df_generation, df_locations, on='발전기명')
else:
    plant_names = filtered_locations['발전기명'].tolist()
    merged_data = df_generation[df_generation['발전기명'].isin(plant_names)]


# map_data에서 마지막으로 클릭한 마커의 툴팁('발전기명')을 가져옴
clicked_plant_name = map_data.get('last_object_clicked_tooltip')
graph_title_name = company

if clicked_plant_name:
    # 클릭된 발전소가 있으면, 데이터를 해당 발전소로 좁힘
    merged_data = merged_data[merged_data['발전기명'] == clicked_plant_name]
    # 그래프 제목도 클릭된 발전소 이름으로 변경
    graph_title_name = clicked_plant_name
    st.subheader(f"➡️ {clicked_plant_name}")
else:
    st.subheader("전체 발전소 합계")

# 사이드바에 연도/월 필터 추가
st.sidebar.title("기간 필터")

# 1차 필터링된 'merged_data'에서 연도/월 목록 가져오기
# .sort_values()를 추가하여 연도/월이 순서대로 나오게 함
year_list = ['전체'] + sorted(list(merged_data['연도'].unique()))
selected_year = st.sidebar.selectbox(
    '연도를 선택하세요:',
    year_list
)

# [동적 필터] 선택된 연도에 해당하는 월만 가져오기
if selected_year == '전체':
    month_list = ['전체'] + sorted(list(merged_data['월'].unique()))
else:
    # 'merged_data'에서 'selected_year'에 해당하는 데이터의 '월'만
    month_list = ['전체'] + sorted(list(merged_data[merged_data['연도'] == selected_year]['월'].unique()))

selected_month = st.sidebar.selectbox(
    '월을 선택하세요:',
    month_list
)
# --------------------------------------------------------


# 기간 필터 적용 (2차 필터링: 연도/월)
# 'selected_year'와 'selected_month'를 기준으로 'merged_data'를 다시 필터링
if selected_year != '전체':
    merged_data = merged_data[merged_data['연도'] == selected_year]

if selected_month != '전체':
    merged_data = merged_data[merged_data['월'] == selected_month]
# --------------------------------------------------------


# 6. 본문에 그래프 띄우기 (최종 필터링된 데이터 사용)
if merged_data.empty:
    st.warning("선택한 조건의 발전량 데이터가 없습니다.")
else:
    # 날짜별로 모든 발전소의 발전량을 합치기
    daily_gen = merged_data.groupby('날짜')['발전량(MWh)'].sum().reset_index()

    # [그래프 수정] 그래프 제목 동적으로 변경
    if selected_year == '전체' and selected_month == '전체':
        title_suffix = "전체 기간"
    elif selected_year != '전체' and selected_month == '전체':
        title_suffix = f"{selected_year}년"
    elif selected_year != '전체' and selected_month != '전체':
        title_suffix = f"{selected_year}년 {selected_month}월"
    else:  # (year='전체', month!='전체'인 경우)
        title_suffix = f"매년 {selected_month}월"

    fig = px.line(daily_gen, x='날짜', y='발전량(MWh)',
                  title=f"{company} {title_suffix} 발전량 합계 추이",
                  markers=True)

    st.plotly_chart(fig)

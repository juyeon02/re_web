# pages/2_🏭_발전소별_상세.py
import streamlit as st
import utils  # (✨ 우리 헬퍼 함수 임포트)
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("🏭 발전소별 상세 (날씨 지도 및 그래프)")

# (✨ utils.py에서 데이터 로드)
df_locations, df_generation, df_region_solar, korea_geojson, df_today_forecast = utils.load_data()

# (✨ utils.py에서 날씨 데이터 처리)
df_current_weather, weather_data_available = utils.process_weather_data(df_today_forecast, df_locations)

# -----------------------------------------------------------------
# 6. 메인 화면 (발전소별 상세)
# -----------------------------------------------------------------
st.header("발전소별 상세 (날씨 지도 및 그래프)")

company_list = ['전체'] + list(df_locations['발전사'].unique())
company = st.sidebar.selectbox(
    '발전사를 선택하세요:',
    company_list
)

# (✨ [KeyError 오류 수정] 부분 반영)
if company != '전체':
    display_columns = ['발전기명']
    if '위도' in df_locations.columns and '경도' in df_locations.columns:
        display_columns.extend(['위도', '경도'])

    plant_list_df = df_locations[df_locations['발전사'] == company][display_columns]
    plant_list_df = plant_list_df.reset_index(drop=True)
    plant_list_df.index += 1

    with st.expander(f"✅ {company} 소속 발전소 목록 (총 {len(plant_list_df)}개)"):
        st.dataframe(plant_list_df, use_container_width=True)

# (✨ utils 함수 호출)
m_weather, filtered_weather_data = utils.draw_plant_weather_map(df_current_weather, weather_data_available, company)
map_data = st_folium(m_weather, width=1200, height=500)

st.header(f"📊 {company} 발전량 그래프")

if company == '전체':
    merged_data = pd.merge(df_generation, df_locations, on='발전기명')
else:
    plant_names = df_locations[df_locations['발전사'] == company]['발전기명'].tolist()
    merged_data = df_generation[df_generation['발전기명'].isin(plant_names)]

clicked_plant_name = map_data.get('last_object_clicked_tooltip')
graph_title_name = company

if clicked_plant_name:
    merged_data = merged_data[merged_data['발전기명'] == clicked_plant_name]
    graph_title_name = clicked_plant_name
    st.subheader(f"➡️ {clicked_plant_name}")
else:
    st.subheader("전체 발전소 합계")

st.sidebar.title("기간 필터")

# (이후 로직은 원본과 동일)
df_generation['날짜'] = pd.to_datetime(df_generation['날짜'])
df_generation['연도'] = df_generation['날짜'].dt.year
df_generation['월'] = df_generation['날짜'].dt.month

if '연도' not in merged_data.columns:
    merged_data['날짜'] = pd.to_datetime(merged_data['날짜'])
    merged_data['연도'] = merged_data['날짜'].dt.year
    merged_data['월'] = merged_data['날짜'].dt.month

year_list_gen = ['전체'] + sorted(list(merged_data['연도'].unique()))
selected_year_gen = st.sidebar.selectbox('연도를 선택하세요:', year_list_gen)

if selected_year_gen == '전체':
    month_list = ['전체'] + sorted(list(merged_data['월'].unique()))
else:
    merged_data = merged_data[merged_data['연도'] == selected_year_gen]
    month_list = ['전체'] + sorted(list(merged_data['월'].unique()))

selected_month = st.sidebar.selectbox('월을 선택하세요:', month_list)

if selected_month != '전체':
    merged_data = merged_data[merged_data['월'] == selected_month]

if merged_data.empty:
    st.warning("선택한 조건의 발전량 데이터가 없습니다.")
else:
    if selected_year_gen != '전체' and selected_month != '전체':
        agg_data = merged_data.groupby('날짜')['발전량(MWh)'].sum().reset_index()
        x_axis = '날짜'
        title_suffix = f"{selected_year_gen}년 {selected_month}월 (일별)"
        stat_prefix = "일"
    elif selected_year_gen != '전체' and selected_month == '전체':
        agg_data = merged_data.groupby('월')['발전량(MWh)'].sum().reset_index()
        x_axis = '월'
        title_suffix = f"{selected_year_gen}년 (월별)"
        stat_prefix = "월"
    else:
        agg_data = merged_data.groupby('연도')['발전량(MWh)'].sum().reset_index()
        x_axis = '연도'
        stat_prefix = "연"
        if selected_month != '전체':
            title_suffix = f"매년 {selected_month}월 (연도별)"
        else:
            title_suffix = "전체 기간 (연도별)"

    fig = px.line(agg_data, x=x_axis, y='발전량(MWh)',
                    title=f"{graph_title_name} {title_suffix} 발전량 합계 추이",
                    markers=True)
    if x_axis in ['월', '연도']:
        fig.update_xaxes(type='category')
    st.plotly_chart(fig, use_container_width=True)

    st.subheader(f"📈 {stat_prefix}별 요약 통계")
    total_gen = agg_data['발전량(MWh)'].sum()
    avg_gen = agg_data['발전량(MWh)'].mean()
    max_gen = agg_data['발전량(MWh)'].max()
    min_gen = agg_data['발전량(MWh)'].min()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("총 발전량 (MWh)", f"{total_gen:,.2f}")
    col2.metric(f"{stat_prefix}평균 발전량 (MWh)", f"{avg_gen:,.2f}")
    col3.metric(f"{stat_prefix}최대 발전량 (MWh)", f"{max_gen:,.2f}")
    col4.metric(f"{stat_prefix}최소 발전량 (MWh)", f"{min_gen:,.2f}")

    with st.expander(f"상세 데이터 표 보기 ({stat_prefix}별 합계)"):
        display_df = agg_data.copy()
        if x_axis == '날짜':
            display_df['날짜'] = display_df['날짜'].dt.strftime('%Y-%m-%d')
        display_df['발전량(MWh)'] = display_df['발전량(MWh)'].round(2)
        st.dataframe(display_df.sort_values(by=x_axis, ascending=False), use_container_width=True)
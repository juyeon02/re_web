# pages/발전소별.py
import streamlit as st
import web_utils
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("🏭 발전소별 상세 (날씨 지도 및 그래프)")

df_locations, df_generation, df_region_solar, korea_geojson, df_today_forecast, df_region_solar_monthly, df_past_forecast = web_utils.load_data()
df_current_weather, weather_data_available = web_utils.process_weather_data(df_today_forecast, df_locations)

# -----------------------------------------------------------------
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
# -----------------------------------------------------------------

st.header("발전소별 상세 (날씨 지도 및 그래프)")

company_list = ['전체'] + list(df_locations['발전사'].unique())
company = st.sidebar.selectbox(
    '발전사를 선택하세요:',
    company_list
)

if company != '전체':
    display_columns = ['발전기명']
    if '위도' in df_locations.columns and '경도' in df_locations.columns:
        display_columns.extend(['위도', '경도'])

    plant_list_df = df_locations[df_locations['발전사'] == company][display_columns]
    plant_list_df = plant_list_df.reset_index(drop=True)
    plant_list_df.index += 1

    with st.expander(f"✅ {company} 소속 발전소 목록 (총 {len(plant_list_df)}개)"):
        st.dataframe(plant_list_df, width='stretch')

m_weather, filtered_weather_data = web_utils.draw_plant_weather_map(df_current_weather, weather_data_available, company)
map_data = st_folium(m_weather, width='stretch', height=500)
st.subheader("📍 오늘 발전량 예측 상세 (지도 데이터)")
if weather_data_available and (filtered_weather_data is not None) and (not filtered_weather_data.empty):
    display_columns = ['날짜', '발전기명', '발전량_예측(MWh)', '일사량', '평균운량', '평균기온', '총강수량', '일조시간', '평균풍속', '총적설량']
    rename_map = {'일사량': '일사량(MJ/m²)', '평균운량': '평균운량(%)', '평균기온': '평균기온(°C)', '총강수량': '총강수량(mm)', '일조시간': '일조시간(h)', '평균풍속': '평균풍속(m/s)', '총적설량': '총적설량(cm)'}
    available_cols = [col for col in display_columns if col in filtered_weather_data.columns]
    df_display_weather = filtered_weather_data[available_cols].copy()
    df_display_weather['날짜'] = df_display_weather['날짜'].dt.strftime('%Y-%m-%d')
    df_display_weather.rename(columns=rename_map, inplace=True)
    st.dataframe(df_display_weather.set_index('날짜'), width='stretch')
elif weather_data_available and (filtered_weather_data is None or filtered_weather_data.empty):
    st.info(f"'{company}' 발전사에는 오늘 예측 데이터가 없습니다.")
else:
    st.warning("일별 발전량 예보 데이터를 불러오지 못했습니다.")

st.divider()

st.header(f"📊 {company} 발전량 비교 (예측 vs 실제)")

# 1. '실제' 발전량 데이터 
if company == '전체':
    actual_data_base = pd.merge(df_generation, df_locations, on='발전기명')
else:
    plant_names = df_locations[df_locations['발전사'] == company]['발전기명'].tolist()
    actual_data_base = df_generation[df_generation['발전기명'].isin(plant_names)]

# 2."과거 예측" 발전량 데이터
if company == '전체':
    past_forecast_data_base = df_past_forecast.copy()
else:
    plant_names = df_locations[df_locations['발전사'] == company]['발전기명'].tolist()
    past_forecast_data_base = df_past_forecast[df_past_forecast['발전기명'].isin(plant_names)]

# 3. 지도 클릭
clicked_plant_name = map_data.get('last_object_clicked_tooltip')
graph_title_name = company

if clicked_plant_name:
    actual_data_base = actual_data_base[actual_data_base['발전기명'] == clicked_plant_name]
    past_forecast_data_base = past_forecast_data_base[past_forecast_data_base['발전기명'] == clicked_plant_name]
    graph_title_name = clicked_plant_name
    st.subheader(f"➡️ {clicked_plant_name}")
else:
    st.subheader("전체 발전소 합계")

# 4. 사이드바 기간 필터
st.sidebar.title("기간 필터")
actual_data_base['연도'] = actual_data_base['날짜'].dt.year
actual_data_base['월'] = actual_data_base['날짜'].dt.month

year_list_gen = ['전체'] + sorted(list(actual_data_base['연도'].unique()))
selected_year_gen = st.sidebar.selectbox('연도를 선택하세요:', year_list_gen)

if selected_year_gen == '전체':
    month_list = ['전체'] + sorted(list(actual_data_base['월'].unique()))
    filtered_actual = actual_data_base
else:
    filtered_actual = actual_data_base[actual_data_base['연도'] == selected_year_gen]
    month_list = ['전체'] + sorted(list(filtered_actual['월'].unique()))

selected_month = st.sidebar.selectbox('월을 선택하세요:', month_list)

if selected_month != '전체':
    filtered_actual = filtered_actual[filtered_actual['월'] == selected_month]

if not past_forecast_data_base.empty:
    past_forecast_data_base['연도'] = past_forecast_data_base['날짜'].dt.year
    past_forecast_data_base['월'] = past_forecast_data_base['날짜'].dt.month
    
    if selected_year_gen != '전체':
        past_forecast_data_base = past_forecast_data_base[past_forecast_data_base['연도'] == selected_year_gen]
    if selected_month != '전체':
        past_forecast_data_base = past_forecast_data_base[past_forecast_data_base['월'] == selected_month]
else:
    st.info("해당 기간의 '과거 예측' 데이터가 없습니다.")


if filtered_actual.empty:
    st.warning("선택한 조건의 '실제' 발전량 데이터가 없습니다.")
else:
    # 6. '실제' 데이터 집계
    if selected_year_gen != '전체' and selected_month != '전체':
        agg_actual = filtered_actual.groupby('날짜')['발전량(MWh)'].sum().reset_index()
        x_axis = '날짜'
        title_suffix = f"{selected_year_gen}년 {selected_month}월 (일별)"
    elif selected_year_gen != '전체' and selected_month == '전체':
        agg_actual = filtered_actual.groupby('월')['발전량(MWh)'].sum().reset_index()
        x_axis = '월'
        title_suffix = f"{selected_year_gen}년 (월별)"
    else:
        agg_actual = filtered_actual.groupby('연도')['발전량(MWh)'].sum().reset_index()
        x_axis = '연도'
        title_suffix = "전체 기간 (연도별)"
    
    agg_actual = agg_actual.rename(columns={'발전량(MWh)': '실제 발전량'})

    # 7"과거 예측" 데이터 집계
    if not past_forecast_data_base.empty:
        if x_axis == '날짜':
            agg_forecast = past_forecast_data_base.groupby('날짜')['발전량_예측(MWh)'].sum().reset_index()
        elif x_axis == '월':
            agg_forecast = past_forecast_data_base.groupby('월')['발전량_예측(MWh)'].sum().reset_index()
        else: # x_axis == '연도'
            agg_forecast = past_forecast_data_base.groupby('연도')['발전량_예측(MWh)'].sum().reset_index()
            
        agg_forecast = agg_forecast.rename(columns={'발전량_예측(MWh)': '예측 발전량'})

        # 8. '실제'와 '예측' 데이터 병합
        merged_df = pd.merge(agg_actual, agg_forecast, on=x_axis, how='outer')
        
    else: # 예측 데이터가 없는 경우 (과거)
        merged_df = agg_actual
        
    # 9. 2개 선을 그리기 위해 데이터 프레임 재구성
    if '예측 발전량' in merged_df.columns:
        df_melted = merged_df.melt(id_vars=[x_axis], 
                                   value_vars=['실제 발전량', '예측 발전량'], 
                                   var_name='데이터 종류', 
                                   value_name='발전량(MWh)')
    else:
        df_melted = merged_df.melt(id_vars=[x_axis], 
                                   value_vars=['실제 발전량'], 
                                   var_name='데이터 종류', 
                                   value_name='발전량(MWh)')

    # 10. 2개 선 그래프 그리기
    fig = px.line(
        df_melted, 
        x=x_axis, 
        y='발전량(MWh)',
        color='데이터 종류', 
        title=f"{graph_title_name} {title_suffix} 발전량 비교",
        markers=True,
        color_discrete_map={'실제 발전량': 'blue', '예측 발전량': 'red'} # 색상 지정
    )
    if x_axis in ['월', '연도']:
        fig.update_xaxes(type='category')
    
    st.plotly_chart(fig, width='stretch')

    # 11. 요약 통계
    st.subheader("📈 '실제' 발전량 요약 통계")
    
    total_gen = agg_actual['실제 발전량'].sum()
    avg_gen = agg_actual['실제 발전량'].mean()
    max_gen = agg_actual['실제 발전량'].max()
    min_gen = agg_actual['실제 발전량'].min()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("총 발전량 (MWh)", f"{total_gen:,.2f}")
    col2.metric("평균 발전량 (MWh)", f"{avg_gen:,.2f}")
    col3.metric("최대 발전량 (MWh)", f"{max_gen:,.2f}")
    col4.metric("최소 발전량 (MWh)", f"{min_gen:,.2f}")

    with st.expander("상세 데이터 표 보기 (실제 vs 예측)"):
        display_df = merged_df.copy()
        if x_axis == '날짜':
            display_df['날짜'] = display_df['날짜'].dt.strftime('%Y-%m-%d')
        
        for col in ['실제 발전량', '예측 발전량']:
            if col in display_df.columns:
                 display_df[col] = display_df[col].round(2)
                 
        st.dataframe(
            display_df.sort_values(by=x_axis, ascending=False).set_index(x_axis),
            width='stretch'
        )
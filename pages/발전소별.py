# pages/발전소별.py
import streamlit as st
import web_utils
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("🏭 발전소별 상세 (날씨 지도 및 그래프)")

# 데이터 로드
df_locations, df_generation, df_region_solar, korea_geojson, df_today_forecast, df_region_solar_monthly, df_past_forecast = web_utils.load_data()

# 오늘 예보 데이터
df_current_weather, weather_data_available = web_utils.process_weather_data(
    df_today_forecast, df_locations
)

# --- 발전사 선택 ---
company_list = ['전체'] + list(df_locations['발전사'].unique())
company = st.sidebar.selectbox('발전사를 선택하세요:', company_list)

# --- 발전사별 발전소 목록 표시 ---
if company != '전체':
    display_cols = ['발전기명']
    if '위도' in df_locations.columns and '경도' in df_locations.columns:
        display_cols.extend(['위도', '경도'])

    list_df = df_locations[df_locations['발전사'] == company][display_cols]
    list_df = list_df.reset_index(drop=True)
    list_df.index += 1

    with st.expander(f"📍 {company} 소속 발전소 목록 ({len(list_df)}개)"):
        st.dataframe(list_df, width='stretch')

# --- 발전소별 지도 (3개 발전사 색상 반영) ---
st.subheader("🌤 오늘의 발전소별 발전량 예측 지도")

map_weather, filtered_weather = web_utils.draw_plant_weather_map(
    df_current_weather, weather_data_available, company
)

map_data = st_folium(map_weather, width='stretch', height=500)

# --- 지도 선택된 발전소 표시 ---
st.subheader("📌 오늘 발전량 예측 상세")

if weather_data_available and filtered_weather is not None and not filtered_weather.empty:
    display_cols = [
        '날짜','발전기명','발전량_예측(MWh)','일사량','평균운량',
        '평균기온','총강수량','일조시간','평균풍속','총적설량'
    ]

    rename_map = {
        '일사량': '일사량(MJ/m²)','평균운량': '평균운량(%)','평균기온': '평균기온(°C)',
        '총강수량':'총강수량(mm)','일조시간':'일조시간(h)',
        '평균풍속':'평균풍속(m/s)','총적설량':'총적설량(cm)'
    }

    df_display = filtered_weather[display_cols].copy()
    df_display['날짜'] = df_display['날짜'].dt.strftime('%Y-%m-%d')
    df_display.rename(columns=rename_map, inplace=True)

    st.dataframe(df_display.set_index('날짜'), width='stretch')

else:
    st.info("해당 발전사의 예측 데이터가 없습니다.")

# -----------------------------------------------------------
#  📊 예측 vs 실제 발전량 비교
# -----------------------------------------------------------

st.divider()
st.header(f"📊 {company} 예측 vs 실제 발전량 비교")

# 실제 데이터 준비
if company == '전체':
    actual_base = pd.merge(df_generation, df_locations, on='발전기명')
else:
    plants = df_locations[df_locations['발전사'] == company]['발전기명'].tolist()
    actual_base = df_generation[df_generation['발전기명'].isin(plants)]

# 과거 예측 데이터
if company == '전체':
    forecast_base = df_past_forecast.copy()
else:
    forecast_base = df_past_forecast[
        df_past_forecast['발전기명'].isin(plants)
    ]

# 클릭된 발전소가 있다면 특정 발전소만 보기
clicked_plant = map_data.get('last_object_clicked_tooltip')
title_name = company

if clicked_plant:
    actual_base = actual_base[actual_base['발전기명'] == clicked_plant]
    forecast_base = forecast_base[forecast_base['발전기명'] == clicked_plant]
    title_name = clicked_plant
    st.subheader(f"➡️ {clicked_plant}")

# ---------------- 기간 필터 -----------------

st.sidebar.title("기간 필터")
actual_base['연도'] = actual_base['날짜'].dt.year
actual_base['월'] = actual_base['날짜'].dt.month

year_list = ['전체'] + sorted(actual_base['연도'].unique())
sel_year = st.sidebar.selectbox('연도를 선택하세요:', year_list)

if sel_year == '전체':
    month_list = ['전체'] + sorted(actual_base['월'].unique())
    filtered_actual = actual_base
else:
    filtered_actual = actual_base[actual_base['연도'] == sel_year]
    month_list = ['전체'] + sorted(filtered_actual['월'].unique())

sel_month = st.sidebar.selectbox('월을 선택하세요:', month_list)

if sel_month != '전체':
    filtered_actual = filtered_actual[filtered_actual['월'] == sel_month]

# ---------------- 실제 발전량 집계 -----------------

if filtered_actual.empty:
    st.warning("해당 기간의 실제 발전량 데이터가 없습니다.")
else:
    if sel_year != '전체' and sel_month != '전체':
        agg_actual = filtered_actual.groupby('날짜')['발전량(MWh)'].sum().reset_index()
        x_key = '날짜'
        suffix = f"{sel_year}년 {sel_month}월 (일별)"
    elif sel_year != '전체' and sel_month == '전체':
        agg_actual = filtered_actual.groupby('월')['발전량(MWh)'].sum().reset_index()
        x_key = '월'
        suffix = f"{sel_year}년 (월별)"
    else:
        agg_actual = filtered_actual.groupby('연도')['발전량(MWh)'].sum().reset_index()
        x_key = '연도'
        suffix = "전체 기간 (연도별)"

    agg_actual = agg_actual.rename(columns={'발전량(MWh)': '실제 발전량'})

    # ---------------- 과거 예측 발전량 -----------------

    if not forecast_base.empty:
        forecast_base['연도'] = forecast_base['날짜'].dt.year
        forecast_base['월'] = forecast_base['날짜'].dt.month

        if sel_year != '전체':
            forecast_base = forecast_base[forecast_base['연도'] == sel_year]
        if sel_month != '전체':
            forecast_base = forecast_base[forecast_base['월'] == sel_month]

        if x_key == '날짜':
            agg_forecast = forecast_base.groupby('날짜')['발전량_예측(MWh)'].sum().reset_index()
        elif x_key == '월':
            agg_forecast = forecast_base.groupby('월')['발전량_예측(MWh)'].sum().reset_index()
        else:
            agg_forecast = forecast_base.groupby('연도')['발전량_예측(MWh)'].sum().reset_index()

        agg_forecast = agg_forecast.rename(columns={'발전량_예측(MWh)': '예측 발전량'})
        merged_df = pd.merge(agg_actual, agg_forecast, on=x_key, how='outer')
    else:
        merged_df = agg_actual.copy()

    # ---------------- 그래프 -----------------

    melt_df = merged_df.melt(
        id_vars=[x_key],
        value_vars=[col for col in ['실제 발전량', '예측 발전량'] if col in merged_df.columns],
        var_name='구분',
        value_name='발전량(MWh)'
    )

    fig = px.line(
        melt_df,
        x=x_key,
        y='발전량(MWh)',
        color='구분',
        title=f"{title_name} {suffix} 발전량 비교",
        markers=True,
        color_discrete_map={'실제 발전량': 'blue', '예측 발전량': 'red'}
    )

    if x_key in ['월', '연도']:
        fig.update_xaxes(type='category')

    st.plotly_chart(fig, use_container_width=True)

    # ---------------- 요약 -----------------

    st.subheader("📈 요약 정보 (실제 발전량)")
    total = agg_actual['실제 발전량'].sum()
    avg = agg_actual['실제 발전량'].mean()
    mx = agg_actual['실제 발전량'].max()
    mn = agg_actual['실제 발전량'].min()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 발전량", f"{total:,.2f} MWh")
    c2.metric("평균", f"{avg:,.2f} MWh")
    c3.metric("최대", f"{mx:,.2f} MWh")
    c4.metric("최소", f"{mn:,.2f} MWh")

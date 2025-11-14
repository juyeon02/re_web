import streamlit as st
import pandas as pd
import folium
import json
import copy
import glob
import os
from datetime import date 
from retry_requests import retry 
import requests_cache
import numpy as np
import joblib 
import pickle

# --------------------------------------------------------------
# 1. 데이터 로드 (함수)
# --------------------------------------------------------------
@st.cache_data
def load_data():

    # -----------------------------
    # 발전소 위치 데이터
    # -----------------------------
    try:
        df_locations = pd.read_csv("data/locations_원본.csv")
        df_locations["발전기명"] = df_locations["발전기명"].str.strip()
        
        # ❗️ [수정] 발전사 컬럼의 앞뒤 공백과 내부 공백을 모두 제거 (강력한 정제)
        df_locations["발전사"] = df_locations["발전사"].str.strip().str.replace(' ', '') 
    except FileNotFoundError:
        st.error("오류: data/locations_원본.csv 파일을 찾을 수 없습니다.")
        st.stop()


    # -----------------------------
    # 실제 발전량 데이터
    # -----------------------------
    try:
        df_generation = pd.read_csv("data/발전량.csv")
        df_generation["날짜"] = pd.to_datetime(df_generation["날짜"], format="%Y.%m.%d")
    except FileNotFoundError:
        st.error("오류: data/발전량.csv 파일을 찾을 수 없습니다.")
        st.stop()
    except ValueError:
        st.error("오류: data/발전량.csv의 날짜 형식이 'YYYY.M.D'가 아닙니다.")
        st.stop()


    # -----------------------------
    # 태양광 데이터(연/월별) - Choropleth Map 용
    # -----------------------------
    path = "solar_analysis/"
    file_list = glob.glob(os.path.join(path, "*_solar_utf8.csv"))

    all_solar = []
    
    if not file_list:
        st.warning("경고: solar_analysis 폴더에 태양광 CSV 파일이 없습니다.")
        df_region_solar_monthly = pd.DataFrame()
        df_region_solar = pd.DataFrame()
    else:
        for file in file_list:
            try:
                year = int(os.path.basename(file).split("_")[0])
            except:
                continue

            df = pd.read_csv(file)
            df = df.rename(columns={"구분": "광역지자체"})
            df["광역지자체"] = df["광역지자체"].str.strip()

            month_cols = [f"{i}월" for i in range(1, 13)]

            for c in month_cols:
                if c in df.columns:
                    df[c] = df[c].astype(str).str.replace(",", "")
                    df[c] = pd.to_numeric(df[c], errors="coerce")

            df_long = df.melt(
                id_vars=["광역지자체"],
                value_vars=month_cols,
                var_name="월",
                value_name="태양광",
            )

            df_long["연도"] = year
            df_long["월"] = df_long["월"].str.replace("월", "").astype(int)

            all_solar.append(df_long)

        df_region_solar_monthly = pd.concat(all_solar, ignore_index=True)

        df_region_solar = (
            df_region_solar_monthly.groupby(["연도", "광역지자체"])["태양광"]
            .sum()
            .reset_index()
        )
    
    # -----------------------------
    # 지도 geojson
    # -----------------------------
    try:
        with open("data/korea_geojson.json", "r", encoding="utf-8") as f:
            korea_geojson = json.load(f)
    except FileNotFoundError:
        korea_geojson = {}
        st.error("오류: korea_geojson.json 파일을 찾을 수 없습니다.")
        st.stop()
        
    # -----------------------------
    # 미래/과거 예측 파일 로드
    # -----------------------------
    try:
        df_today_forecast = pd.read_csv("최종_일별_발전량_예측.csv", parse_dates=["날짜"])
        if '날짜' in df_today_forecast.columns:
            df_today_forecast["날짜"] = df_today_forecast["날짜"].dt.tz_localize(None)
    except:
        df_today_forecast = pd.DataFrame()

    try:
        df_past_forecast = pd.read_csv(
            "data/최종_과거_예측_데이터.csv", parse_dates=["날짜"]
        )
        if '날짜' in df_past_forecast.columns:
            df_past_forecast["날짜"] = df_past_forecast["날짜"].dt.tz_localize(None)
    except:
        df_past_forecast = pd.DataFrame()

    return (
        df_locations,
        df_generation,
        df_region_solar,
        korea_geojson,
        df_today_forecast,
        df_region_solar_monthly,
        df_past_forecast,
    )


# --------------------------------------------------------------
# 2. 오늘 예측 날씨 처리
# --------------------------------------------------------------
def process_weather_data(df_today_forecast, df_locations):

    if df_today_forecast.empty:
        return pd.DataFrame(), False

    today = pd.Timestamp.now().date()

    # 오늘 날짜 데이터 필터
    df = df_today_forecast[df_today_forecast["날짜"].dt.date == today].copy()

    # 발전사 + 위도/경도 + 설비용량 추가
    location_info_subset = df_locations[["발전기명", "발전사", "설비용량(MW)"]]

    df = df.merge(
        location_info_subset,
        on="발전기명",
        how="left"
    )

    # 위도/경도 누락되면 지도 못 그림 (forecast 파일의 위도/경도 사용)
    df = df.dropna(subset=["위도", "경도"]) 

    return df, (not df.empty)


# --------------------------------------------------------------
# 3. 지역별 색상 지도 (툴팁 정상 작동)
# --------------------------------------------------------------
def draw_choropleth_map(geojson, map_data, legend_title):

    m = folium.Map(location=[36.5, 127.5], zoom_start=7, tiles="OpenStreetMap")
    gj = copy.deepcopy(geojson)

    name_map = {
        "서울": "Seoul", "부산": "Busan", "대구": "Daegu", "인천": "Incheon",
        "광주": "Gwangju", "대전": "Daejeon", "울산": "Ulsan", "세종": "Sejong",
        "경기": "Gyeonggi-do", "강원": "Gangwon-do", "충북": "Chungcheongbuk-do",
        "충남": "Chungcheongnam-do", "전북": "Jeollabuk-do", "전남": "Jeollanam-do",
        "경북": "Gyeongsangbuk-do", "경남": "Gyeongsangnam-do", "제주": "Jeju",
    }
    
    map_data["광역지자체_clean"] = map_data["광역지자체"].apply(lambda x: x.split("도")[0].split("특별시")[0].split("광역시")[0].split("특별자치시")[0].split("특별자치도")[0].split("시")[0].strip())
    
    map_data["geojson_name"] = map_data["광역지자체_clean"].map(name_map)
    map_data = map_data.dropna(subset=['geojson_name']) 

    value_map = map_data.set_index("geojson_name")["태양광"]
    ko_map = map_data.set_index("geojson_name")["광역지자체_clean"]

    for f in gj["features"]:
        name = f["properties"]["NAME_1"]
        f["properties"]["태양광"] = float(value_map.get(name, 0))
        f["properties"]["KOREAN_NAME"] = ko_map.get(name, "")

    c = folium.Choropleth(
        geo_data=gj,
        key_on="feature.properties.NAME_1",
        data=map_data,
        columns=["geojson_name", "태양광"],
        fill_color="YlOrRd",
        fill_opacity=0.7,
        line_opacity=0.3,
        legend_name=legend_title,
    ).add_to(m)

    folium.GeoJsonTooltip(
        fields=["KOREAN_NAME", "태양광"],
        aliases=["지역:", "발전량(MWh):"],
        sticky=True,
        labels=True,
        style="background:white; padding:5px; border:1px solid black; border-radius:4px;",
    ).add_to(c.geojson)

    return m


# --------------------------------------------------------------
# 4. 발전소 날씨 지도 (3개 발전사 색상 적용 + 팝업 정보)
# --------------------------------------------------------------
# 팝업 아이콘 생성 함수 (HTML 마커)
def create_weather_icon(row):
    temp = row.get('평균기온', 0)
    prediction = row.get('발전량_예측(MWh)', 0)

    html = f"""
    <div style="font-family: 'Arial', sans-serif;
                background-color: rgba(255, 255, 255, 0.85); 
                border: 1px solid #777; 
                border-radius: 5px; 
                padding: 5px 8px; 
                font-size: 11px; 
                text-align: center;
                box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
                width: 110px; 
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;">
        <strong style="font-size: 13px; color: #333;">{row['발전기명']}</strong><br>
        <span style="color: #E67E22; font-weight: bold;">⚡ {prediction:.2f} MWh</span><br>
        <span style="color: #C0392B;">🌡️ {temp:.1f} °C (평균)</span>
    </div>
    """
    return folium.features.DivIcon(
        icon_size=(120, 60), icon_anchor=(60, 30), html=html
    )

# 지도 그리는 메인 함수
def draw_plant_weather_map(df, available, company):

    # 발전사별 마커 색상
    COLOR_MAP = {
        "한국남동발전": "red",
        "한국동서발전": "blue",
        "한국중부발전": "green",
    }

    m = folium.Map(location=[36.5, 127.5], zoom_start=7)

    if not available or df.empty:
        return m, df

    # 회사 필터
    if company != "전체":
        df = df[df["발전사"] == company]

    if df.empty:
        st.info(f"선택한 '{company}'의 발전소에 대한 데이터가 없습니다.")
        return m, df

    # 지도 중심을 발전소 평균 위치로 이동
    m.location = [df["위도"].mean(), df["경도"].mean()]
    m.zoom_start = 8 if company != "전체" else 7

    # 마커 생성
    for _, row in df.iterrows():
        color_key = row["발전사"] 

        color = COLOR_MAP.get(color_key, "gray")

        # 팝업 내용 정의
        popup_html = (
            f"<b>{row['발전기명']}</b><br>"
            f"발전량 예측: {row['발전량_예측(MWh)']:.2f} MWh<br>"
            f"평균기온: {row.get('평균기온', 0):.1f} °C<br>"
            f"일사량: {row.get('일사량', 0):.2f} MJ/m²"
        )

        # 팝업 객체 생성 및 최대 너비 설정 (가로로 길게 보이게 함)
        popup_obj = folium.Popup(popup_html, max_width=350) 
        
        folium.Marker(
            location=[row["위도"], row["경도"]],
            tooltip=row["발전기명"],
            popup=popup_obj, # ❗️ 팝업 객체 사용
            icon=folium.Icon(color=color, icon="bolt", prefix="fa"),
        ).add_to(m)

    return m, df
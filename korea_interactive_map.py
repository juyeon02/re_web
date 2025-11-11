import pandas as pd
import geopandas as gpd
import folium

print("--- 1. 데이터 불러오기 ---")

# (A) 전국 17개 시도 지도 모양 데이터 불러오기
map_file = "gadm41_KOR_1.json"
korea_map = gpd.read_file(map_file)
print(" - 전국 지도(GeoJSON) 불러오기 성공")

# (B) 17개 시도별 가상 분석 데이터 (이전과 동일)
data_rows = [
    ('부산', 3200),
    ('경상북도', 7100),
    ('경상남도', 8200),
    ('대구', 4100),
    ('대전', 3900),
    ('강원도', 10500),
    ('경주', 2900),
    ('경기도', 11200),
    ('경상북도', 10800),
    ('경상남도', 9500),
    ('인천', 4500),
    ('제주', 5300),
    ('전라북도', 9100),
    ('전라남도', 12500),
    ('세종', 1800),
    ('서울', 4800),
    ('울산', 3700)
]
analysis_data = pd.DataFrame(data_rows, columns=['Region_Name', 'Solar_Production'])
print(" - 17개 시도별 가상 데이터 준비 완료")


print("\n--- 2. 두 데이터 합치기 ---")

# 'NAME_1'(지도 영문이름)과 'Region_Name'(데이터 영문이름)을 기준으로 합칩니다.
merged_data = korea_map.merge(analysis_data, left_on='NAME_1', right_on='Region_Name')
print(" - 지도/분석 데이터 병합 완료")


print("\n--- 3. 인터랙티브 지도 만들기 ---")

# (A) 대한민국 중심에 기본 지도 생성 (위치, 축척 변경)
m = folium.Map(
    location=[36.5, 127.5],  # 대한민국의 중심 좌표
    zoom_start=7,           # 전국이 보이도록 축척 조절
    tiles='cartodbdarkmatter' # 어두운 배경 타일 (취향껏 'OpenStreetMap' 등으로 변경 가능)
)

# (B) 데이터에 따라 시도별로 색칠하기 (Choropleth)
folium.Choropleth(
    geo_data=merged_data,               # 경계선 데이터 (GeoDataFrame)
    data=merged_data,                   # 색칠할 값 데이터 (DataFrame)
    columns=['NAME_1', 'Solar_Production'], # 기준열(Key)과 값(Value) 열
    key_on='feature.properties.NAME_1', # geo_data의 'NAME_1' 속성을 기준으로
    fill_color='YlOrRd',                # 색상 테마 (YlGnBu -> YlOrRd로 변경)
    fill_opacity=0.7,                   # 색상 투명도
    line_opacity=0.3,                   # 경계선 투명도
    legend_name='태양광 발전량 (MW)'   # 범례 제목
).add_to(m)

# (C) 마우스 올리면 정보 뜨게 하기 (Tooltip / Popup)
folium.GeoJson(
    merged_data,
    # 툴팁 (마우스 호버)
    tooltip=folium.GeoJsonTooltip(
        fields=['NAME_1', 'Solar_Production'],     # 보여줄 데이터 열
        aliases=['시도 이름:', '발전량 (MW):'],      # 표시될 별명
        style=("background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;")
    ),
    # 팝업 (클릭 시)
    popup=folium.GeoJsonPopup(
        fields=['NAME_1', 'Solar_Production'],
        aliases=['시도 이름', '발전량 (MW)']
    )
).add_to(m)

print("\n--- 4. 파일로 저장하기 ---")

# 'korea_interactive_map.html' 파일이 생성됩니다.
output_file = 'korea_interactive_map.html'
m.save(output_file)

print(f"지도 생성이 완료되었습니다! {output_file} 파일을 열어보세요.")
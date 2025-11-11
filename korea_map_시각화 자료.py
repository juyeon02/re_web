import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

# 한글 폰트가 깨질 경우를 위한 설정 (우선 주석 처리)
# import platform
# if platform.system() == 'Windows':
#     plt.rc('font', family='Malgun Gothic')
# else:
#     # Mac이나 Linux의 경우 맞는 폰트 설정 필요
#     plt.rc('font', family='AppleGothic') 


print("--- 1. 지도 데이터 불러오는 중... ---")
# 1. 지도 데이터 불러오기
# (gadm41_KOR_1.json 파일이 이 스크립트와 같은 폴더에 있어야 함)
map_file = "gadm41_KOR_1.json"
korea_map = gpd.read_file(map_file)

print("--- 지도 불러오기 성공! (NAME_1 컬럼 확인) ---")
print(korea_map['NAME_1'].tolist()) # 17개 시도 영문 이름 확인용


print("\n--- 2. 시각화할 분석 데이터 준비 중... ---")
# 2. 분석 데이터 준비 (가상 데이터)
# (이름, 값) 튜플의 리스트로 '표'처럼 만듭니다.
# '이름'은 korea_map의 'NAME_1' 컬럼 값과 정확히 일치해야 합니다.
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

# DataFrame으로 변환
analysis_data = pd.DataFrame(data_rows, columns=['Region_Name', 'Solar_Production'])

# TODO: 나중에 이 가상 데이터 부분을 
# 실제 데이터 파일(예: pd.read_csv("my_data.csv"))로 교체하고,
# 'Region_Name' 컬럼을 'NAME_1'과 일치하도록 가공해야 합니다.

print("--- 가상 데이터 준비 완료 ---")
print(analysis_data.head())


print("\n--- 3. 지도 데이터와 분석 데이터 병합(merge) 중... ---")
# 3. 데이터 병합 (Merge)
# 지도(korea_map)의 'NAME_1'과 분석 데이터(analysis_data)의 'Region_Name'을
# 기준으로 두 테이블을 합칩니다.
merged_data = korea_map.merge(analysis_data, left_on='NAME_1', right_on='Region_Name')

print("--- 병합 완료 ---")


print("\n--- 4. 지도 시각화 시작... ---")
# 4. 지도 시각화 (Plotting) 🎨
fig, ax = plt.subplots(1, 1, figsize=(10, 14)) # 도화지(fig)와 그림(ax) 준비

# 병합된 데이터(merged_data)를 그립니다.
merged_data.plot(column='Solar_Production', # 'Solar_Production' 값에 따라 색을 칠함
                 ax=ax, 
                 legend=True,          # 범례 표시
                 cmap='OrRd',          # 색상 테마 (주황-빨강)
                 edgecolor='black',    # 경계선 색
                 linewidth=0.5,        # 경계선 두께
                 legend_kwds={'label': "태양광 발전량 (MW)", # 범례 제목
                              'orientation': "horizontal", # 범례 가로로
                              'shrink': 0.7})           # 범례 크기 조절

ax.set_title("전국 시도별 태양광 발전량 (가상 데이터)", fontsize=20) # 전체 지도 제목
ax.axis('off') # x, y축 좌표 숨기기

plt.show() # 지도 창 띄우기

print("--- 시각화 완료 ---")
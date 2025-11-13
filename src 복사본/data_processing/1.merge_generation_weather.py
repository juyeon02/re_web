import pandas as pd
import os

# ----------------------------------------------------------
# 1️⃣ 파일 경로 설정
# ----------------------------------------------------------
BASE_DIR = "/Users/parkhyeji/Desktop/PV"
GEN_PATH = os.path.join(BASE_DIR, "data/raw/발전량.csv")
WEATHER_PATH = os.path.join(BASE_DIR, "data/raw/기상.csv")
OUTPUT_PATH = os.path.join(BASE_DIR, "data/processed/발전량+기상.csv")

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

# ----------------------------------------------------------
# 2️⃣ CSV 불러오기
# ----------------------------------------------------------
gen_df = pd.read_csv(GEN_PATH, encoding='utf-8-sig')
weather_df = pd.read_csv(WEATHER_PATH, encoding='utf-8-sig')

# ----------------------------------------------------------
# 3️⃣ 컬럼 정리 및 날짜 변환 (timezone 제거)
# ----------------------------------------------------------
gen_df.columns = gen_df.columns.str.strip()
weather_df.columns = weather_df.columns.str.strip()

gen_df['날짜'] = pd.to_datetime(gen_df['날짜'], errors='coerce').dt.tz_localize(None)
weather_df['날짜'] = pd.to_datetime(weather_df['날짜'], errors='coerce').dt.tz_localize(None)

# 발전기명 문자열 정제 (공백, 특수문자 제거)
gen_df['발전기명'] = gen_df['발전기명'].astype(str).str.strip().str.replace(' ', '')
weather_df['발전기명'] = weather_df['발전기명'].astype(str).str.strip().str.replace(' ', '')

# ----------------------------------------------------------
# 4️⃣ 병합 (발전량 기준 Left Join)
# ----------------------------------------------------------
merged_df = pd.merge(
    gen_df,
    weather_df,
    on=['날짜', '발전기명'],
    how='left',  # ← 발전량 기준으로 병합
)

# ----------------------------------------------------------
# 5️⃣ 열 순서 재정렬
# ----------------------------------------------------------
final_cols = [
    '날짜', '발전기명', '설비용량(MW)', '발전량(MWh)',
    '평균기온', '평균습도', '총강수량', '총적설량',
    '평균풍속', '일조시간', '일사량', '평균운량',
    '날씨코드', '위도', '경도'
]

# 존재하는 컬럼만 추려서 재정렬 (예외 방지)
merged_df = merged_df[[c for c in final_cols if c in merged_df.columns]]

# ----------------------------------------------------------
# 6️⃣ 결과 저장
# ----------------------------------------------------------
merged_df.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')

# ----------------------------------------------------------
# 7️⃣ 로그 출력
# ----------------------------------------------------------
total_gen = len(gen_df)
merged_count = len(merged_df.dropna(subset=['평균기온']))  # 기상 데이터가 붙은 행만 계산
missing_count = total_gen - merged_count

print(f"✅ 병합 완료! 결과 저장 경로:\n{OUTPUT_PATH}")
print(f"📊 발전량 데이터 기준 총 {total_gen:,}개 중 {merged_count:,}개가 기상 데이터와 매칭되었습니다.")
if missing_count > 0:
    print(f"⚠️ 기상 데이터가 없는 행: {missing_count:,}개 (날짜/발전기명 불일치)")

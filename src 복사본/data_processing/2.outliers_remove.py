import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
from openpyxl import load_workbook
from openpyxl.drawing.image import Image as XLImage

# ----------------------------------------------------------
# ✅ macOS 한글 폰트 설정
# ----------------------------------------------------------
plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False

# ----------------------------------------------------------
# 설정
# ----------------------------------------------------------
input_path = "/Users/parkhyeji/Desktop/PV/data/processed/발전량+기상.csv"
output_dir = "/Users/parkhyeji/Desktop/PV/data/outliers_removed"
os.makedirs(output_dir, exist_ok=True)

# 출력 파일 경로
report_path = os.path.join(output_dir, "과거데이터품질_시각화통합보고서.xlsx")

# ----------------------------------------------------------
# 1️⃣ 데이터 불러오기
# ----------------------------------------------------------
df = pd.read_csv(input_path, encoding='utf-8-sig')
df.columns = df.columns.str.strip()

required_cols = [
    '날짜', '발전기명', '설비용량(MW)', '발전량(MWh)',
    '평균기온', '평균습도', '총강수량', '총적설량',
    '평균풍속', '일조시간', '일사량', '평균운량',
    '날씨코드', '위도', '경도'
]

missing_cols = [c for c in required_cols if c not in df.columns]
if missing_cols:
    raise ValueError(f"누락된 컬럼: {missing_cols}")

# ----------------------------------------------------------
# 2️⃣ 데이터 타입 및 결측치 점검
# ----------------------------------------------------------
dtype_info = pd.DataFrame({
    '컬럼명': df.columns,
    '데이터타입': df.dtypes.astype(str),
    '결측치수': df.isna().sum(),
    '고유값개수': df.nunique()
})

missing_ratio = (df.isnull().sum() / len(df) * 100).reset_index()
missing_ratio.columns = ['컬럼명', '결측치비율(%)']

# ----------------------------------------------------------
# 3️⃣ 날짜 범위 확인
# ----------------------------------------------------------
df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
date_summary = pd.DataFrame({
    '시작일자': [df['날짜'].min()],
    '종료일자': [df['날짜'].max()],
    '총일수': [(df['날짜'].max() - df['날짜'].min()).days]
})

# ----------------------------------------------------------
# 4️⃣ IQR 이상치 탐지 (발전량 기준)
# ----------------------------------------------------------
iqr_info_list, filtered_df_list = [], []

for gen, sub in df.groupby('발전기명'):
    q1, q3 = sub['발전량(MWh)'].quantile([0.25, 0.75])
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr

    iqr_info_list.append({
        '발전기명': gen,
        'Q1': q1, 'Q3': q3, 'IQR': iqr,
        '하한': lower, '상한': upper
    })

    sub_f = sub[(sub['발전량(MWh)'] >= lower) & (sub['발전량(MWh)'] <= upper)].copy()
    filtered_df_list.append(sub_f)

iqr_df = pd.DataFrame(iqr_info_list)
filtered_df = pd.concat(filtered_df_list, ignore_index=True)

# ----------------------------------------------------------
# 5️⃣ Z-score 이상치 탐지
# ----------------------------------------------------------
zscore_info = []
for gen, sub in df.groupby('발전기명'):
    mean, std = sub['발전량(MWh)'].mean(), sub['발전량(MWh)'].std()
    sub['Zscore'] = (sub['발전량(MWh)'] - mean) / std
    outliers = sub[np.abs(sub['Zscore']) > 3]
    zscore_info.append({
        '발전기명': gen,
        '평균': mean,
        '표준편차': std,
        '이상치수': len(outliers),
        '전체데이터수': len(sub),
        '이상치비율(%)': round(len(outliers) / len(sub) * 100, 2)
    })

zscore_df = pd.DataFrame(zscore_info)

# ----------------------------------------------------------
# 6️⃣ 시각화 (그래프 이미지 파일 생성)
# ----------------------------------------------------------
img_dir = os.path.join(output_dir, "plots")
os.makedirs(img_dir, exist_ok=True)

# 🔹 결측치율 시각화
plt.figure(figsize=(8, 4))
sns.barplot(data=missing_ratio, x='컬럼명', y='결측치비율(%)', palette='Blues_d')
plt.title('결측치 비율 (%)')
plt.xticks(rotation=45)
plt.tight_layout()
missing_img = os.path.join(img_dir, "missing_ratio.png")
plt.savefig(missing_img, dpi=150)
plt.close()

# 🔹 발전기별 발전량 분포 히스토그램
plt.figure(figsize=(10, 5))
sns.histplot(df, x='발전량(MWh)', hue='발전기명', multiple='stack', bins=30)
plt.title('발전기별 발전량 분포')
plt.tight_layout()
hist_img = os.path.join(img_dir, "generation_hist.png")
plt.savefig(hist_img, dpi=150)
plt.close()

# 🔹 발전기별 박스플롯 (IQR 시각화)
plt.figure(figsize=(12, 6))
sns.boxplot(data=df, x='발전기명', y='발전량(MWh)')
plt.title('발전기별 발전량 박스플롯 (IQR 이상치 시각화)')
plt.xticks(rotation=45)
plt.tight_layout()
box_img = os.path.join(img_dir, "iqr_boxplot.png")
plt.savefig(box_img, dpi=150)
plt.close()

# ----------------------------------------------------------
# 7️⃣ 통합 엑셀 보고서 생성
# ----------------------------------------------------------
with pd.ExcelWriter(report_path, engine='openpyxl') as writer:
    dtype_info.to_excel(writer, index=False, sheet_name='1_데이터타입')
    missing_ratio.to_excel(writer, index=False, sheet_name='2_결측치비율')
    date_summary.to_excel(writer, index=False, sheet_name='3_날짜범위')
    iqr_df.to_excel(writer, index=False, sheet_name='4_IQR통계')
    zscore_df.to_excel(writer, index=False, sheet_name='5_Zscore통계')
    filtered_df.to_excel(writer, index=False, sheet_name='6_이상치제거')

# ----------------------------------------------------------
# 8️⃣ 이상치 제거된 데이터 별도 파일 저장
# ----------------------------------------------------------
filtered_csv_path = os.path.join(output_dir, "이상치제거_데이터.csv")
filtered_df.to_csv(filtered_csv_path, index=False, encoding='utf-8-sig')

# ----------------------------------------------------------
# 완료 메시지
# ----------------------------------------------------------
print("✅ 데이터 품질 진단 + 이상치 탐지 + 시각화 보고서 생성 완료!")
print(f"📘 통합 보고서 파일: {report_path}")
print(f"📊 그래프 이미지 폴더: {img_dir}")
print(f"💾 이상치 제거 CSV: {filtered_csv_path}")

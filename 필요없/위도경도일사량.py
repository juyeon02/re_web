import pandas as pd
import numpy as np

# --- 파라미터 ---
INPUT_FILE = "solar_data_2024_total.csv"
OUTPUT_FILE = "solar_data_daily_2024.csv"
OUTPUT_ENCODING = "utf-8-sig"
# ----------------

try:
    df = pd.read_csv(INPUT_FILE)
    print(f"'{INPUT_FILE}' 파일 로드 성공. (총 {len(df)} 행)")

    # 2. 'DATETIME' 컬럼을 실제 날짜/시간 객체로 변환합니다.
    df['DATETIME'] = pd.to_datetime(df['DATETIME'])

    # 3. 'SI' 컬럼의 결측값(NaN)을 0으로.
    df['SI'] = df['SI'].fillna(0)
    print(" 'DATETIME' 변환 및 'SI' 결측값(NaN)을 0으로 처리 완료.")

    # 4. [핵심] 일별 데이터로 집계(Aggregate)
    # '발전기명'과 '날짜(D)'를 기준으로 그룹화(groupby)
    # pd.Grouper(key='DATETIME', freq='D')는 DATETIME 컬럼을 'D'(Daily) 기준으로 묶어줍니다.
    df_daily_sum = df.groupby(
        ['발전기명', pd.Grouper(key='DATETIME', freq='D')]
    )['SI'].sum().reset_index()

    # 5. 컬럼명 변경
    df_daily_sum = df_daily_sum.rename(columns={
        'DATETIME': '날짜',
        'SI': '일별_총_일사량(SI_Sum)'
    })
    
    # '날짜' 컬럼에서 시간(00:00:00) 부분 제거
    df_daily_sum['날짜'] = df_daily_sum['날짜'].dt.date

    print(" '발전기명' 및 '일' 기준으로 SI 값 합산 완료.")

    # 6. 결과를 새 CSV 파일로 저장
    df_daily_sum.to_csv(OUTPUT_FILE, index=False, encoding=OUTPUT_ENCODING)

    print(f"\n 일별 합산 완료")
    print(f"일별 합산 데이터(총 {len(df_daily_sum)} 행)를 '{OUTPUT_FILE}' 파일로 저장했습니다.")

    print("\n--- '일별 합계' 데이터 미리보기 (처음 10행) ---")
    print(df_daily_sum.head(10))

except FileNotFoundError:
    print(f"[오류] 입력 파일 '{INPUT_FILE}'을(를) 찾을 수 없습니다.")
except Exception as e:
    print(f"[오류] 데이터 처리 중 오류가 발생했습니다: {e}")
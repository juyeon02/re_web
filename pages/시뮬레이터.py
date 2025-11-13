import streamlit as st
import web_utils # ❗️ 'web_utils.py' (utils.py) 임포트
import pandas as pd
import joblib
import pickle
import os

# -----------------------------------------------------------------
# 1. 페이지 설정 및 데이터 로드
# -----------------------------------------------------------------
st.set_page_config(layout="wide")
st.title("⚙️ 발전량 예측 시뮬레이터 (What-if)")

# ❗️ 모델이 학습한 9개 변수 (순서 중요)
MODEL_FEATURES = [
    '설비용량(MW)', '평균기온', '평균습도', '총강수량', '총적설량',
    '평균풍속', '일조시간', '일사량', '평균운량'
]

# ❗️ 발전소 목록과 기본 설비용량을 가져오기 위해 df_locations 로드
try:
    df_locations = web_utils.load_data()[0] # load_data()의 첫 번째 반환값이 df_locations
except FileNotFoundError:
    st.error("`data/locations_원본.csv` 파일을 찾을 수 없습니다.")
    st.stop()
except Exception as e:
    st.error(f"데이터 로드 중 오류 발생: {e}")
    st.stop()

# -----------------------------------------------------------------
# 2. 시뮬레이터 UI
# -----------------------------------------------------------------

# 1. 모델 선택
plant_list_sim = sorted(df_locations['발전기명'].unique())
selected_plant_sim = st.selectbox(
    "예측할 발전소를 선택하세요:",
    plant_list_sim,
    key='sim_plant_select'
)

# 2. 9개 변수 입력받기
st.subheader(f"'{selected_plant_sim}'의 예측 조건 입력")

# '설비용량'은 선택한 발전소의 기본값으로 설정
try:
    default_capacity = df_locations[df_locations['발전기명'] == selected_plant_sim]['설비용량(MW)'].values[0]
except IndexError:
    st.error(f"'{selected_plant_sim}'의 설비용량 정보를 찾을 수 없습니다. 'data/locations_원본.csv'를 확인하세요.")
    default_capacity = 0.0 # 기본값

col1, col2, col3 = st.columns(3)

with col1:
    capacity = st.number_input("설비용량(MW)", value=float(default_capacity), step=1.0)
    temp = st.number_input("평균기온 (°C)", value=15.0)
    humidity = st.number_input("평균습도 (%)", value=60.0)

with col2:
    rain = st.number_input("총강수량 (mm)", value=0.0)
    snow = st.number_input("총적설량 (cm)", value=0.0)
    wind = st.number_input("평균풍속 (m/s)", value=2.0)

with col3:
    sunshine = st.number_input("일조시간 (h)", value=8.0)
    solar = st.number_input("일사량 (MJ/m²)", value=15.0)
    cloud = st.number_input("평균운량 (%)", value=30.0)

# 3. 예측 실행 버튼
if st.button("예측 실행하기"):
    
    # 3-1. 모델 파일 경로 생성 (7일발전량예측api.py와 동일한 로직)
    clean_name = selected_plant_sim.strip().replace(' ', '')
    model_path = f"models/rf_full_{clean_name}_step9.pkl" # .pkl 파일 사용

    if os.path.exists(model_path):
        try:
            # 3-2. 선택한 발전소의 모델(.pkl) 불러오기
            # (joblib이 오류를 일으켰으므로 pickle로 시도)
            model = None
            try:
                with open(model_path, 'rb') as f:
                    model = pickle.load(f)
            except Exception as e_pkl:
                # pickle도 실패하면 joblib으로 다시 시도
                try:
                    model = joblib.load(model_path)
                except Exception as e_joblib:
                    st.error(f"모델 로드 실패 (Pickle: {e_pkl}, Joblib: {e_joblib})")
                    
            if model:
                # 3-3. 입력값을 모델이 학습한 9개 순서(MODEL_FEATURES)대로 2D 배열로 만듦
                features_df = pd.DataFrame([[
                    capacity, temp, humidity, rain, snow, wind, sunshine, solar, cloud
                ]], columns=MODEL_FEATURES)
                
                # 3-4. 예측 수행
                prediction = model.predict(features_df) 
                
                st.success(f"## 💡 예측 발전량: {prediction[0]:.2f} MWh")

        except Exception as e:
            st.error(f"예측 중 오류 발생: {e}")
    else:
        st.error(f"'{selected_plant_sim}'의 모델 파일({model_path})을 찾을 수 없습니다.")
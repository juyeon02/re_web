# pages/시뮬레이터.py
import streamlit as st
import pandas as pd
import joblib
import web_utils
import os

st.set_page_config(layout="wide")
st.title("⚙️ 태양광 발전량 시뮬레이터")

MODEL_FEATURES = [
    '설비용량(MW)', '평균기온', '평균습도', '총강수량', '총적설량',
    '평균풍속', '일조시간', '일사량', '평균운량'
]

df_locations = web_utils.load_data()[0]

# --------------------------
# 발전소 선택
# --------------------------
plant_list = sorted(df_locations['발전기명'].unique())
selected_plant = st.selectbox("발전소 선택", plant_list)

# 설비용량 자동 적용
default_capacity = float(
    df_locations[df_locations['발전기명'] == selected_plant]['설비용량(MW)'].values[0]
)

st.subheader(f"🌤 '{selected_plant}' 입력 변수")

col1, col2, col3 = st.columns(3)

with col1:
    capacity = st.number_input("설비용량(MW)", value=default_capacity)
    temp = st.number_input("평균기온(°C)", value=15.0)
    humidity = st.number_input("평균습도(%)", value=60.0)

with col2:
    rain = st.number_input("총강수량(mm)", value=0.0)
    snow = st.number_input("총적설량(cm)", value=0.0)
    wind = st.number_input("평균풍속(m/s)", value=2.0)

with col3:
    sunshine = st.number_input("일조시간(h)", value=8.0)
    solar = st.number_input("일사량(MJ/m²)", value=15.0)
    cloud = st.number_input("평균운량(%)", value=40.0)

# --------------------------
# 예측 실행
# --------------------------
if st.button("📡 예측하기"):
    clean_name = selected_plant.strip().replace(" ", "")
    model_path = f"models/rf_full_{clean_name}_step9.pkl"

    if not os.path.exists(model_path):
        st.error(f"❌ 모델 파일을 찾을 수 없습니다: {model_path}")
    else:
        try:
            model = joblib.load(model_path)
            df_input = pd.DataFrame([[capacity, temp, humidity, rain, snow, wind,
                                      sunshine, solar, cloud]], columns=MODEL_FEATURES)

            pred = model.predict(df_input)[0]
            st.success(f"### 🔥 예측 발전량: **{pred:.2f} MWh**")

        except Exception as e:
            st.error(f"❌ 예측 중 오류: {e}")

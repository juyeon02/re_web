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

# --------------------------------------------------
# 3. 발전량 예측
# --------------------------------------------------
st.divider()
st.header("📈 일일 태양광 발전량 예측 시뮬레이터 설명")

with st.expander("ℹ️ 태양광 발전량 예측 시뮬레이터 설명", expanded=True):
    st.markdown("""
    ### Q. 시뮬레이터가 어떻게 작동하나요?

    이 페이지는 **발전소별 머신러닝 모델(Random Forest)**을 활용해 **일일 태양광 발전량을 자동으로 예측**합니다. 
                **발전소**를 선택하고 **기상값**을 입력하세요!
                

    #### 📌 사용되는 주요 기상 요소
    - **일사량(MJ/m²)** : 태양광 발전량에 가장 큰 영향을 주는 지표  
      (값이 높을수록 태양에너지가 많이 들어오는 날)
    - **일조시간(h)** : 실제로 햇빛이 비친 시간  
    - **평균운량(%)** : 구름 양 (0 = 맑음, 100 = 흐림)  
    - **평균기온(°C)** : 온도가 너무 높거나 낮아도 발전효율이 떨어짐  
    - **평균풍속(m/s)** : 공기 흐름은 구름 이동 및 대기 투과율에 영향  
    - **총강수량(mm)** : 비/눈 오는 날 일사량 급감

    #### 🌤️ 날씨 상태 간단 기준
    | 상태 | 평균운량(%) | 설명 |
    |------|------------|------|
    | ☀️ 맑음 | 0 ~ 30 | 태양광 발전 매우 유리 |
    | 🌤️ 구름 조금 | 30 ~ 60 | 평균 수준의 발전 예상 |
    | ☁️ 흐림 | 60 ~ 90 | 발전량 감소 |
    | 🌧️/🌨️ 비/눈 | 90 ~ 100 | 일사량 거의 없음 |

    """)

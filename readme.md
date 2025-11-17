# 🌞 태양광 발전량 예측 통합 시스템  
기상 데이터 기반 *전국 발전소별 태양광 발전량 예측·분석 시스템*  

---

## 📘 프로젝트 개요

이 프로젝트는 **기상데이터(일사량·일조시간·기온·습도·강수·풍속 등)**를 기반으로  
**전국 발전소별 일일 태양광 발전량을 예측**하는 시스템입니다.

다음 기능들을 제공합니다:

- 발전소별 RandomForest 모델 생성 및 저장
- 하이퍼파라미터 튜닝(GridSearchCV)
- 변수 중요도 분석 및 후진제거법 (Backward Elimination)
- Open-Meteo API 기반 7일 발전량 자동 예측
- GitHub Action을 통한 매일 자동 업데이트
- Streamlit 기반 시각화 대시보드

---

# 🔥 전체 파이프라인 구조

📁 과거데이터 → 이상치 제거 → 발전소별 모델 학습
📁 모델 저장 (.pkl)
📁 API 호출(Open-Meteo) → 7일 날씨 데이터 생성
📁 모델로 발전량 예측 → CSV 저장
📁 GitHub Action 자동 업데이트
📁 Streamlit 대시보드에서 지도·그래프 제공


---

# 🧠 모델링

총 4가지 RandomForest 모델을 발전기별로 생성합니다:

| 모델 종류 | 설명 |
|----------|------|
| Baseline Model | 전체 기상변수 사용한 기본 모델 |
| Feature Importance Model | 변수별 중요도 분석 & 그래프 저장 |
| Backward Elimination | 중요도 낮은 변수부터 제거 → 최적 모델 선택 |
| Hyperparameter Tuning | GridSearchCV로 최적 파라미터 자동 탐색 |

---

# 🌤️ 7일 발전량 예측 API

`7일발전량예측api.py` 를 사용하여:

- 발전소 좌표 기반 기상 데이터 수집
- 발전기별 RandomForest 모델로 발전량 산출
- CSV 자동 저장:
data/최종_일별_발전량_예측.csv


Streamlit 대시보드에서 사용됨.

---

# 🤖 GitHub Actions 자동 실행

매일 한국 시간 오전 9시(UTC 00:00)에 자동 실행됩니다.

`.github/workflows/weather_update.yml`


name: 날씨 예보 업데이트

on:
  schedule:
    - cron: '0 0 * * *'
  workflow_dispatch:

jobs:
  update-weather-data:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Run weather forecast script
        run: python 7일발전량예측api.py

      - name: Commit and push if changes
        uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: '날씨: 매일 예보 데이터 자동 업데이트'
          file_pattern: 'data/최종_일별_발전량_예측.csv'

주요 기능
전국 발전소 지도 시각화(Folium)

발전소 클릭 시 상세 분석

7일 발전량 예측 그래프

지역별 태양광 분석 지도

발전량 시뮬레이터(직접 기상값 입력하여 예측)


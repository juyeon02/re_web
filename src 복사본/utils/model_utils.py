# 모델 저장/로드용 유틸리티 파일

import os
import joblib

def save_model(model, model_name, output_dir="outputs/models"):
    """
    모델 객체를 지정된 경로에 저장
    """
    os.makedirs(output_dir, exist_ok=True)
    save_path = os.path.join(output_dir, f"{model_name}.pkl")
    joblib.dump(model, save_path)
    print(f"✅ 모델 저장 완료: {save_path}")
    return save_path


def load_model(model_name, output_dir="outputs/models"):
    """
    지정된 이름의 모델을 로드
    """
    load_path = os.path.join(output_dir, f"{model_name}.pkl")
    if not os.path.exists(load_path):
        raise FileNotFoundError(f"❌ 모델 파일을 찾을 수 없습니다: {load_path}")
    model = joblib.load(load_path)
    print(f"✅ 모델 로드 완료: {load_path}")
    return model
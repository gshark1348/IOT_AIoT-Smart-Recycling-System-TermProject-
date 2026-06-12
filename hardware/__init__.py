import os

# Raspberry Pi 5에서는 lgpio 기반 GPIO 제어를 권장합니다.
# 패키지가 로드될 때 가장 먼저 실행되어 gpiozero 모듈 임포트 전 환경을 설정합니다.
os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")

from .manager import Hardware

__all__ = ["Hardware"]
import os
from pathlib import Path

# ============================================================
# 사용자가 수정할 수 있는 설정값
# ============================================================

# ------------------------------
# GPIO 핀 설정, BCM 번호 기준
# ------------------------------
PIN_DHT = 4              # DHT22/DHT11 DATA: GPIO4, 물리핀 7
PIN_ULTRA_TRIG = 23      # HC-SR04 TRIG: GPIO23, 물리핀 16
PIN_ULTRA_ECHO = 24      # HC-SR04 ECHO: GPIO24, 물리핀 18, 전압분배 필수
PIN_SERVO = 18           # Servo Signal: GPIO18, 물리핀 12
PIN_LED = 27             # LED: GPIO27, 물리핀 13
PIN_BUZZER = 22
PIN_MOTION = 25          # PIR Motion Sensor OUT: GPIO25, 물리핀 22          # Piezo Buzzer +: GPIO22, 물리핀 15
PIN_HX711_DT = 5         # HX711 DT/DOUT: GPIO5, 물리핀 29
PIN_HX711_SCK = 6        # HX711 SCK/CLK: GPIO6, 물리핀 31

# ------------------------------
# 센서 사용 여부
# 하드웨어가 아직 없으면 False로 바꿔도 UI와 흐름 테스트 가능
# ------------------------------
USE_DHT = True
USE_ULTRASONIC = True
USE_SERVO = True
USE_LED = True
USE_BUZZER = True

# PIR motion sensor
USE_MOTION_SENSOR = True
MOTION_ACTIVE_HIGH = True
BUZZER_LOW_LEVEL_TRIGGER = True
USE_LOADCELL = False

# ------------------------------
# DHT 센서 종류
# DHT22를 쓰면 "DHT22", DHT11을 쓰면 "DHT11"
# ------------------------------
DHT_SENSOR_TYPE = "DHT22"

# ------------------------------
# YOLO 설정
# models/best.pt 파일이 있으면 YOLO를 사용합니다.
# 없으면 Classification Failed 화면 후 수동 선택으로 진행합니다.
# ------------------------------
MODEL_PATH = "models/best.pt"
MIN_CONFIDENCE = 0.25
ADMIN_PASSWORD = "0000"

# 본인의 YOLO 모델 클래스 이름에 맞게 수정하는 부분입니다.
# 예: 모델 class가 plastic_bottle이면 "plastic_bottle": "Plastic" 추가
CLASS_TO_CATEGORY = {
    "plastic": "Plastic",
    "plastic bottle": "Plastic",
    "bottle": "Plastic",
    "pet bottle": "Plastic",

    "can": "Can/Metal",
    "metal": "Can/Metal",
    "aluminum can": "Can/Metal",

    "paper": "Paper",
    "cardboard": "Paper",

    "glass": "Glass",
    "glass bottle": "Glass",

    "general waste": "General Waste",
    "trash": "General Waste",
    "waste": "General Waste",
}

CATEGORIES = ["Plastic", "Can/Metal", "Paper", "Glass", "General Waste"]

CATEGORY_GUIDE = {
    "Plastic": [
        "Empty and rinse the container.",
        "Remove food or liquid residue.",
        "Separate caps or labels if required.",
        "Flatten bulky bottles when possible."
    ],
    "Can/Metal": [
        "Empty and rinse the can.",
        "Remove food residue.",
        "Be careful with sharp lids.",
        "Separate non-metal parts if possible."
    ],
    "Paper": [
        "Keep paper clean and dry.",
        "Flatten boxes before disposal.",
        "Do not recycle greasy or wet paper.",
        "Remove plastic film or tape if possible."
    ],
    "Glass": [
        "Empty and rinse the glass item.",
        "Remove caps or lids if possible.",
        "Do not intentionally break glass.",
        "Handle carefully to avoid injury."
    ],
    "General Waste": [
        "Use this bin for non-recyclable waste.",
        "Do not mix recyclables with general waste.",
        "Bag dirty waste securely if needed.",
        "Dispose of hazardous items separately."
    ]
}

# ------------------------------
# 카메라 설정
# ------------------------------
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 10

# 프레임 변화량 기준값
# 자동 캡처가 너무 안 되면 값을 20~30으로 올리십시오.
# 너무 빨리 캡처되면 값을 8~12로 낮추십시오.
FRAME_DIFF_THRESHOLD = 15.0

# 움직임이 없어야 하는 시간
STABLE_TIME_SEC = 2

# 자동 캡처 대기 최대 시간
STABILITY_TIMEOUT_SEC = 10

REQUIRED_STABLE_FRAMES = CAMERA_FPS * STABLE_TIME_SEC

# ------------------------------
# 초음파 안전 거리 설정
# Servo 동작 전 이 거리보다 가까우면 손/이물질로 판단
# ------------------------------
SAFE_DISTANCE_CM = 15.0

# ------------------------------
# 화재 경보 설정
# 온도가 FIRE_TEMP_THRESHOLD_C 이상으로 FIRE_CONFIRM_SECONDS 동안 지속되면
# Fire Alarm 화면을 띄우고 시스템을 일시중단합니다.
# 온도가 다시 FIRE_TEMP_THRESHOLD_C 이하로 FIRE_RECOVERY_SECONDS 동안 유지되면
# Fire Alarm 화면을 종료합니다.
# ------------------------------
FIRE_TEMP_THRESHOLD_C = 50.0
FIRE_CONFIRM_SECONDS = 30
FIRE_RECOVERY_SECONDS = 30
FIRE_CHECK_INTERVAL_SEC = 1.0

# Fire Alarm 화면이 표시되는 동안 부저를 울리는 간격입니다.
BUZZER_INTERVAL_SEC = 0.7
BUZZER_ON_SEC = 0.15

# Passive piezo buzzer tone settings
BUZZER_TONE_HZ = 2000
BUZZER_DUTY = 0.5

# Button click sound
BUZZER_CLICK_MS = 45
BUZZER_CLICK_HZ = 2600

# Point earned sound
POINT_SOUND_DUTY = 0.55
POINT_SOUND_TONES = [2200, 2800, 3600]
POINT_SOUND_ON_MS = 90
POINT_SOUND_GAP_MS = 55

# Fire Alarm siren sound
# Low/high tone alternates only while the Fire Alarm screen is displayed.
FIRE_ALARM_LOW_HZ = 1800
FIRE_ALARM_HIGH_HZ = 3000
FIRE_ALARM_DUTY = 0.65
FIRE_ALARM_BEEP_ON_SEC = 0.22
FIRE_ALARM_BEEP_OFF_SEC = 0.10

# ------------------------------
# Servo 각도 설정
# 실제 분류판 구조에 맞게 반드시 조정하십시오.
# Admin Mode → Servo Test에서 확인하면서 수정하면 됩니다.
# ------------------------------
SERVO_HOME_ANGLE = 90

SERVO_ANGLE_MAP = {
    "Plastic": 20,
    "Can/Metal": 55,
    "Paper": 90,
    "Glass": 125,
    "General Waste": 160,
}

SERVO_MIN_PULSE_WIDTH = 0.0005
SERVO_MAX_PULSE_WIDTH = 0.0025
SERVO_MOVE_DELAY_SEC = 1.0

# ------------------------------
# 로드셀 설정
# 정확한 kg 측정은 보정이 필요합니다.
# 값이 이상하면 Admin Mode에서 Reset Bin Weight 후 보정값을 조정하십시오.
# ------------------------------
FULL_WEIGHT_THRESHOLD_KG = 1.0
HX711_CALIBRATION_FACTOR = 100000.0

# ------------------------------
# 화면 설정
# 7인치 LCD가 800x480이면 그대로 사용
# ------------------------------
LCD_WIDTH = 800
LCD_HEIGHT = 480
FULLSCREEN = True

# ------------------------------
# 저장 경로
# ------------------------------
BASE_DIR = Path(__file__).resolve().parent
CAPTURE_DIR = BASE_DIR / "captures"
LOG_DIR = BASE_DIR / "logs"
MODEL_FILE = BASE_DIR / MODEL_PATH
LOG_FILE = LOG_DIR / "sorting_log.csv"
USER_FILE = LOG_DIR / "users.json"

# ------------------------------
# 사용자 / 포인트 / 자동 로그아웃 설정
# ------------------------------
SESSION_TIMEOUT_SEC = 180

# Screen power control by motion sensor
# 화면이 너무 빨리 꺼지는 것을 막기 위해, 모션이 없는 상태가 일정 시간 유지될 때만 화면을 끕니다.
MOTION_SCREEN_OFF_SEC = 30
MOTION_CHECK_INTERVAL_MS = 1000
POINT_PER_SORT = 10

CAPTURE_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

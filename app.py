#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AIoT Smart Recycling System
Raspberry Pi 5용 통합 실행 코드

구현 기능:
1. LCD Touch Display 기반 UI
2. 첫 화면 우측 상단 [Admin Mode]
3. "쓰레기를 올려놓고 Sort 버튼을 눌러주세요" 안내
4. 카메라 프레임 변화량 기반 자동 캡처
5. YOLO 분류, 모델이 없으면 수동 선택 모드
6. Confidence 낮을 때 수동 선택
7. 초음파 센서로 투입구 손/이물질 안전 확인
8. Servo Motor 분류판 각 degrees
9. 로드셀 무게 측정, 기본값은 실패 시 0kg 처리
10. CSV 로그 저장
11. Statistics 화면
12. Admin Mode: 센서 상태, Servo 테스트, 카메라 테스트, 로그 초기화

GPIO 번호는 BCM 번호 기준입니다.
"""

import os

# Raspberry Pi 5에서는 lgpio 기반 GPIO 제어를 권장합니다.
# gpiozero import 전에 설정해야 합니다.
os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")

import csv
import json
import hashlib
import subprocess
import time
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import font

import cv2
import numpy as np
from PIL import Image, ImageTk


# ============================================================
# 1. 사용자가 수정할 수 있는 설정값
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
USE_DHT = False
USE_ULTRASONIC = False
USE_SERVO = False
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


# ============================================================
# 2. 라이브러리 import
# ============================================================

try:
    from gpiozero import LED, DistanceSensor, AngularServo, DigitalInputDevice, DigitalOutputDevice, PWMOutputDevice
    GPIO_OK = True
except Exception as e:
    print("[WARN] GPIO 라이브러리 로드 실패:", e)
    GPIO_OK = False

try:
    from picamera2 import Picamera2
    PICAMERA_OK = True
except Exception as e:
    print("[WARN] Picamera2 로드 실패:", e)
    PICAMERA_OK = False

try:
    import board
    import adafruit_dht
    DHT_OK = True
except Exception as e:
    print("[WARN] DHT 라이브러리 로드 실패:", e)
    DHT_OK = False

try:
    from ultralytics import YOLO
    YOLO_OK = True
except Exception as e:
    print("[INFO] ultralytics 미설치 또는 로드 실패. 수동 선택 모드 사용:", e)
    YOLO_OK = False


# ============================================================
# 3. HX711 로드셀 간단 드라이버
# ============================================================

class SimpleHX711:
    """
    HX711 로드셀 값을 읽기 위한 간단한 클래스입니다.
    정확한 무게 측정을 위해서는 반드시 보정이 필요합니다.
    """

    def __init__(self, dout_pin, sck_pin):
        self.dout = DigitalInputDevice(dout_pin, pull_up=False)
        self.sck = DigitalOutputDevice(sck_pin, initial_value=False)
        self.offset = 0

    def read_raw_once(self, timeout=1.0):
        start = time.time()

        while self.dout.value == 1:
            if time.time() - start > timeout:
                raise TimeoutError("HX711 응답 시간 초과")
            time.sleep(0.001)

        count = 0

        for _ in range(24):
            self.sck.on()
            count = count << 1
            self.sck.off()
            if self.dout.value:
                count += 1

        # gain 128 설정용 추가 pulse
        self.sck.on()
        self.sck.off()

        # 24bit signed 변환
        if count & 0x800000:
            count -= 0x1000000

        return count

    def read_average(self, samples=5):
        values = []

        for _ in range(samples):
            try:
                values.append(self.read_raw_once())
            except Exception:
                pass
            time.sleep(0.05)

        if not values:
            raise RuntimeError("HX711 값을 읽지 못했습니다.")

        return sum(values) / len(values)

    def tare(self):
        self.offset = self.read_average(samples=10)
        return self.offset

    def get_weight_kg(self):
        raw = self.read_average(samples=5)
        return (raw - self.offset) / HX711_CALIBRATION_FACTOR


# ============================================================
# 4. 하드웨어 제어
# ============================================================

class Hardware:
    def __init__(self):
        self.led = None
        self.buzzer = None
        self.motion_sensor = None
        self.servo = None
        self.ultrasonic = None
        self.dht = None
        self.hx711 = None

        self.init_gpio()
        self.init_dht()

    def init_gpio(self):
        if not GPIO_OK:
            return

        if USE_LED:
            try:
                self.led = LED(PIN_LED)
            except Exception as e:
                print("[WARN] LED initialization failed:", e)

        if USE_MOTION_SENSOR:
            try:
                self.motion_sensor = DigitalInputDevice(PIN_MOTION, pull_up=False)
                print("[INFO] Motion sensor initialized on GPIO", PIN_MOTION)
            except Exception as e:
                self.motion_sensor = None
                print("[WARN] Motion sensor initialization failed:", e)

        if USE_BUZZER:
            try:
                self.buzzer = PWMOutputDevice(PIN_BUZZER, active_high=not BUZZER_LOW_LEVEL_TRIGGER, initial_value=0, frequency=BUZZER_TONE_HZ)
            except Exception as e:
                print("[WARN] Buzzer initialization failed:", e)

        if USE_ULTRASONIC:
            try:
                self.ultrasonic = DistanceSensor(
                    echo=PIN_ULTRA_ECHO,
                    trigger=PIN_ULTRA_TRIG,
                    max_distance=2.0
                )
            except Exception as e:
                print("[WARN] Ultrasonic sensor initialization failed:", e)

        if USE_SERVO:
            try:
                self.servo = AngularServo(
                    PIN_SERVO,
                    min_angle=0,
                    max_angle=180,
                    min_pulse_width=SERVO_MIN_PULSE_WIDTH,
                    max_pulse_width=SERVO_MAX_PULSE_WIDTH
                )
                self.move_servo(SERVO_HOME_ANGLE)
            except Exception as e:
                print("[WARN] Servo initialization failed:", e)

        if USE_LOADCELL:
            try:
                self.hx711 = SimpleHX711(PIN_HX711_DT, PIN_HX711_SCK)
                self.hx711.tare()
            except Exception as e:
                print("[WARN] HX711 initialization failed:", e)

    def init_dht(self):
        if not USE_DHT or not DHT_OK:
            return

        try:
            dht_pin = getattr(board, f"D{PIN_DHT}")

            if DHT_SENSOR_TYPE.upper() == "DHT11":
                self.dht = adafruit_dht.DHT11(dht_pin, use_pulseio=False)
            else:
                self.dht = adafruit_dht.DHT22(dht_pin, use_pulseio=False)

        except Exception as e:
            print("[WARN] DHT initialization failed:", e)
            self.dht = None

    def led_on(self):
        if self.led:
            self.led.on()

    def led_off(self):
        if self.led:
            self.led.off()

    def motion_detected(self):
        if not USE_MOTION_SENSOR:
            return True

        if self.motion_sensor is None:
            # 센서가 없거나 초기화 실패 시 화면이 꺼지지 않도록 안전하게 True 처리
            return True

        try:
            value = bool(self.motion_sensor.value)

            if MOTION_ACTIVE_HIGH:
                return value

            return not value

        except Exception:
            return True

    def buzzer_on(self, tone_hz=None, duty=None):
        if self.buzzer:
            try:
                # Passive piezo buzzer needs PWM tone.
                # active_high=False handles low-level trigger modules.
                if hasattr(self.buzzer, "frequency"):
                    self.buzzer.frequency = tone_hz if tone_hz is not None else BUZZER_TONE_HZ
                    self.buzzer.value = duty if duty is not None else BUZZER_DUTY
                else:
                    if BUZZER_LOW_LEVEL_TRIGGER:
                        self.buzzer.off()
                    else:
                        self.buzzer.on()
            except Exception:
                pass

    def buzzer_off(self):
        if self.buzzer:
            try:
                if hasattr(self.buzzer, "value"):
                    self.buzzer.value = 0.0
                else:
                    if BUZZER_LOW_LEVEL_TRIGGER:
                        self.buzzer.on()
                    else:
                        self.buzzer.off()
            except Exception:
                pass


    def read_temp_humidity(self):
        if not self.dht:
            return None, None

        try:
            return self.dht.temperature, self.dht.humidity
        except Exception:
            return None, None

    def get_distance_cm(self):
        if not self.ultrasonic:
            return None

        try:
            return self.ultrasonic.distance * 100.0
        except Exception:
            return None

    def is_inlet_safe(self):
        distance = self.get_distance_cm()

        # 센서값을 못 읽으면 데모 편의를 위해 안전으로 처리합니다.
        # 실제 제품에서는 False로 처리하는 것이 더 안전합니다.
        if distance is None:
            return True, None

        return distance >= SAFE_DISTANCE_CM, distance

    def move_servo(self, angle):
        print(f"[Servo] {angle} degrees")

        if self.servo:
            try:
                self.servo.angle = float(angle)
                time.sleep(SERVO_MOVE_DELAY_SEC)
            except Exception as e:
                print("[WARN] Servo 이동 실패:", e)

    def move_to_category(self, category):
        angle = SERVO_ANGLE_MAP.get(category, SERVO_HOME_ANGLE)
        self.move_servo(angle)

    def reset_servo(self):
        self.move_servo(SERVO_HOME_ANGLE)

    def read_weight_kg(self):
        if not self.hx711:
            return 0.0

        try:
            return self.hx711.get_weight_kg()
        except Exception:
            return 0.0

    def tare_loadcell(self):
        if not self.hx711:
            return False

        try:
            self.hx711.tare()
            return True
        except Exception:
            return False

    def check_full(self):
        weight = self.read_weight_kg()
        return weight >= FULL_WEIGHT_THRESHOLD_KG, weight


# ============================================================
# 5. 카메라 제어
# ============================================================

class Camera:
    def __init__(self):
        self.picam2 = None
        self.usb = None

    def start(self):
        # CSI 카메라 우선 사용
        if PICAMERA_OK:
            try:
                self.picam2 = Picamera2()
                config = self.picam2.create_preview_configuration(
                    main={"size": (CAMERA_WIDTH, CAMERA_HEIGHT), "format": "RGB888"}
                )
                self.picam2.configure(config)
                self.picam2.start()
                time.sleep(1.0)
                return True
            except Exception as e:
                print("[WARN] Picamera2 시작 실패:", e)
                self.picam2 = None

        # 실패 시 USB 카메라 시도
        try:
            self.usb = cv2.VideoCapture(0)
            self.usb.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            self.usb.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            return self.usb.isOpened()
        except Exception:
            return False

    def get_frame(self):
        if self.picam2:
            frame_rgb = self.picam2.capture_array()
            return cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

        if self.usb:
            ret, frame = self.usb.read()
            if ret:
                return frame

        return None

    def stop(self):
        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
            except Exception:
                pass
            self.picam2 = None

        if self.usb:
            try:
                self.usb.release()
            except Exception:
                pass
            self.usb = None


# ============================================================
# 6. YOLO 분류
# ============================================================

class Classifier:
    def __init__(self):
        self.model = None

        if YOLO_OK and MODEL_FILE.exists():
            try:
                self.model = YOLO(str(MODEL_FILE))
                print("[INFO] YOLO model loaded:", MODEL_FILE)
            except Exception as e:
                print("[WARN] YOLO model load failed:", e)
        else:
            print("[INFO] models/best.pt not found. Manual selection mode will be used.")

    def classify(self, image_path):
        if self.model is None:
            return {
                "detected": False,
                "label": None,
                "category": None,
                "confidence": 0.0,
                "image_path": str(image_path)
            }

        try:
            results = self.model(str(image_path), imgsz=640, conf=0.25, verbose=False)
            result = results[0]

            if result.boxes is None or len(result.boxes) == 0:
                return {
                    "detected": False,
                    "label": None,
                    "category": None,
                    "confidence": 0.0,
                    "image_path": str(image_path)
                }

            best_box = None
            best_conf = -1.0

            for box in result.boxes:
                conf = float(box.conf[0])
                if conf > best_conf:
                    best_conf = conf
                    best_box = box

            cls_id = int(best_box.cls[0])
            label = str(self.model.names[cls_id])
            key = label.strip().lower()

            category = CLASS_TO_CATEGORY.get(key)

            if category is None:
                for cat in CATEGORIES:
                    if key == cat.lower():
                        category = cat
                        break

            return {
                "detected": True,
                "label": label,
                "category": category,
                "confidence": best_conf,
                "image_path": str(image_path)
            }

        except Exception as e:
            print("[WARN] YOLO inference failed:", e)
            return {
                "detected": False,
                "label": None,
                "category": None,
                "confidence": 0.0,
                "image_path": str(image_path)
            }


# ============================================================
# 7. 파일 저장, 로그, 통계
# ============================================================

def save_capture(frame):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = CAPTURE_DIR / f"{timestamp}.jpg"
    cv2.imwrite(str(path), frame)
    return path


def frame_diff(prev_frame, cur_frame):
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    cur_gray = cv2.cvtColor(cur_frame, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(prev_gray, cur_gray)
    return float(np.mean(diff))


LOG_COLUMNS = [
    "Time",
    "User ID",
    "User Total Points",
    "Predicted Category",
    "Final Category",
    "Method",
    "Confidence",
    "User Confirmed",
    "Earned Points",
    "Bin Weight",
    "Image Path",
    "Status",
]


def hash_pin(pin):
    return hashlib.sha256(str(pin).encode("utf-8")).hexdigest()


def load_users():
    if not USER_FILE.exists():
        return {}

    try:
        with open(USER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data

        return {}

    except Exception as e:
        print("[WARN] Failed to load users:", e)
        return {}


def save_users(users):
    try:
        with open(USER_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        return True

    except Exception as e:
        print("[WARN] Failed to save users:", e)
        return False


def create_user(user_id, pin):
    users = load_users()

    if user_id in users:
        return False, "ID code already exists."

    users[user_id] = {
        "id": user_id,
        "name": f"User {user_id}",
        "pin_hash": hash_pin(pin),
        "points": 0,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    ok = save_users(users)
    return ok, "User registered successfully." if ok else "Failed to save user."

def validate_user(user_id, pin):
    users = load_users()
    user = users.get(user_id)

    if not user:
        return False, None

    if user.get("pin_hash") != hash_pin(pin):
        return False, None

    return True, user


def add_user_points(user_id, points):
    users = load_users()
    user = users.get(user_id)

    if not user:
        return None

    current = int(user.get("points", 0))
    current += int(points)
    user["points"] = current
    users[user_id] = user
    save_users(users)

    return current


def get_user_points(user_id):
    users = load_users()
    user = users.get(user_id)

    if not user:
        return 0

    return int(user.get("points", 0))


def ensure_log_file_schema():
    if not LOG_FILE.exists():
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=LOG_COLUMNS)
            writer.writeheader()
        return

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            old_fields = reader.fieldnames or []
            rows = list(reader)

        if all(col in old_fields for col in LOG_COLUMNS):
            return

        migrated = []

        for row in rows:
            user_id = row.get("User ID", "Guest") or "Guest"
            earned = row.get("Earned Points", "0") or "0"
            total = row.get("User Total Points", "N/A") or "N/A"
            confirmed = row.get("User Confirmed", "") or ""
            method = row.get("Method", "") or ""

            if not method:
                method = "Auto" if confirmed.strip().lower() in ["yes", "auto", "true"] else "Manual"

            migrated.append({
                "Time": row.get("Time", ""),
                "User ID": user_id,
                "User Total Points": total,
                "Predicted Category": row.get("Predicted Category", ""),
                "Final Category": row.get("Final Category", ""),
                "Method": method,
                "Confidence": row.get("Confidence", ""),
                "User Confirmed": confirmed,
                "Earned Points": earned,
                "Bin Weight": row.get("Bin Weight", ""),
                "Image Path": row.get("Image Path", ""),
                "Status": row.get("Status", ""),
            })

        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=LOG_COLUMNS)
            writer.writeheader()
            writer.writerows(migrated)

        print("[INFO] Existing sorting_log.csv migrated to new user log schema.")

    except Exception as e:
        print("[WARN] Failed to migrate log schema:", e)


def save_log(
    predicted,
    final,
    confidence,
    confirmed,
    weight,
    image_path,
    status,
    user_id="Guest",
    earned_points=0,
    user_total_points="N/A"
):
    ensure_log_file_schema()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    confirmed_text = str(confirmed or "")

    method = "Auto" if confirmed_text.strip().lower() in ["yes", "auto", "true"] else "Manual"

    if method == "Auto":
        try:
            conf_text = f"{float(confidence):.3f}"
        except Exception:
            conf_text = "N/A"
    else:
        conf_text = "N/A"

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_COLUMNS)
        writer.writerow({
            "Time": now,
            "User ID": user_id or "Guest",
            "User Total Points": user_total_points if user_total_points is not None else "N/A",
            "Predicted Category": predicted or "",
            "Final Category": final or "",
            "Method": method,
            "Confidence": conf_text,
            "User Confirmed": confirmed or "",
            "Earned Points": str(earned_points),
            "Bin Weight": f"{weight:.3f}kg" if isinstance(weight, (int, float)) else str(weight),
            "Image Path": image_path or "",
            "Status": status,
        })

def clear_logs():
    if LOG_FILE.exists():
        LOG_FILE.unlink()


def today_stats():
    stats = {cat: 0 for cat in CATEGORIES}
    today = datetime.now().strftime("%Y-%m-%d")

    if not LOG_FILE.exists():
        return stats

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            if row.get("Time", "").startswith(today):
                cat = row.get("Final Category", "")
                if cat in stats:
                    stats[cat] += 1

    return stats


# ============================================================
# 8. LCD UI 애플리케이션
# ============================================================

class App:
    def __init__(self):
        self.hw = Hardware()
        self.classifier = Classifier()

        self.root = tk.Tk()
        self.root.title("AIoT Smart Recycling System")
        self.root.geometry(f"{LCD_WIDTH}x{LCD_HEIGHT}")
        self.root.configure(bg="#eef3f8")

        if FULLSCREEN:
            self.root.attributes("-fullscreen", True)

        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))

        # Play a short buzzer click sound whenever a Tkinter Button is released.
        self.root.bind_all("<ButtonRelease-1>", self.play_button_click_sound, add="+")

        # Start periodic motion sensor screen power monitor.
        self.root.after(MOTION_CHECK_INTERVAL_MS, self.motion_monitor_tick)

        self.action = None
        self.photo = None

        # User session state
        self.current_user_id = None
        self.current_user_name = None
        self.is_guest = False
        self.last_activity_at = time.time()
        self.in_admin_mode = False

        # Motion-based screen power state
        self.screen_is_off = False
        self.screen_blank_overlay = None
        self.last_motion_at = time.time()
        self.last_motion_debug_at = 0.0

        # Fire alarm runtime state
        self.fire_high_since = None
        self.fire_alarm_active = False
        self.last_fire_check_at = 0.0

        self.font_title = font.Font(family="DejaVu Sans", size=22, weight="bold")
        self.font_big = font.Font(family="DejaVu Sans", size=24, weight="bold")
        self.font_normal = font.Font(family="DejaVu Sans", size=15)
        self.font_button = font.Font(family="DejaVu Sans", size=14, weight="bold")
        self.font_small = font.Font(family="DejaVu Sans", size=10)

    def show_screen_blank_overlay(self):
        try:
            if self.screen_blank_overlay is not None:
                return

            overlay = tk.Toplevel(self.root)
            overlay.configure(bg="black")
            overlay.overrideredirect(True)
            overlay.attributes("-fullscreen", True)
            overlay.attributes("-topmost", True)

            try:
                overlay.geometry(
                    f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0"
                )
            except Exception:
                pass

            # Motion이 다시 감지되거나 화면을 터치하면 복구될 수 있도록 클릭 이벤트도 연결합니다.
            overlay.bind("<ButtonPress-1>", lambda e: self.set_display_power(True))
            overlay.bind("<Key>", lambda e: self.set_display_power(True))

            self.screen_blank_overlay = overlay
            self.screen_is_off = True
            print("[DISPLAY] OFF by black overlay fallback")

        except Exception as e:
            print("[WARN] Failed to show black overlay:", e)

    def hide_screen_blank_overlay(self):
        try:
            if self.screen_blank_overlay is not None:
                self.screen_blank_overlay.destroy()
                self.screen_blank_overlay = None

            self.screen_is_off = False
            print("[DISPLAY] ON / black overlay removed")

        except Exception as e:
            print("[WARN] Failed to hide black overlay:", e)
            self.screen_blank_overlay = None
            self.screen_is_off = False


    def set_display_power(self, on):
        env = dict(os.environ)
        env.setdefault("DISPLAY", ":0")
        env.setdefault("XAUTHORITY", "/home/pi/.Xauthority")

        if on:
            commands = [
                ["vcgencmd", "display_power", "1"],
                ["xset", "s", "reset"],
                ["xset", "dpms", "force", "on"],
            ]
        else:
            commands = [
                ["vcgencmd", "display_power", "0"],
                ["xset", "s", "activate"],
                ["xset", "dpms", "force", "off"],
            ]

        success = False

        for cmd in commands:
            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                    timeout=1.5
                )

                if result.returncode == 0:
                    success = True

            except Exception:
                pass

        if on:
            self.hide_screen_blank_overlay()

            if success:
                print("[DISPLAY] ON by system command")

            return True

        # OFF 시도 성공 여부와 관계없이, 현재 환경에서는 실제 OFF가 안 될 수 있으므로
        # 검은 오버레이를 fallback으로 항상 표시합니다.
        self.show_screen_blank_overlay()

        if success:
            print("[DISPLAY] OFF command sent, overlay also applied")
        else:
            print("[DISPLAY] OFF command failed, overlay fallback applied")

        return True


    def motion_monitor_tick(self):
        try:
            if not USE_MOTION_SENSOR:
                return

            now = time.time()

            # Fire Alarm 화면에서는 안전상 화면이 꺼지지 않도록 유지합니다.
            if getattr(self, "fire_alarm_active", False):
                self.last_motion_at = now

                if getattr(self, "screen_is_off", False):
                    self.set_display_power(True)

                return

            detected = self.hw.motion_detected()

            if now - getattr(self, "last_motion_debug_at", 0.0) >= 5.0:
                idle_sec = now - getattr(self, "last_motion_at", now)
                print(
                    f"[MOTION] detected={detected} "
                    f"idle={idle_sec:.1f}s "
                    f"screen_off={getattr(self, 'screen_is_off', False)}"
                )
                self.last_motion_debug_at = now

            if detected:
                self.last_motion_at = now

                if getattr(self, "screen_is_off", False):
                    self.set_display_power(True)

            else:
                idle_sec = now - getattr(self, "last_motion_at", now)

                if idle_sec >= MOTION_SCREEN_OFF_SEC and not getattr(self, "screen_is_off", False):
                    self.set_display_power(False)

        except Exception as e:
            print("[WARN] motion monitor error:", e)

        finally:
            try:
                self.root.after(MOTION_CHECK_INTERVAL_MS, self.motion_monitor_tick)
            except Exception:
                pass


    def play_button_click_sound(self, event=None):
        try:
            if not USE_BUZZER:
                return

            # Only play sound for actual Tkinter Button widgets.
            if event is not None and not isinstance(event.widget, tk.Button):
                return

            # Do not disturb the fire alarm buzzer pattern.
            if getattr(self, "fire_alarm_active", False):
                return

            if not hasattr(self, "hw") or self.hw is None:
                return

            buzzer = getattr(self.hw, "buzzer", None)

            if buzzer is None:
                return

            # Short click tone.
            if hasattr(buzzer, "frequency"):
                try:
                    buzzer.frequency = BUZZER_CLICK_HZ
                except Exception:
                    pass

            self.hw.buzzer_on()

            try:
                self.root.after(BUZZER_CLICK_MS, self.hw.buzzer_off)
            except Exception:
                time.sleep(BUZZER_CLICK_MS / 1000.0)
                self.hw.buzzer_off()

        except Exception:
            pass


    def clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def set_action(self, action):
        print(f"[UI ACTION] {action}")
        self.touch_session()
        self.action = action



    def contrast_button_color(self, text):
        t = str(text or "").lower()

        # Category buttons
        if "plastic" in t:
            return "#1d4ed8"      # dark blue
        if "can" in t or "metal" in t:
            return "#374151"      # dark gray
        if "paper" in t:
            return "#92400e"      # dark amber/brown
        if "glass" in t:
            return "#0f766e"      # dark teal
        if "general" in t or "waste" in t:
            return "#991b1b"      # dark red

        # Main positive actions
        if t in ["sort", "start", "yes", "done", "try again", "retry", "confirm"]:
            return "#15803d"      # dark green

        # Manual / information actions
        if "manual" in t or "select" in t or "statistics" in t or "admin" in t:
            return "#1d4ed8"      # dark blue

        # Cancel / negative actions
        if "cancel" in t or t == "no" or "back" in t:
            return "#b91c1c"      # dark red

        # Test / utility buttons
        if "test" in t or "check" in t or "reset" in t:
            return "#4338ca"      # dark indigo

        # Default button color
        return "#334155"          # dark slate

    def apply_button_contrast_recursive(self, widget=None):
        if widget is None:
            widget = self.root

        try:
            children = widget.winfo_children()
        except Exception:
            return

        for child in children:
            try:
                if isinstance(child, tk.Button):
                    text = child.cget("text")
                    bg = self.contrast_button_color(text)

                    if not hasattr(self, "_contrast_button_font"):
                        self._contrast_button_font = font.Font(
                            family="DejaVu Sans",
                            size=14,
                            weight="bold"
                        )

                    child.configure(
                        bg=bg,
                        fg="white",
                        activebackground=bg,
                        activeforeground="white",
                        disabledforeground="#e5e7eb",
                        font=self._contrast_button_font,
                        relief="flat",
                        bd=0,
                        highlightthickness=0,
                        cursor="hand2"
                    )
            except Exception:
                pass

            self.apply_button_contrast_recursive(child)

    def wait_action(self):
        self.action = None

        while self.action is None:
            self.apply_button_contrast_recursive()
            self.root.update()

            try:
                if hasattr(self, "check_fire_alarm_trigger"):
                    self.check_fire_alarm_trigger()
            except Exception:
                pass

            if self.check_session_timeout():
                self.action = "AUTO_LOGOUT"
                break

            time.sleep(0.03)

        return self.action


    def button(self, parent, text, action, width=15, height=2, bg="#1d4ed8", fg="white"):
        return tk.Button(
            parent,
            text=text,
            width=width,
            height=height,
            font=font.Font(family="DejaVu Sans", size=14, weight="bold"),
            bg=bg,
            fg=fg,
            activebackground=bg,
            activeforeground=fg,
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=lambda: self.set_action(action)
        )
    def message_screen(self, title, msg, buttons):
        self.clear()

        tk.Label(self.root, text=title, font=self.font_title).pack(pady=30)
        tk.Label(self.root, text=msg, font=self.font_normal, justify="center").pack(pady=20)

        frame = tk.Frame(self.root)
        frame.pack(pady=20)

        for text, action, color in buttons:
            self.button(frame, text, action, bg=color).pack(side="left", padx=10)

        return self.wait_action()




    def main_screen(self):
        self.clear()
        self.root.configure(bg="#edf4f8")

        temp, humid = self.hw.read_temp_humidity()
        full, weight = self.hw.check_full()

        dark = "#0f172a"
        muted = "#475569"
        card = "#ffffff"
        page_bg = "#edf4f8"

        # Header
        header = tk.Frame(self.root, bg=dark, height=62)
        header.pack(fill="x")
        header.pack_propagate(False)

        title_box = tk.Frame(header, bg=dark)
        title_box.pack(side="left", padx=18, pady=8)

        tk.Label(
            title_box,
            text="AIoT Smart Recycling System",
            font=font.Font(family="DejaVu Sans", size=19, weight="bold"),
            bg=dark,
            fg="white"
        ).pack(anchor="w")

        tk.Label(
            title_box,
            text="Smart Recycling Kiosk",
            font=self.font_small,
            bg=dark,
            fg="#cbd5e1"
        ).pack(anchor="w")

        header_actions = tk.Frame(header, bg=dark)
        header_actions.pack(side="right", padx=12, pady=10)

        tk.Button(
            header_actions,
            text="Logout",
            font=self.font_small,
            bg="#b91c1c",
            fg="white",
            activebackground="#991b1b",
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=10,
            pady=6,
            highlightthickness=0,
            cursor="hand2",
            command=lambda: self.set_action("LOGOUT")
        ).pack(side="right", padx=(6, 0))

        tk.Button(
            header_actions,
            text="Admin Mode",
            font=self.font_small,
            bg="#1d4ed8",
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
            highlightthickness=0,
            cursor="hand2",
            command=lambda: self.set_action("ADMIN")
        ).pack(side="right")

        self.home_clock_label = tk.Label(
            header,
            text="",
            font=font.Font(family="DejaVu Sans", size=10),
            bg=dark,
            fg="#cbd5e1",
            justify="right"
        )
        self.home_clock_label.pack(side="right", padx=(0, 8), pady=12)

        def update_home_clock():
            try:
                if self.home_clock_label.winfo_exists():
                    self.home_clock_label.config(
                        text=datetime.now().strftime("%Y-%m-%d\n%H:%M")
                    )
                    self.root.after(1000, update_home_clock)
            except Exception:
                pass

        update_home_clock()

        # Body
        body = tk.Frame(self.root, bg=page_bg)
        body.pack(fill="both", expand=True, padx=18, pady=12)

        # Main guide card
        main_card = tk.Frame(body, bg=card, highlightbackground="#d8e3eb", highlightthickness=1, bd=0)
        main_card.pack(fill="x")

        title_row = tk.Frame(main_card, bg=card)
        title_row.pack(fill="x", padx=18, pady=(14, 3))

        tk.Label(
            title_row,
            text="Ready to sort your waste?",
            font=font.Font(family="DejaVu Sans", size=22, weight="bold"),
            bg=card,
            fg=dark
        ).pack(side="left", anchor="w")

        self.home_recycle_icon = tk.Label(
            title_row,
            text="♻",
            font=font.Font(family="DejaVu Sans", size=42, weight="bold"),
            bg=card,
            fg="#16a34a"
        )
        self.home_recycle_icon.pack(side="right", padx=(10, 4))

        tk.Label(
            main_card,
            text="Place the waste on the tray and press the Sort button.",
            font=font.Font(family="DejaVu Sans", size=12),
            bg=card,
            fg=muted,
            justify="left"
        ).pack(anchor="w", padx=18)

        tk.Label(
            main_card,
            text="The camera captures automatically when the waste is stable.",
            font=font.Font(family="DejaVu Sans", size=12),
            bg=card,
            fg=muted,
            justify="left"
        ).pack(anchor="w", padx=18, pady=(0, 12))

        # Status cards
        status_row = tk.Frame(body, bg=page_bg)
        status_row.pack(fill="x", pady=(10, 10))

        def small_card(parent, title, value, color):
            c = tk.Frame(parent, bg=card, highlightbackground="#d8e3eb", highlightthickness=1, bd=0)
            c.pack(side="left", expand=True, fill="x", padx=5)

            tk.Frame(c, bg=color, height=5).pack(fill="x")

            tk.Label(
                c,
                text=title,
                font=self.font_small,
                bg=card,
                fg=muted
            ).pack(anchor="w", padx=12, pady=(7, 0))

            tk.Label(
                c,
                text=value,
                font=font.Font(family="DejaVu Sans", size=16, weight="bold"),
                bg=card,
                fg=dark
            ).pack(anchor="w", padx=12, pady=(2, 8))

        temp_text = "N/A" if temp is None else f"{temp:.1f}°C"
        humid_text = "N/A" if humid is None else f"{humid:.1f}%"
        bin_text = "FULL" if full else "READY"

        small_card(status_row, "Temperature", temp_text, "#b45309")
        small_card(status_row, "Humidity", humid_text, "#0e7490")
        small_card(status_row, "Bin Status", bin_text, "#b91c1c" if full else "#15803d")

        # Recycling impact card
        impact_card = tk.Frame(body, bg="#ecfdf5", highlightbackground="#bbf7d0", highlightthickness=1, bd=0)
        impact_card.pack(fill="x", pady=(0, 10))

        tk.Label(
            impact_card,
            text="Recycling Impact",
            font=font.Font(family="DejaVu Sans", size=14, weight="bold"),
            bg="#ecfdf5",
            fg="#166534"
        ).pack(anchor="w", padx=16, pady=(8, 0))

        tk.Label(
            impact_card,
            text="Every recycled item helps reduce waste, save resources, and keep the Earth cleaner.",
            font=font.Font(family="DejaVu Sans", size=12),
            bg="#ecfdf5",
            fg="#166534",
            justify="left",
            wraplength=720
        ).pack(anchor="w", padx=16, pady=(2, 8))

        # Action card
        action_card = tk.Frame(body, bg=card, highlightbackground="#d8e3eb", highlightthickness=1, bd=0)
        action_card.pack(fill="both", expand=True)

        tk.Label(
            action_card,
            text=self.current_user_display_text(),
            font=font.Font(family="DejaVu Sans", size=12, weight="bold"),
            bg=card,
            fg="#1d4ed8" if not self.is_guest else "#475569"
        ).pack(pady=(10, 0))

        tk.Label(
            action_card,
            text=f"Current Load: {weight:.3f}kg",
            font=font.Font(family="DejaVu Sans", size=13),
            bg=card,
            fg=muted
        ).pack(pady=(4, 2))

        tk.Label(
            action_card,
            text="Choose an action to continue",
            font=font.Font(family="DejaVu Sans", size=16, weight="bold"),
            bg=card,
            fg=dark
        ).pack(pady=(0, 8))

        btn_row = tk.Frame(action_card, bg=card)
        btn_row.pack(pady=(4, 8))

        self.button(btn_row, "Sort", "START", width=19, height=2, bg="#15803d").pack(side="left", padx=14)

        if self.current_user_id and not self.is_guest:
            self.button(btn_row, "My Log", "USER_LOG", width=19, height=2, bg="#1d4ed8").pack(side="left", padx=14)

        if full:
            tk.Label(
                action_card,
                text="Warning: Trash bin is full. Please empty the bin.",
                font=font.Font(family="DejaVu Sans", size=12, weight="bold"),
                bg=card,
                fg="#b91c1c"
            ).pack(pady=(4, 0))
        else:
            tk.Label(
                action_card,
                text="Tip: Keep the waste still for automatic camera capture.",
                font=self.font_small,
                bg=card,
                fg="#475569"
            ).pack(pady=(4, 0))

        return self.wait_action()
    def auto_capture(self):
        self.clear()
        self.root.configure(bg="#edf4f8")
        self.action = None

        dark = "#edf4f8"
        panel = "#ffffff"
        text_light = "#0f172a"
        muted = "#475569"
        green = "#22c55e"

        # Header
        header = tk.Frame(self.root, bg=dark, height=44)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Camera Preview",
            font=font.Font(family="DejaVu Sans", size=18, weight="bold"),
            bg=dark,
            fg="#0f172a"
        ).pack(side="left", padx=18, pady=8)

        tk.Button(
            header,
            text="Cancel",
            font=font.Font(family="DejaVu Sans", size=12, weight="bold"),
            bg="#b91c1c",
            fg="white",
            activebackground="#991b1b",
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=14,
            pady=5,
            highlightthickness=0,
            cursor="hand2",
            command=lambda: self.set_action("CANCEL")
        ).pack(side="right", padx=14, pady=7)

        # Main camera area
        body = tk.Frame(self.root, bg=dark)
        body.pack(fill="both", expand=True, padx=14, pady=(8, 10))

        preview_card = tk.Frame(body, bg=panel, highlightbackground="#cbd5e1", highlightthickness=1, bd=0)
        preview_card.pack(fill="both", expand=True)

        image_label = tk.Label(preview_card, bg="#f8fafc")
        image_label.pack(pady=(8, 6))

        progress_canvas = tk.Canvas(
            preview_card,
            width=690,
            height=24,
            bg="#e2e8f0",
            highlightthickness=0
        )
        progress_canvas.pack(pady=(0, 4))

        status_label = tk.Label(
            preview_card,
            text="Stability: 0%  |  Keep the waste still for automatic capture.",
            font=font.Font(family="DejaVu Sans", size=12),
            bg=panel,
            fg=text_light
        )
        status_label.pack(pady=(0, 4))

        hint_label = tk.Label(
            preview_card,
            text="Green box: estimated waste area based on motion and contour detection.",
            font=font.Font(family="DejaVu Sans", size=10),
            bg=panel,
            fg=muted
        )
        hint_label.pack(pady=(0, 6))

        def draw_progress(percent):
            percent = max(0, min(100, int(percent)))
            w = 690
            h = 24
            fill_w = int(w * percent / 100)
            progress_canvas.delete("all")
            progress_canvas.create_rectangle(0, 0, w, h, fill="#cbd5e1", outline="")
            progress_canvas.create_rectangle(0, 0, fill_w, h, fill=green, outline="")
            progress_canvas.create_text(
                w // 2,
                h // 2,
                text=f"{percent}%",
                fill="#0f172a",
                font=("DejaVu Sans", 11, "bold")
            )

        def find_object_box(frame_rgb, prev_gray_for_box):
            try:
                gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
                gray = cv2.GaussianBlur(gray, (5, 5), 0)

                masks = []

                if prev_gray_for_box is not None:
                    diff = cv2.absdiff(prev_gray_for_box, gray)
                    _, motion_mask = cv2.threshold(diff, 14, 255, cv2.THRESH_BINARY)
                    motion_mask = cv2.dilate(motion_mask, None, iterations=3)
                    masks.append(motion_mask)

                edges = cv2.Canny(gray, 50, 150)
                edges = cv2.dilate(edges, None, iterations=2)
                masks.append(edges)

                best_box = None
                best_area = 0
                frame_area = frame_rgb.shape[0] * frame_rgb.shape[1]

                for mask in masks:
                    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    for cnt in contours:
                        area = cv2.contourArea(cnt)
                        if area < 1200:
                            continue
                        if area > frame_area * 0.65:
                            continue
                        x, y, w, h = cv2.boundingRect(cnt)
                        if w < 35 or h < 35:
                            continue
                        if area > best_area:
                            best_area = area
                            best_box = (x, y, w, h)

                return best_box
            except Exception:
                return None

        # Camera open
        picam2 = None
        cap = None
        use_picamera2 = False

        try:
            from picamera2 import Picamera2
            picam2 = Picamera2()
            config = picam2.create_preview_configuration(
                main={
                    "size": (CAMERA_WIDTH, CAMERA_HEIGHT),
                    "format": "RGB888"
                }
            )
            picam2.configure(config)
            picam2.start()
            use_picamera2 = True
            time.sleep(0.5)
        except Exception as e:
            print("[Camera] Picamera2 failed:", e)
            try:
                if picam2 is not None:
                    try:
                        picam2.stop()
                    except Exception:
                        pass
                    try:
                        picam2.close()
                    except Exception:
                        pass
            except Exception:
                pass
            picam2 = None

        if not use_picamera2:
            self.message_screen(
                "Camera Failed",
                "Cannot open the camera. Please wait a few seconds and try again.",
                [("Back", "CANCEL", "#b91c1c")]
            )
            return None

        prev_gray = None
        stable_frames = 0
        required_stable_frames = max(8, int(CAMERA_FPS * STABLE_TIME_SEC))
        start_time = time.time()
        saved_path = None

        try:
            while True:
                try:
                    if hasattr(self, "apply_button_contrast_recursive"):
                        self.apply_button_contrast_recursive()
                except Exception:
                    pass

                self.root.update()

                if self.action == "CANCEL":
                    return None

                if use_picamera2:
                    frame_rgb = picam2.capture_array()
                else:
                    ok, frame_bgr = cap.read()
                    if not ok:
                        continue
                    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

                gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
                gray = cv2.GaussianBlur(gray, (5, 5), 0)

                if prev_gray is None:
                    diff_value = 999.0
                    stable_frames = 0
                    stability_percent = 0
                else:
                    diff = cv2.absdiff(prev_gray, gray)
                    diff_value = float(np.mean(diff))

                    if diff_value < FRAME_DIFF_THRESHOLD:
                        stable_frames += 1
                    else:
                        stable_frames = max(0, stable_frames - 3)

                    stability_percent = int(100 * stable_frames / required_stable_frames)
                    stability_percent = max(0, min(100, stability_percent))

                display_frame = frame_rgb.copy()

                box = find_object_box(display_frame, prev_gray)
                if box is not None:
                    x, y, w, h = box
                    cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 255, 0), 3)
                    cv2.putText(
                        display_frame,
                        "Estimated waste area",
                        (x, max(24, y - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.65,
                        (0, 255, 0),
                        2,
                        cv2.LINE_AA
                    )

                draw_progress(stability_percent)
                status_label.configure(
                    text=f"Stability: {stability_percent}%  |  Motion score: {diff_value:.2f}"
                )

                # Bigger preview area
                img = Image.fromarray(display_frame)
                max_w = 720
                max_h = 335
                img_w, img_h = img.size
                scale = min(max_w / img_w, max_h / img_h)
                new_w = int(img_w * scale)
                new_h = int(img_h * scale)

                try:
                    resample = Image.Resampling.LANCZOS
                except Exception:
                    resample = Image.LANCZOS

                img = img.resize((new_w, new_h), resample)
                photo = ImageTk.PhotoImage(img)
                image_label.configure(image=photo)
                image_label.image = photo

                if stability_percent >= 100:
                    capture_dir = Path("captures")
                    capture_dir.mkdir(exist_ok=True)
                    filename = "capture_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg"
                    saved_path = capture_dir / filename
                    cv2.imwrite(str(saved_path), cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR))
                    return str(saved_path)

                if time.time() - start_time > STABILITY_TIMEOUT_SEC:
                    print("[Camera] Stability timeout.")
                    return None

                prev_gray = gray
                time.sleep(max(0.01, 1.0 / max(1, CAMERA_FPS)))

        finally:
            try:
                if picam2 is not None:
                    try:
                        picam2.stop()
                    except Exception:
                        pass
                    try:
                        picam2.close()
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                import gc
                gc.collect()
            except Exception:
                pass

            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass
    def result_screen(self, label, category, conf, image_path=None):
        self.clear()

        tk.Label(
            self.root,
            text="Classification Result",
            font=self.font_title,
            fg="#0f172a"
        ).pack(pady=(12, 6))

        # Show captured image from camera
        if image_path is not None:
            try:
                img = Image.open(image_path)
                img.thumbnail((300, 170))

                photo = ImageTk.PhotoImage(img)
                self.result_photo = photo

                tk.Label(
                    self.root,
                    image=photo,
                    bg="#eef3f8"
                ).pack(pady=(2, 6))

            except Exception as e:
                print("[WARN] Result image preview failed:", e)

        info_text = (
            f"Detected: {label}   |   "
            f"Confidence: {conf * 100:.1f}%"
        )

        tk.Label(
            self.root,
            text=info_text,
            font=font.Font(family="DejaVu Sans", size=14),
            fg="#475569",
            justify="center"
        ).pack(pady=(2, 8))

        question_frame = tk.Frame(self.root, bg="#eef3f8")
        question_frame.pack(pady=(4, 14))

        question_font = font.Font(family="DejaVu Sans", size=28, weight="bold")

        tk.Label(
            question_frame,
            text="Is it ",
            font=question_font,
            bg="#eef3f8",
            fg="#111827"
        ).pack(side="left")

        tk.Label(
            question_frame,
            text=str(category),
            font=question_font,
            bg="#eef3f8",
            fg="#2563eb"
        ).pack(side="left")

        tk.Label(
            question_frame,
            text="?",
            font=question_font,
            bg="#eef3f8",
            fg="#111827"
        ).pack(side="left")

        frame = tk.Frame(self.root, bg="#eef3f8")
        frame.pack(pady=6)

        self.button(frame, "Yes", "YES", bg="#bbf7d0").pack(side="left", padx=15)
        self.button(frame, "No", "NO", bg="#fecaca").pack(side="left", padx=15)

        return self.wait_action()
    def manual_screen(self, title="Manual Selection", msg="Please select the correct category."):
        self.clear()

        tk.Label(self.root, text=title, font=self.font_title).pack(pady=20)
        tk.Label(self.root, text=msg, font=self.font_normal).pack(pady=10)

        grid = tk.Frame(self.root)
        grid.pack(pady=10)

        for i, cat in enumerate(CATEGORIES):
            self.button(grid, cat, cat, width=18, bg="#fde68a").grid(row=i // 2, column=i % 2, padx=10, pady=8)

        self.button(self.root, "Cancel", "CANCEL", width=16, height=1, bg="#fecaca").pack(pady=10)

        return self.wait_action()

    def safety_warning(self, distance):
        self.clear()
        self.root.configure(bg="#eef3f8")

        page_bg = "#eef3f8"
        card = "#ffffff"
        dark = "#0f172a"
        muted = "#475569"
        red = "#dc2626"

        tk.Label(
            self.root,
            text="Safety Warning",
            font=self.font_title,
            bg=page_bg,
            fg=dark
        ).pack(pady=(16, 8))

        warn_card = tk.Frame(
            self.root,
            bg=card,
            highlightbackground="#d8e3eb",
            highlightthickness=1,
            bd=0
        )
        warn_card.pack(fill="both", expand=True, padx=28, pady=(4, 18))

        # Exclamation mark icon-like display
        icon_wrap = tk.Frame(warn_card, bg=card)
        icon_wrap.pack(pady=(22, 10))

        tk.Label(
            icon_wrap,
            text="!",
            font=font.Font(family="DejaVu Sans", size=42, weight="bold"),
            bg=card,
            fg=red,
            width=2,
            height=1
        ).pack()

        tk.Label(
            warn_card,
            text="Please remove your hand or any foreign object from the waste bin inlet.",
            font=font.Font(family="DejaVu Sans", size=15, weight="bold"),
            bg=card,
            fg=red,
            wraplength=700,
            justify="center"
        ).pack(padx=22, pady=(4, 10))

        tk.Label(
            warn_card,
            text="Sorting will start after the inlet is safe.",
            font=font.Font(family="DejaVu Sans", size=12),
            bg=card,
            fg=muted
        ).pack(pady=(0, 10))

        dist_text = "Distance: N/A" if distance is None else f"Distance: {distance:.1f} cm"
        tk.Label(
            warn_card,
            text=dist_text,
            font=font.Font(family="DejaVu Sans", size=13, weight="bold"),
            bg=card,
            fg=dark
        ).pack(pady=(0, 18))

        btn_row = tk.Frame(warn_card, bg=card)
        btn_row.pack(pady=(0, 20))

        self.button(btn_row, "Retry", "RETRY", bg="#fde68a").pack(side="left", padx=14)
        self.button(btn_row, "Cancel", "CANCEL", bg="#fecaca").pack(side="left", padx=14)

        return self.wait_action()
    def servo_preparing(self, category):
        self.clear()
        tk.Label(self.root, text="Preparing the sorting path.", font=self.font_title).pack(pady=70)
        tk.Label(self.root, text=f"Category: {category}\nPlease wait.", font=self.font_normal).pack(pady=20)
        self.apply_button_contrast_recursive()
        self.root.update()


    def disposal_screen(self, category):
        self.clear()
        self.root.configure(bg="#edf4f8")

        dark = "#0f172a"
        muted = "#475569"
        card = "#ffffff"

        header = tk.Frame(self.root, bg=dark, height=58)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Dispose the Waste",
            font=font.Font(family="DejaVu Sans", size=20, weight="bold"),
            bg=dark,
            fg="white"
        ).pack(side="left", padx=18, pady=12)

        body = tk.Frame(self.root, bg="#edf4f8")
        body.pack(fill="both", expand=True, padx=18, pady=14)

        top_card = tk.Frame(body, bg=card, highlightbackground="#d8e3eb", highlightthickness=1, bd=0)
        top_card.pack(fill="x")

        tk.Label(
            top_card,
            text="Please put the waste into the machine.",
            font=font.Font(family="DejaVu Sans", size=19, weight="bold"),
            bg=card,
            fg=dark
        ).pack(anchor="w", padx=18, pady=(14, 4))

        tk.Label(
            top_card,
            text=f"Selected Category: {category}",
            font=font.Font(family="DejaVu Sans", size=14, weight="bold"),
            bg=card,
            fg="#1d4ed8"
        ).pack(anchor="w", padx=18, pady=(0, 4))

        tk.Label(
            top_card,
            text="Warning: Do not put your fingers or any foreign objects into the waste bin inlet while the motor is operating.",
            font=font.Font(family="DejaVu Sans", size=12, weight="bold"),
            bg=card,
            fg="#dc2626",
            justify="left",
            wraplength=720
        ).pack(anchor="w", padx=18, pady=(0, 14))

        guide_card = tk.Frame(body, bg=card, highlightbackground="#d8e3eb", highlightthickness=1, bd=0)
        guide_card.pack(fill="x", pady=12)

        tk.Label(
            guide_card,
            text="Proper disposal guide",
            font=font.Font(family="DejaVu Sans", size=16, weight="bold"),
            bg=card,
            fg=dark
        ).pack(anchor="w", padx=18, pady=(12, 4))

        items = CATEGORY_GUIDE.get(category, ["Follow local recycling rules."])
        guide_text = chr(10).join([f"- {x}" for x in items])

        tk.Label(
            guide_card,
            text=guide_text,
            font=font.Font(family="DejaVu Sans", size=12),
            bg=card,
            fg=muted,
            justify="left",
            wraplength=700
        ).pack(anchor="w", padx=20, pady=(0, 12))

        btn_area = tk.Frame(body, bg="#edf4f8")
        btn_area.pack(fill="x", pady=4)

        self.button(btn_area, "Done", "DONE", width=18, height=2, bg="#15803d").pack()

        return self.wait_action()
    def stats_screen(self):
        stats = today_stats()
        self.clear()

        tk.Label(self.root, text="Today’s Recycling Summary", font=self.font_title).pack(pady=25)

        text = "\n".join([f"{cat}: {stats[cat]}" for cat in CATEGORIES])
        tk.Label(self.root, text=text, font=font.Font(family="DejaVu Sans", size=20), justify="left").pack(pady=25)

        self.button(self.root, "Back", "BACK", bg="#dbeafe").pack(pady=10)
        return self.wait_action()

    def admin_password_screen(self):
        self.clear()
        self.root.configure(bg="#edf4f8")

        dark = "#0f172a"
        muted = "#475569"
        card = "#ffffff"
        page_bg = "#edf4f8"

        tk.Label(
            self.root,
            text="Admin Authentication",
            font=font.Font(family="DejaVu Sans", size=22, weight="bold"),
            bg=page_bg,
            fg=dark
        ).pack(pady=(22, 8))

        panel = tk.Frame(
            self.root,
            bg=card,
            highlightbackground="#cbd5e1",
            highlightthickness=1,
            bd=0
        )
        panel.pack(padx=28, pady=8, fill="both", expand=True)

        tk.Label(
            panel,
            text="Enter administrator password.",
            font=font.Font(family="DejaVu Sans", size=14, weight="bold"),
            bg=card,
            fg=dark
        ).pack(pady=(18, 4))

        tk.Label(
            panel,
            text="Password is required to access Admin Mode.",
            font=font.Font(family="DejaVu Sans", size=11),
            bg=card,
            fg=muted
        ).pack(pady=(0, 12))

        display = tk.Label(
            panel,
            text="----",
            font=font.Font(family="DejaVu Sans", size=28, weight="bold"),
            bg="#f8fafc",
            fg=dark,
            width=12,
            height=1,
            relief="solid",
            bd=1
        )
        display.pack(pady=(0, 8))

        error_label = tk.Label(
            panel,
            text="",
            font=font.Font(family="DejaVu Sans", size=11, weight="bold"),
            bg=card,
            fg="#dc2626"
        )
        error_label.pack(pady=(0, 8))

        state = {"value": ""}

        def refresh_display():
            if state["value"]:
                display.config(text="●" * len(state["value"]))
            else:
                display.config(text="----")

        def add_digit(digit):
            if len(state["value"]) < 8:
                state["value"] += str(digit)
                error_label.config(text="")
                refresh_display()

        def delete_digit():
            state["value"] = state["value"][:-1]
            error_label.config(text="")
            refresh_display()

        def clear_password():
            state["value"] = ""
            error_label.config(text="")
            refresh_display()

        def submit_password():
            if state["value"] == ADMIN_PASSWORD:
                self.set_action("AUTH_OK")
            else:
                state["value"] = ""
                error_label.config(text="Incorrect password. Please try again.")
                refresh_display()

        keypad = tk.Frame(panel, bg=card)
        keypad.pack(pady=(0, 12))

        def make_key(parent, text, command, bg="#334155", fg="white", width=7):
            return tk.Button(
                parent,
                text=text,
                width=width,
                height=2,
                font=font.Font(family="DejaVu Sans", size=14, weight="bold"),
                bg=bg,
                fg=fg,
                activebackground=bg,
                activeforeground=fg,
                relief="flat",
                bd=0,
                highlightthickness=0,
                cursor="hand2",
                command=command
            )

        keys = [
            [("1", lambda: add_digit("1")), ("2", lambda: add_digit("2")), ("3", lambda: add_digit("3"))],
            [("4", lambda: add_digit("4")), ("5", lambda: add_digit("5")), ("6", lambda: add_digit("6"))],
            [("7", lambda: add_digit("7")), ("8", lambda: add_digit("8")), ("9", lambda: add_digit("9"))],
            [("Clear", clear_password), ("0", lambda: add_digit("0")), ("Del", delete_digit)],
        ]

        for r, row in enumerate(keys):
            for c, item in enumerate(row):
                key_text, cmd = item
                make_key(keypad, key_text, cmd).grid(row=r, column=c, padx=6, pady=6)

        bottom = tk.Frame(panel, bg=card)
        bottom.pack(pady=(0, 14))

        make_key(
            bottom,
            "Cancel",
            lambda: self.set_action("AUTH_CANCEL"),
            bg="#b91c1c",
            width=10
        ).pack(side="left", padx=8)

        make_key(
            bottom,
            "OK",
            submit_password,
            bg="#15803d",
            width=10
        ).pack(side="left", padx=8)

        return self.wait_action()


    def admin_ultrasonic_safety_test(self):
        self.clear()
        self.root.configure(bg="#edf4f8")
        self.action = None

        dark = "#0f172a"
        muted = "#475569"
        card = "#ffffff"
        page_bg = "#edf4f8"
        red = "#dc2626"
        green = "#15803d"
        amber = "#b45309"

        tk.Label(
            self.root,
            text="Ultrasonic Safety Test",
            font=self.font_title,
            bg=page_bg,
            fg=dark
        ).pack(pady=(18, 6))

        panel = tk.Frame(
            self.root,
            bg=card,
            highlightbackground="#cbd5e1",
            highlightthickness=1,
            bd=0
        )
        panel.pack(fill="both", expand=True, padx=28, pady=(4, 18))

        tk.Label(
            panel,
            text="Place your hand or an object near the ultrasonic sensor.",
            font=font.Font(family="DejaVu Sans", size=14, weight="bold"),
            bg=card,
            fg=dark,
            wraplength=700,
            justify="center"
        ).pack(pady=(22, 8))

        tk.Label(
            panel,
            text=f"If the measured distance is less than {SAFE_DISTANCE_CM:.1f} cm, the Safety Warning screen will appear.",
            font=font.Font(family="DejaVu Sans", size=11),
            bg=card,
            fg=muted,
            wraplength=700,
            justify="center"
        ).pack(pady=(0, 14))

        status_label = tk.Label(
            panel,
            text="Initializing ultrasonic sensor...",
            font=font.Font(family="DejaVu Sans", size=18, weight="bold"),
            bg=card,
            fg=dark
        )
        status_label.pack(pady=(8, 8))

        guide_label = tk.Label(
            panel,
            text="This test uses TRIG/ECHO timeout reading, so Cancel works even if no echo is received.",
            font=font.Font(family="DejaVu Sans", size=10),
            bg=card,
            fg=muted,
            wraplength=700,
            justify="center"
        )
        guide_label.pack(pady=(0, 16))

        btn_row = tk.Frame(panel, bg=card)
        btn_row.pack(pady=(4, 16))

        state = {
            "cancelled": False,
            "done": False,
            "trig": None,
            "echo": None,
        }

        def cleanup_pins():
            for key in ("trig", "echo"):
                dev = state.get(key)
                if dev is not None:
                    try:
                        dev.close()
                    except Exception:
                        pass
                    state[key] = None

        def cancel_test():
            state["cancelled"] = True
            state["done"] = True
            cleanup_pins()
            self.set_action("CANCEL")

        tk.Button(
            btn_row,
            text="Cancel",
            width=16,
            height=2,
            font=font.Font(family="DejaVu Sans", size=14, weight="bold"),
            bg="#b91c1c",
            fg="white",
            activebackground="#991b1b",
            activeforeground="white",
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=cancel_test
        ).pack(side="left", padx=10)

        self.apply_button_contrast_recursive()
        self.root.update()

        if not GPIO_OK:
            status_label.config(text="GPIO library is not available.", fg=red)
            return self.wait_action()

        try:
            state["trig"] = DigitalOutputDevice(PIN_ULTRA_TRIG, initial_value=False)
            state["echo"] = DigitalInputDevice(PIN_ULTRA_ECHO, pull_up=False)
            time.sleep(0.08)
            status_label.config(text="Sensor ready. Waiting for detection...", fg=green)
        except Exception as e:
            status_label.config(text=f"GPIO pin setup failed: {e}", fg=red)
            cleanup_pins()
            return self.wait_action()

        def read_distance_once(timeout=0.025):
            trig = state["trig"]
            echo = state["echo"]

            if trig is None or echo is None:
                return None, "pin_closed"

            # Trigger pulse: 10 microseconds
            trig.off()
            time.sleep(0.000002)
            trig.on()
            time.sleep(0.00001)
            trig.off()

            # Wait until echo goes HIGH
            start_wait = time.time()
            while echo.value == 0:
                if state["cancelled"]:
                    return None, "cancelled"
                if time.time() - start_wait > timeout:
                    return None, "no_echo_start"

            pulse_start = time.time()

            # Wait until echo goes LOW
            while echo.value == 1:
                if state["cancelled"]:
                    return None, "cancelled"
                if time.time() - pulse_start > timeout:
                    return None, "no_echo_end"

            pulse_end = time.time()
            pulse_duration = pulse_end - pulse_start

            # Speed of sound: about 34300 cm/s, round trip divided by 2
            distance_cm = (pulse_duration * 34300.0) / 2.0
            return distance_cm, "ok"

        def poll_sensor():
            if state["done"] or state["cancelled"]:
                return

            try:
                distance, status = read_distance_once(timeout=0.025)
            except Exception as e:
                distance, status = None, f"error: {e}"

            if state["cancelled"]:
                return

            if status == "ok" and distance is not None:
                if distance < SAFE_DISTANCE_CM:
                    status_label.config(text=f"Detected: {distance:.1f} cm", fg=red)
                    state["done"] = True
                    cleanup_pins()
                    self.root.after(150, lambda d=distance: self.safety_warning(d))
                    return

                status_label.config(text=f"Distance: {distance:.1f} cm | Safe", fg=green)

            elif status == "no_echo_start":
                status_label.config(text="No echo received. Check wiring or sensor direction.", fg=amber)

            elif status == "no_echo_end":
                status_label.config(text="Echo timeout. Check ECHO wiring.", fg=amber)

            elif status == "cancelled":
                return

            else:
                status_label.config(text=f"Distance read failed: {status}", fg=red)

            self.root.after(120, poll_sensor)

        self.root.after(120, poll_sensor)

        while not state["done"] and self.action is None:
            self.apply_button_contrast_recursive()
            self.root.update()
            time.sleep(0.03)

        cleanup_pins()

        if state["cancelled"]:
            return "CANCEL"

        return self.action


    def check_fire_alarm_trigger(self):
        if self.fire_alarm_active:
            return False

        now = time.time()

        if now - self.last_fire_check_at < FIRE_CHECK_INTERVAL_SEC:
            return False

        self.last_fire_check_at = now

        temp, _ = self.hw.read_temp_humidity()

        # DHT 센서가 없거나 값을 읽지 못하면 화재 경보 판단을 하지 않습니다.
        if temp is None:
            self.fire_high_since = None
            return False

        if temp >= FIRE_TEMP_THRESHOLD_C:
            if self.fire_high_since is None:
                self.fire_high_since = now
                return False

            if now - self.fire_high_since >= FIRE_CONFIRM_SECONDS:
                print(f"[FIRE] Alarm triggered. Temperature: {temp:.1f} C")

                self.fire_alarm_active = True
                self.action = "FIRE_ALARM"

                try:
                    self.hw.reset_servo()
                except Exception as e:
                    print("[WARN] Servo reset during fire alarm failed:", e)

                self.fire_alarm_screen(test_mode=False)

                self.fire_alarm_active = False
                self.fire_high_since = None
                self.action = "FIRE_ALARM_RESOLVED"
                return True

        else:
            self.fire_high_since = None

        return False

    def fire_alarm_screen(self, test_mode=False, duration_sec=5):
        self.clear()
        self.root.configure(bg="#b91c1c")

        red_bg = "#b91c1c"
        white = "#ffffff"
        light = "#fee2e2"

        tk.Label(
            self.root,
            text="Fire Alarm\nCall Fire Department",
            font=font.Font(family="DejaVu Sans", size=34, weight="bold"),
            bg=red_bg,
            fg=white,
            justify="center"
        ).pack(expand=True)

        status_label = tk.Label(
            self.root,
            text="System paused for safety.",
            font=font.Font(family="DejaVu Sans", size=16, weight="bold"),
            bg=red_bg,
            fg=light,
            justify="center"
        )
        status_label.pack(pady=(0, 22))

        detail_label = tk.Label(
            self.root,
            text="",
            font=font.Font(family="DejaVu Sans", size=12),
            bg=red_bg,
            fg=light,
            justify="center"
        )
        detail_label.pack(pady=(0, 24))

        self.root.update()

        buzzer_state = {
            "on": False,
            "off_at": 0.0,
            "next_at": 0.0,
            "tone_index": 0,
        }

        def service_fire_buzzer():
            if not USE_BUZZER:
                return

            now = time.time()

            # Turn current tone off after the ON duration.
            if buzzer_state["on"] and now >= buzzer_state["off_at"]:
                self.hw.buzzer_off()
                buzzer_state["on"] = False
                buzzer_state["next_at"] = now + FIRE_ALARM_BEEP_OFF_SEC

            # Start next tone after the OFF duration.
            if not buzzer_state["on"] and now >= buzzer_state["next_at"]:
                if buzzer_state["tone_index"] % 2 == 0:
                    tone = FIRE_ALARM_LOW_HZ
                else:
                    tone = FIRE_ALARM_HIGH_HZ

                self.hw.buzzer_on(tone_hz=tone, duty=FIRE_ALARM_DUTY)
                buzzer_state["tone_index"] += 1
                buzzer_state["on"] = True
                buzzer_state["off_at"] = now + FIRE_ALARM_BEEP_ON_SEC

        if test_mode:
            start = time.time()

            while time.time() - start < duration_sec:
                remain = max(0, int(duration_sec - (time.time() - start)) + 1)
                detail_label.config(
                    text=f"Admin test mode. Returning to Admin Mode in {remain} seconds."
                )
                service_fire_buzzer()
                self.root.update()
                time.sleep(0.1)

            self.hw.buzzer_off()
            return

        safe_since = None

        while True:
            temp, _ = self.hw.read_temp_humidity()
            now = time.time()

            if temp is None:
                safe_since = None
                detail_label.config(
                    text="Temperature sensor value is not available.\nPlease check the sensor connection."
                )

            elif temp <= FIRE_TEMP_THRESHOLD_C:
                if safe_since is None:
                    safe_since = now

                elapsed = now - safe_since
                remain = max(0, FIRE_RECOVERY_SECONDS - int(elapsed))

                detail_label.config(
                    text=(
                        f"Current temperature: {temp:.1f}°C\n"
                        f"Cooling detected. Keep below {FIRE_TEMP_THRESHOLD_C:.1f}°C for {remain} more seconds."
                    )
                )

                if elapsed >= FIRE_RECOVERY_SECONDS:
                    print(f"[FIRE] Alarm cleared. Temperature: {temp:.1f} C")
                    break

            else:
                safe_since = None
                detail_label.config(
                    text=(
                        f"Current temperature: {temp:.1f}°C\n"
                        f"Waiting until temperature stays below {FIRE_TEMP_THRESHOLD_C:.1f}°C for {FIRE_RECOVERY_SECONDS} seconds."
                    )
                )

            service_fire_buzzer()
            self.root.update()
            time.sleep(0.2)

        self.hw.buzzer_off()

    def admin_fire_alarm_test(self):
        try:
            self.hw.reset_servo()
        except Exception as e:
            print("[WARN] Servo reset during fire alarm test failed:", e)

        self.fire_alarm_screen(test_mode=True, duration_sec=5)


    def touch_session(self):
        self.last_activity_at = time.time()

        try:
            self.last_motion_at = time.time()

            if getattr(self, "screen_is_off", False):
                self.set_display_power(True)

        except Exception:
            pass

    def check_session_timeout(self):
        if self.in_admin_mode:
            return False

        if self.current_user_id is None:
            return False

        return (time.time() - self.last_activity_at) >= SESSION_TIMEOUT_SEC

    def start_guest_session(self):
        self.current_user_id = "Guest"
        self.current_user_name = "Guest"
        self.is_guest = True
        self.touch_session()

    def start_user_session(self, user_id, user_name=None):
        self.current_user_id = user_id
        self.current_user_name = user_name or f"User {user_id}"
        self.is_guest = False
        self.touch_session()

    def logout(self):
        self.current_user_id = None
        self.current_user_name = None
        self.is_guest = False
        self.last_activity_at = time.time()
        try:
            self.reset_system()
        except Exception:
            pass

    def current_user_display_text(self):
        if self.current_user_id is None:
            return "Not logged in"

        if self.is_guest:
            return "Guest Mode"

        points = get_user_points(self.current_user_id)
        return f"User ID {self.current_user_id} | {points} Point"

    def play_point_earned_sound(self):
        try:
            if not USE_BUZZER:
                return

            if getattr(self, "fire_alarm_active", False):
                return

            if not hasattr(self, "hw") or self.hw is None:
                return

            if getattr(self.hw, "buzzer", None) is None:
                return

            total_delay = 0

            for tone in POINT_SOUND_TONES:
                self.root.after(
                    total_delay,
                    lambda t=tone: self.hw.buzzer_on(
                        tone_hz=t,
                        duty=POINT_SOUND_DUTY
                    )
                )

                self.root.after(
                    total_delay + POINT_SOUND_ON_MS,
                    self.hw.buzzer_off
                )

                total_delay += POINT_SOUND_ON_MS + POINT_SOUND_GAP_MS

            self.root.after(total_delay + 20, self.hw.buzzer_off)

        except Exception:
            try:
                self.hw.buzzer_off()
            except Exception:
                pass


    def timed_popup(self, title, msg, duration_sec=5):
        self.clear()
        self.action = None
        self.root.configure(bg="#edf4f8")

        card = "#ffffff"
        page_bg = "#edf4f8"
        dark = "#0f172a"
        muted = "#475569"

        box = tk.Frame(
            self.root,
            bg=card,
            highlightbackground="#cbd5e1",
            highlightthickness=1,
            bd=0
        )
        box.pack(expand=True, fill="both", padx=60, pady=70)

        tk.Label(
            box,
            text=title,
            font=font.Font(family="DejaVu Sans", size=24, weight="bold"),
            bg=card,
            fg=dark
        ).pack(pady=(36, 12))

        tk.Label(
            box,
            text=msg,
            font=font.Font(family="DejaVu Sans", size=15, weight="bold"),
            bg=card,
            fg=dark,
            wraplength=620,
            justify="center"
        ).pack(pady=(0, 16))

        remain_label = tk.Label(
            box,
            text="",
            font=font.Font(family="DejaVu Sans", size=11),
            bg=card,
            fg=muted
        )
        remain_label.pack(pady=(0, 18))

        self.button(box, "Close", "CLOSE", width=14, height=1, bg="#dbeafe").pack()

        start = time.time()

        while self.action is None:
            elapsed = time.time() - start
            remain = max(0, int(duration_sec - elapsed) + 1)
            remain_label.config(text=f"Closing automatically in {remain} seconds.")

            self.apply_button_contrast_recursive()
            self.root.update()

            if elapsed >= duration_sec:
                break

            time.sleep(0.05)

        return "CLOSE"

    def base_screen(self):
        self.clear()
        self.root.configure(bg="#edf4f8")

        dark = "#0f172a"
        muted = "#475569"
        card = "#ffffff"
        page_bg = "#edf4f8"

        header = tk.Frame(self.root, bg=dark, height=62)
        header.pack(fill="x")
        header.pack_propagate(False)

        title_box = tk.Frame(header, bg=dark)
        title_box.pack(side="left", padx=18, pady=8)

        tk.Label(
            title_box,
            text="AIoT Smart Recycling System",
            font=font.Font(family="DejaVu Sans", size=19, weight="bold"),
            bg=dark,
            fg="white"
        ).pack(anchor="w")

        tk.Label(
            title_box,
            text="Smart Recycling Kiosk",
            font=self.font_small,
            bg=dark,
            fg="#cbd5e1"
        ).pack(anchor="w")

        tk.Button(
            header,
            text="Admin Mode",
            font=self.font_small,
            bg="#1d4ed8",
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
            highlightthickness=0,
            cursor="hand2",
            command=lambda: self.set_action("ADMIN")
        ).pack(side="right", padx=16, pady=14)

        body = tk.Frame(self.root, bg=page_bg)
        body.pack(fill="both", expand=True, padx=18, pady=12)

        main_card = tk.Frame(body, bg=card, highlightbackground="#d8e3eb", highlightthickness=1, bd=0)
        main_card.pack(fill="x")

        title_row = tk.Frame(main_card, bg=card)
        title_row.pack(fill="x", padx=18, pady=(14, 3))

        tk.Label(
            title_row,
            text="Welcome to Smart Recycling",
            font=font.Font(family="DejaVu Sans", size=22, weight="bold"),
            bg=card,
            fg=dark
        ).pack(side="left", anchor="w")

        tk.Label(
            title_row,
            text="♻",
            font=font.Font(family="DejaVu Sans", size=42, weight="bold"),
            bg=card,
            fg="#16a34a"
        ).pack(side="right", padx=(10, 4))

        tk.Label(
            main_card,
            text="Login to save your recycling history and earn points.",
            font=font.Font(family="DejaVu Sans", size=12),
            bg=card,
            fg=muted,
            justify="left"
        ).pack(anchor="w", padx=18, pady=(0, 12))

        impact_card = tk.Frame(body, bg="#ecfdf5", highlightbackground="#bbf7d0", highlightthickness=1, bd=0)
        impact_card.pack(fill="x", pady=(10, 10))

        tk.Label(
            impact_card,
            text="Recycling Impact",
            font=font.Font(family="DejaVu Sans", size=14, weight="bold"),
            bg="#ecfdf5",
            fg="#166534"
        ).pack(anchor="w", padx=16, pady=(8, 0))

        tk.Label(
            impact_card,
            text="Every recycled item helps reduce waste, save resources, and keep the Earth cleaner.",
            font=font.Font(family="DejaVu Sans", size=12),
            bg="#ecfdf5",
            fg="#166534",
            justify="left",
            wraplength=720
        ).pack(anchor="w", padx=16, pady=(2, 8))

        action_card = tk.Frame(body, bg=card, highlightbackground="#d8e3eb", highlightthickness=1, bd=0)
        action_card.pack(fill="both", expand=True)

        tk.Label(
            action_card,
            text="Choose access mode",
            font=font.Font(family="DejaVu Sans", size=18, weight="bold"),
            bg=card,
            fg=dark
        ).pack(pady=(24, 12))

        btn_row = tk.Frame(action_card, bg=card)
        btn_row.pack(pady=12)

        self.button(btn_row, "Login", "LOGIN", width=16, height=2, bg="#15803d").pack(side="left", padx=10)
        self.button(btn_row, "Register", "REGISTER", width=16, height=2, bg="#1d4ed8").pack(side="left", padx=10)
        self.button(btn_row, "Guest", "GUEST", width=16, height=2, bg="#475569").pack(side="left", padx=10)

        tk.Label(
            action_card,
            text="Guest mode can sort waste, but personal logs and points are not saved.",
            font=self.font_small,
            bg=card,
            fg=muted
        ).pack(pady=(10, 0))

        return self.wait_action()

    def login_screen(self):
        self.clear()
        self.root.configure(bg="#edf4f8")

        card = "#ffffff"
        page_bg = "#edf4f8"
        dark = "#0f172a"
        muted = "#475569"
        red = "#dc2626"

        state = {
            "stage": "id",
            "user_id": "",
            "pin": "",
        }

        tk.Label(
            self.root,
            text="Login",
            font=self.font_title,
            bg=page_bg,
            fg=dark
        ).pack(pady=(18, 6))

        panel = tk.Frame(
            self.root,
            bg=card,
            highlightbackground="#cbd5e1",
            highlightthickness=1,
            bd=0
        )
        panel.pack(fill="both", expand=True, padx=42, pady=(0, 18))

        stage_label = tk.Label(
            panel,
            text="",
            font=font.Font(family="DejaVu Sans", size=18, weight="bold"),
            bg=card,
            fg=dark
        )
        stage_label.pack(pady=(18, 8))

        display_label = tk.Label(
            panel,
            text="----",
            font=font.Font(family="DejaVu Sans", size=32, weight="bold"),
            bg="#f8fafc",
            fg=dark,
            width=12,
            relief="solid",
            bd=1,
            pady=8
        )
        display_label.pack(pady=(0, 8))

        msg_label = tk.Label(
            panel,
            text="Enter your 4-digit ID Code.",
            font=self.font_small,
            bg=card,
            fg=muted
        )
        msg_label.pack(pady=(0, 8))

        keypad = tk.Frame(panel, bg=card)
        keypad.pack(pady=(0, 8))

        keys = [
            ("1", "KEY_1"), ("2", "KEY_2"), ("3", "KEY_3"),
            ("4", "KEY_4"), ("5", "KEY_5"), ("6", "KEY_6"),
            ("7", "KEY_7"), ("8", "KEY_8"), ("9", "KEY_9"),
            ("Clear", "KEY_CLEAR"), ("0", "KEY_0"), ("Del", "KEY_BACK"),
        ]

        for idx, (label, action) in enumerate(keys):
            r = idx // 3
            c = idx % 3
            bg = "#e2e8f0"

            if label == "Clear":
                bg = "#fde68a"
            elif label == "Del":
                bg = "#fecaca"

            self.button(
                keypad,
                label,
                action,
                width=8,
                height=1,
                bg=bg
            ).grid(row=r, column=c, padx=5, pady=4)

        btn_row = tk.Frame(panel, bg=card)
        btn_row.pack(fill="x", padx=40, pady=(4, 8))

        for col in range(3):
            btn_row.grid_columnconfigure(col, weight=1, uniform="login_action_buttons")

        self.button(
            btn_row,
            "Back",
            "BACK",
            width=12,
            height=1,
            bg="#fecaca"
        ).grid(row=0, column=0, sticky="w", padx=8)

        tk.Label(
            btn_row,
            text="",
            bg=card,
            width=12
        ).grid(row=0, column=1, sticky="nsew", padx=8)

        primary_btn = tk.Button(
            btn_row,
            text="Next",
            font=font.Font(family="DejaVu Sans", size=13, weight="bold"),
            bg="#15803d",
            fg="white",
            activebackground="#15803d",
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=22,
            pady=8,
            highlightthickness=0,
            cursor="hand2",
            command=lambda: self.set_action("LOGIN_NEXT")
        )
        primary_btn.grid(row=0, column=2, sticky="e", padx=8)

        def masked(value):
            return "●" * len(value) + "-" * (4 - len(value))

        def update_ui():
            if state["stage"] == "id":
                stage_label.config(text="Enter ID Code")
                display_label.config(text=state["user_id"] + "-" * (4 - len(state["user_id"])))
                msg_label.config(text="Enter your 4-digit ID Code.", fg=muted)
                primary_btn.config(
                    text="Next",
                    command=lambda: self.set_action("LOGIN_NEXT")
                )
            else:
                stage_label.config(text="Enter Password")
                display_label.config(text=masked(state["pin"]))
                msg_label.config(text="Enter your 4-digit Password.", fg=muted)
                primary_btn.config(
                    text="Login",
                    command=lambda: self.set_action("LOGIN_SUBMIT")
                )

        update_ui()

        while True:
            act = self.wait_action()

            if act == "AUTO_LOGOUT":
                return "BACK"

            if act == "BACK":
                if state["stage"] == "pin":
                    state["stage"] = "id"
                    state["pin"] = ""
                    update_ui()
                    self.action = None
                    continue

                return "BACK"

            if act.startswith("KEY_"):
                key = act.replace("KEY_", "")

                target = "user_id" if state["stage"] == "id" else "pin"

                if key.isdigit():
                    if len(state[target]) < 4:
                        state[target] += key

                elif key == "BACK":
                    state[target] = state[target][:-1]

                elif key == "CLEAR":
                    state[target] = ""

                update_ui()
                self.action = None
                continue

            if act == "LOGIN_NEXT":
                if len(state["user_id"]) != 4:
                    msg_label.config(text="ID Code must be 4 digits.", fg=red)
                    self.action = None
                    continue

                state["stage"] = "pin"
                update_ui()
                self.action = None
                continue

            if act == "LOGIN_SUBMIT":
                user_id = state["user_id"]
                pin = state["pin"]

                if len(user_id) != 4:
                    msg_label.config(text="ID Code must be 4 digits.", fg=red)
                    state["stage"] = "id"
                    update_ui()
                    self.action = None
                    continue

                if len(pin) != 4:
                    msg_label.config(text="Password must be 4 digits.", fg=red)
                    self.action = None
                    continue

                ok, user = validate_user(user_id, pin)

                if not ok:
                    msg_label.config(text="Invalid ID Code or Password.", fg=red)
                    state["pin"] = ""
                    update_ui()
                    self.action = None
                    continue

                self.start_user_session(user_id)
                return "LOGIN_OK"

    def register_screen(self):
        self.clear()
        self.root.configure(bg="#edf4f8")

        card = "#ffffff"
        page_bg = "#edf4f8"
        dark = "#0f172a"
        muted = "#475569"
        red = "#dc2626"
        green = "#15803d"

        state = {
            "stage": "id",
            "user_id": "",
            "pin": "",
            "pin2": "",
            "checked_id": None,
        }

        tk.Label(
            self.root,
            text="Register",
            font=self.font_title,
            bg=page_bg,
            fg=dark
        ).pack(pady=(12, 4))

        panel = tk.Frame(
            self.root,
            bg=card,
            highlightbackground="#cbd5e1",
            highlightthickness=1,
            bd=0
        )
        panel.pack(fill="both", expand=True, padx=42, pady=(0, 14))

        stage_label = tk.Label(
            panel,
            text="",
            font=font.Font(family="DejaVu Sans", size=18, weight="bold"),
            bg=card,
            fg=dark
        )
        stage_label.pack(pady=(14, 6))

        display_label = tk.Label(
            panel,
            text="----",
            font=font.Font(family="DejaVu Sans", size=31, weight="bold"),
            bg="#f8fafc",
            fg=dark,
            width=12,
            relief="solid",
            bd=1,
            pady=7
        )
        display_label.pack(pady=(0, 6))

        msg_label = tk.Label(
            panel,
            text="Enter a new 4-digit ID Code.",
            font=self.font_small,
            bg=card,
            fg=muted
        )
        msg_label.pack(pady=(0, 6))

        keypad = tk.Frame(panel, bg=card)
        keypad.pack(pady=(0, 6))

        keys = [
            ("1", "KEY_1"), ("2", "KEY_2"), ("3", "KEY_3"),
            ("4", "KEY_4"), ("5", "KEY_5"), ("6", "KEY_6"),
            ("7", "KEY_7"), ("8", "KEY_8"), ("9", "KEY_9"),
            ("Clear", "KEY_CLEAR"), ("0", "KEY_0"), ("Del", "KEY_BACK"),
        ]

        for idx, (label, action) in enumerate(keys):
            r = idx // 3
            c = idx % 3
            bg = "#e2e8f0"

            if label == "Clear":
                bg = "#fde68a"
            elif label == "Del":
                bg = "#fecaca"

            self.button(
                keypad,
                label,
                action,
                width=8,
                height=1,
                bg=bg
            ).grid(row=r, column=c, padx=5, pady=3)

        btn_row = tk.Frame(panel, bg=card)
        btn_row.pack(fill="x", padx=38, pady=(4, 8))

        for col in range(3):
            btn_row.grid_columnconfigure(col, weight=1, uniform="register_action_buttons")

        self.button(
            btn_row,
            "Back",
            "BACK",
            width=10,
            height=1,
            bg="#fecaca"
        ).grid(row=0, column=0, sticky="w", padx=5)

        center_slot = tk.Frame(btn_row, bg=card)
        center_slot.grid(row=0, column=1, sticky="nsew", padx=5)

        check_btn = tk.Button(
            center_slot,
            text="Check ID",
            font=font.Font(family="DejaVu Sans", size=12, weight="bold"),
            bg="#dbeafe",
            fg=dark,
            activebackground="#bfdbfe",
            activeforeground=dark,
            relief="flat",
            bd=0,
            padx=14,
            pady=8,
            highlightthickness=0,
            cursor="hand2",
            command=lambda: self.set_action("CHECK_ID")
        )
        check_btn.pack(anchor="center")

        center_blank = tk.Label(
            center_slot,
            text="",
            bg=card,
            width=12
        )

        primary_btn = tk.Button(
            btn_row,
            text="Next",
            font=font.Font(family="DejaVu Sans", size=12, weight="bold"),
            bg="#15803d",
            fg="white",
            activebackground="#15803d",
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=18,
            pady=8,
            highlightthickness=0,
            cursor="hand2",
            command=lambda: self.set_action("REG_NEXT")
        )
        primary_btn.grid(row=0, column=2, sticky="e", padx=5)

        def masked(value):
            return "●" * len(value) + "-" * (4 - len(value))

        def current_target():
            if state["stage"] == "id":
                return "user_id"
            if state["stage"] == "pin":
                return "pin"
            return "pin2"

        def update_ui():
            if state["stage"] == "id":
                stage_label.config(text="Create ID Code")
                display_label.config(text=state["user_id"] + "-" * (4 - len(state["user_id"])))
                primary_btn.config(
                    text="Next",
                    command=lambda: self.set_action("REG_NEXT")
                )
                center_blank.pack_forget()
                check_btn.pack(anchor="center")
                if state["checked_id"] == state["user_id"] and len(state["user_id"]) == 4:
                    msg_label.config(text="ID Code is available.", fg=green)
                else:
                    msg_label.config(text="Enter 4 digits and press Check ID.", fg=muted)

            elif state["stage"] == "pin":
                stage_label.config(text="Create Password")
                display_label.config(text=masked(state["pin"]))
                primary_btn.config(
                    text="Next",
                    command=lambda: self.set_action("REG_NEXT")
                )
                check_btn.pack_forget()
                center_blank.pack(anchor="center")
                msg_label.config(text="Enter a 4-digit Password.", fg=muted)

            else:
                stage_label.config(text="Confirm Password")
                display_label.config(text=masked(state["pin2"]))
                primary_btn.config(
                    text="Register",
                    command=lambda: self.set_action("REGISTER_SUBMIT")
                )
                check_btn.pack_forget()
                center_blank.pack(anchor="center")
                msg_label.config(text="Enter the same Password again.", fg=muted)

        update_ui()

        while True:
            act = self.wait_action()

            if act == "AUTO_LOGOUT":
                return "BACK"

            if act == "BACK":
                if state["stage"] == "pin":
                    state["stage"] = "id"
                    state["pin"] = ""
                    update_ui()
                    self.action = None
                    continue

                if state["stage"] == "pin2":
                    state["stage"] = "pin"
                    state["pin2"] = ""
                    update_ui()
                    self.action = None
                    continue

                return "BACK"

            if act.startswith("KEY_"):
                key = act.replace("KEY_", "")
                target = current_target()

                if key.isdigit():
                    if len(state[target]) < 4:
                        state[target] += key

                    if target == "user_id":
                        state["checked_id"] = None

                elif key == "BACK":
                    state[target] = state[target][:-1]

                    if target == "user_id":
                        state["checked_id"] = None

                elif key == "CLEAR":
                    state[target] = ""

                    if target == "user_id":
                        state["checked_id"] = None

                update_ui()
                self.action = None
                continue

            if act == "CHECK_ID":
                user_id = state["user_id"]
                users = load_users()

                if len(user_id) != 4:
                    msg_label.config(text="ID Code must be exactly 4 digits.", fg=red)
                    self.action = None
                    continue

                if user_id in users:
                    state["checked_id"] = None
                    msg_label.config(text="This ID Code already exists.", fg=red)
                    self.action = None
                    continue

                state["checked_id"] = user_id
                msg_label.config(text="ID Code is available.", fg=green)
                self.action = None
                continue

            if act == "REG_NEXT":
                if state["stage"] == "id":
                    if len(state["user_id"]) != 4:
                        msg_label.config(text="ID Code must be exactly 4 digits.", fg=red)
                        self.action = None
                        continue

                    if state["checked_id"] != state["user_id"]:
                        msg_label.config(text="Please press Check ID first.", fg=red)
                        self.action = None
                        continue

                    state["stage"] = "pin"
                    update_ui()
                    self.action = None
                    continue

                if state["stage"] == "pin":
                    if len(state["pin"]) != 4:
                        msg_label.config(text="Password must be exactly 4 digits.", fg=red)
                        self.action = None
                        continue

                    state["stage"] = "pin2"
                    update_ui()
                    self.action = None
                    continue

            if act == "REGISTER_SUBMIT":
                user_id = state["user_id"]
                pin = state["pin"]
                pin2 = state["pin2"]

                if len(user_id) != 4 or state["checked_id"] != user_id:
                    state["stage"] = "id"
                    update_ui()
                    msg_label.config(text="Please check ID duplication first.", fg=red)
                    self.action = None
                    continue

                if len(pin) != 4:
                    state["stage"] = "pin"
                    update_ui()
                    msg_label.config(text="Password must be exactly 4 digits.", fg=red)
                    self.action = None
                    continue

                if pin != pin2:
                    state["pin2"] = ""
                    update_ui()
                    msg_label.config(text="Passwords do not match. Try again.", fg=red)
                    self.action = None
                    continue

                ok, msg = create_user(user_id, pin)

                if not ok:
                    state["stage"] = "id"
                    state["checked_id"] = None
                    update_ui()
                    msg_label.config(text=msg, fg=red)
                    self.action = None
                    continue

                self.start_user_session(user_id)
                self.timed_popup(
                    "Registration Complete",
                    f"Welcome.\nYour ID Code is {user_id}.",
                    duration_sec=5
                )
                return "REGISTER_OK"

    def user_log_screen(self):
        if self.is_guest or self.current_user_id in [None, "Guest"]:
            self.timed_popup(
                "Login Required",
                "Register or login to view your personal recycling log.",
                duration_sec=5
            )
            return

        page = 0
        rows_per_page = 7

        def load_my_rows():
            ensure_log_file_schema()
            rows = []

            try:
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)

                    for row in reader:
                        if row.get("User ID", "") == self.current_user_id:
                            rows.append(row)

            except Exception as e:
                print("[WARN] Failed to load user log:", e)

            rows.reverse()
            return rows

        while True:
            rows = load_my_rows()
            total_pages = max(1, (len(rows) + rows_per_page - 1) // rows_per_page)
            page = max(0, min(page, total_pages - 1))
            page_rows = rows[page * rows_per_page:(page + 1) * rows_per_page]

            self.clear()
            self.root.configure(bg="#edf4f8")

            dark = "#0f172a"
            muted = "#475569"
            card = "#ffffff"
            page_bg = "#edf4f8"
            points = get_user_points(self.current_user_id)

            tk.Label(
                self.root,
                text="My Recycling Log",
                font=font.Font(family="DejaVu Sans", size=22, weight="bold"),
                bg=page_bg,
                fg=dark
            ).pack(pady=(12, 2))

            tk.Label(
                self.root,
                text=f"User ID {self.current_user_id} | Total {points} Point",
                font=font.Font(family="DejaVu Sans", size=13, weight="bold"),
                bg=page_bg,
                fg="#1d4ed8"
            ).pack(pady=(0, 8))

            table = tk.Frame(
                self.root,
                bg=card,
                highlightbackground="#cbd5e1",
                highlightthickness=1,
                bd=0
            )
            table.pack(fill="both", expand=True, padx=18, pady=(0, 8))

            headers = [
                ("Date / Time", 28),
                ("Category", 20),
                ("Point", 10),
            ]

            for col, weight in enumerate([3, 2, 1]):
                table.grid_columnconfigure(col, weight=weight, uniform="my_log_columns")

            for col, (title, width) in enumerate(headers):
                tk.Label(
                    table,
                    text=title,
                    width=width,
                    anchor="w" if col == 0 else "center",
                    font=font.Font(family="DejaVu Sans", size=11, weight="bold"),
                    bg="#e2e8f0",
                    fg=dark,
                    padx=6,
                    pady=6
                ).grid(row=0, column=col, sticky="nsew", padx=1, pady=1)

            if not page_rows:
                tk.Label(
                    table,
                    text="No personal recycling log has been recorded yet.",
                    font=font.Font(family="DejaVu Sans", size=14, weight="bold"),
                    bg=card,
                    fg=muted,
                    pady=34
                ).grid(row=1, column=0, columnspan=3, sticky="nsew")
            else:
                for r, row in enumerate(page_rows, start=1):
                    bg = "#ffffff" if r % 2 else "#f8fafc"
                    values = [
                        row.get("Time", "-"),
                        row.get("Final Category", "-"),
                        f"+{row.get('Earned Points', '0')}",
                    ]

                    for c, value in enumerate(values):
                        fg = dark

                        if c == 1:
                            fg = self.contrast_button_color(value)
                        elif c == 2:
                            fg = "#15803d"

                        tk.Label(
                            table,
                            text=value,
                            width=headers[c][1],
                            anchor="w" if c == 0 else "center",
                            font=font.Font(
                                family="DejaVu Sans",
                                size=10,
                                weight="bold" if c in [1, 2] else "normal"
                            ),
                            bg=bg,
                            fg=fg,
                            padx=6,
                            pady=6
                        ).grid(row=r, column=c, sticky="nsew", padx=1, pady=1)

            nav = tk.Frame(self.root, bg=page_bg)
            nav.pack(pady=(0, 10))

            self.button(nav, "Prev", "PREV_LOG", width=10, height=1, bg="#dbeafe").pack(side="left", padx=6)

            tk.Label(
                nav,
                text=f"Page {page + 1} / {total_pages}",
                font=font.Font(family="DejaVu Sans", size=11, weight="bold"),
                bg=page_bg,
                fg=dark,
                width=16
            ).pack(side="left", padx=6)

            self.button(nav, "Next", "NEXT_LOG", width=10, height=1, bg="#dbeafe").pack(side="left", padx=6)
            self.button(nav, "Back", "BACK", width=10, height=1, bg="#fecaca").pack(side="left", padx=6)

            act = self.wait_action()

            if act in ["BACK", "AUTO_LOGOUT"]:
                break
            elif act == "PREV_LOG":
                page = max(0, page - 1)
            elif act == "NEXT_LOG":
                page = min(total_pages - 1, page + 1)

    def admin_recycling_log_screen(self):
        page = 0
        rows_per_page = 6

        def parse_conf(value):
            try:
                return float(str(value).strip())
            except Exception:
                return None

        def load_rows():
            ensure_log_file_schema()
            rows = []

            try:
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)

            except Exception as e:
                print("[WARN] Failed to load admin recycling log:", e)

            rows.reverse()
            return rows

        while True:
            rows = load_rows()

            auto_conf = [
                parse_conf(row.get("Confidence", ""))
                for row in rows
                if row.get("Method", "") == "Auto" and parse_conf(row.get("Confidence", "")) is not None
            ]

            avg_conf = "N/A" if not auto_conf else f"{(sum(auto_conf) / len(auto_conf)) * 100:.1f}%"

            total_pages = max(1, (len(rows) + rows_per_page - 1) // rows_per_page)
            page = max(0, min(page, total_pages - 1))
            page_rows = rows[page * rows_per_page:(page + 1) * rows_per_page]

            self.clear()
            self.root.configure(bg="#edf4f8")

            dark = "#0f172a"
            muted = "#475569"
            card = "#ffffff"
            page_bg = "#edf4f8"

            tk.Label(
                self.root,
                text="Recycling Log",
                font=font.Font(family="DejaVu Sans", size=22, weight="bold"),
                bg=page_bg,
                fg=dark
            ).pack(pady=(8, 2))

            tk.Label(
                self.root,
                text=f"Average Auto Confidence: {avg_conf} | Total Records: {len(rows)}",
                font=font.Font(family="DejaVu Sans", size=11, weight="bold"),
                bg=page_bg,
                fg="#1d4ed8"
            ).pack(pady=(0, 5))

            table = tk.Frame(
                self.root,
                bg=card,
                highlightbackground="#cbd5e1",
                highlightthickness=1,
                bd=0
            )
            table.pack(fill="both", expand=True, padx=8, pady=(0, 6))

            headers = [
                ("Time", 18),
                ("User ID", 8),
                ("Category", 13),
                ("Method", 8),
                ("Conf.", 8),
                ("Total Pt", 8),
            ]

            for col, weight in enumerate([20, 10, 14, 10, 10, 10]):
                table.grid_columnconfigure(col, weight=weight, uniform="admin_log_columns")

            for col, (title, width) in enumerate(headers):
                tk.Label(
                    table,
                    text=title,
                    width=width,
                    anchor="center",
                    font=font.Font(family="DejaVu Sans", size=9, weight="bold"),
                    bg="#e2e8f0",
                    fg=dark,
                    padx=3,
                    pady=5
                ).grid(row=0, column=col, sticky="nsew", padx=1, pady=1)

            if not page_rows:
                tk.Label(
                    table,
                    text="No recycling log has been recorded yet.",
                    font=font.Font(family="DejaVu Sans", size=14, weight="bold"),
                    bg=card,
                    fg=muted,
                    pady=32
                ).grid(row=1, column=0, columnspan=6, sticky="nsew")
            else:
                for r, row in enumerate(page_rows, start=1):
                    bg = "#ffffff" if r % 2 else "#f8fafc"

                    conf = row.get("Confidence", "N/A")
                    if conf not in ["", "N/A"]:
                        try:
                            conf = f"{float(conf) * 100:.1f}%"
                        except Exception:
                            conf = "N/A"

                    values = [
                        row.get("Time", "-"),
                        row.get("User ID", "Guest") or "Guest",
                        row.get("Final Category", "-"),
                        row.get("Method", "-"),
                        conf or "N/A",
                        row.get("User Total Points", "N/A") or "N/A",
                    ]

                    for c, value in enumerate(values):
                        fg = dark
                        if c == 2:
                            fg = self.contrast_button_color(value)
                        elif c == 3:
                            fg = "#15803d" if value == "Auto" else "#92400e"

                        tk.Label(
                            table,
                            text=value,
                            width=headers[c][1],
                            anchor="center",
                            font=font.Font(
                                family="DejaVu Sans",
                                size=8,
                                weight="bold" if c in [1, 2, 3] else "normal"
                            ),
                            bg=bg,
                            fg=fg,
                            padx=2,
                            pady=5
                        ).grid(row=r, column=c, sticky="nsew", padx=1, pady=1)

            nav = tk.Frame(self.root, bg=page_bg)
            nav.pack(pady=(0, 8))

            self.button(nav, "Prev", "PREV_LOG", width=10, height=1, bg="#dbeafe").pack(side="left", padx=6)

            tk.Label(
                nav,
                text=f"Page {page + 1} / {total_pages}",
                font=font.Font(family="DejaVu Sans", size=11, weight="bold"),
                bg=page_bg,
                fg=dark,
                width=16
            ).pack(side="left", padx=6)

            self.button(nav, "Next", "NEXT_LOG", width=10, height=1, bg="#dbeafe").pack(side="left", padx=6)
            self.button(nav, "Back", "BACK", width=10, height=1, bg="#fecaca").pack(side="left", padx=6)

            act = self.wait_action()

            if act == "BACK":
                break
            elif act == "PREV_LOG":
                page = max(0, page - 1)
            elif act == "NEXT_LOG":
                page = min(total_pages - 1, page + 1)

    def admin_users_screen(self):
        page = 0
        rows_per_page = 8

        while True:
            users = load_users()
            rows = list(users.values())
            rows.sort(key=lambda u: str(u.get("id", "")))

            total_users = len(rows)
            avg_point = 0.0 if not rows else sum(int(u.get("points", 0)) for u in rows) / len(rows)

            total_pages = max(1, (len(rows) + rows_per_page - 1) // rows_per_page)
            page = max(0, min(page, total_pages - 1))
            page_rows = rows[page * rows_per_page:(page + 1) * rows_per_page]

            self.clear()
            self.root.configure(bg="#edf4f8")

            dark = "#0f172a"
            muted = "#475569"
            card = "#ffffff"
            page_bg = "#edf4f8"

            tk.Label(
                self.root,
                text="Users",
                font=font.Font(family="DejaVu Sans", size=22, weight="bold"),
                bg=page_bg,
                fg=dark
            ).pack(pady=(12, 2))

            tk.Label(
                self.root,
                text=f"Total Users: {total_users} | Average Point: {avg_point:.1f}",
                font=font.Font(family="DejaVu Sans", size=12, weight="bold"),
                bg=page_bg,
                fg="#1d4ed8"
            ).pack(pady=(0, 8))

            table = tk.Frame(
                self.root,
                bg=card,
                highlightbackground="#cbd5e1",
                highlightthickness=1,
                bd=0
            )
            table.pack(fill="both", expand=True, padx=36, pady=(0, 8))

            headers = [
                ("ID Code", 16),
                ("Point", 16),
                ("Created At", 28),
            ]

            for col, weight in enumerate([1, 1, 2]):
                table.grid_columnconfigure(col, weight=weight, uniform="admin_users_columns")

            for col, (title, width) in enumerate(headers):
                tk.Label(
                    table,
                    text=title,
                    width=width,
                    anchor="center",
                    font=font.Font(family="DejaVu Sans", size=11, weight="bold"),
                    bg="#e2e8f0",
                    fg=dark,
                    padx=4,
                    pady=6
                ).grid(row=0, column=col, sticky="nsew", padx=1, pady=1)

            if not page_rows:
                tk.Label(
                    table,
                    text="No registered users yet.",
                    font=font.Font(family="DejaVu Sans", size=14, weight="bold"),
                    bg=card,
                    fg=muted,
                    pady=34
                ).grid(row=1, column=0, columnspan=3, sticky="nsew")
            else:
                for r, user in enumerate(page_rows, start=1):
                    bg = "#ffffff" if r % 2 else "#f8fafc"
                    values = [
                        user.get("id", "-"),
                        str(user.get("points", 0)),
                        user.get("created_at", "-"),
                    ]

                    for c, value in enumerate(values):
                        fg = "#15803d" if c == 1 else dark

                        tk.Label(
                            table,
                            text=value,
                            width=headers[c][1],
                            anchor="center",
                            font=font.Font(
                                family="DejaVu Sans",
                                size=10,
                                weight="bold" if c in [0, 1] else "normal"
                            ),
                            bg=bg,
                            fg=fg,
                            padx=4,
                            pady=6
                        ).grid(row=r, column=c, sticky="nsew", padx=1, pady=1)

            nav = tk.Frame(self.root, bg=page_bg)
            nav.pack(pady=(0, 10))

            self.button(nav, "Prev", "PREV_USERS", width=10, height=1, bg="#dbeafe").pack(side="left", padx=6)

            tk.Label(
                nav,
                text=f"Page {page + 1} / {total_pages}",
                font=font.Font(family="DejaVu Sans", size=11, weight="bold"),
                bg=page_bg,
                fg=dark,
                width=16
            ).pack(side="left", padx=6)

            self.button(nav, "Next", "NEXT_USERS", width=10, height=1, bg="#dbeafe").pack(side="left", padx=6)
            self.button(nav, "Back", "BACK", width=10, height=1, bg="#fecaca").pack(side="left", padx=6)

            act = self.wait_action()

            if act == "BACK":
                break
            elif act == "PREV_USERS":
                page = max(0, page - 1)
            elif act == "NEXT_USERS":
                page = min(total_pages - 1, page + 1)

    def admin_loop(self):
        auth = self.admin_password_screen()

        if auth != "AUTH_OK":
            return

        self.in_admin_mode = True

        try:
            while True:
                admin = self.admin_screen()

                if admin == "RESET_BIN_WEIGHT":
                    ok = self.hw.tare_loadcell()
                    msg = "Bin weight has been reset." if ok else "Load cell reset failed."
                    self.message_screen("Reset Bin Weight", msg, [("Back", "BACK", "#dbeafe")])

                elif admin == "CHECK_SENSOR_STATUS":
                    self.admin_sensor_status()

                elif admin == "SERVO_TEST":
                    self.admin_servo_test()

                elif admin == "CAMERA_TEST":
                    self.admin_camera_test()

                elif admin == "SAFETY_WARNING_TEST":
                    if hasattr(self, "admin_ultrasonic_safety_test"):
                        self.admin_ultrasonic_safety_test()
                    else:
                        self.safety_warning(7.5)

                elif admin == "FIRE_ALARM_TEST":
                    if hasattr(self, "admin_fire_alarm_test"):
                        self.admin_fire_alarm_test()
                    else:
                        self.fire_alarm_screen(test_mode=True, duration_sec=5)

                elif admin == "RECYCLING_LOG":
                    self.admin_recycling_log_screen()

                elif admin == "ADMIN_USERS":
                    self.admin_users_screen()

                elif admin == "CLEAR_LOGS":
                    act = self.message_screen(
                        "Clear Logs",
                        "Are you sure you want to delete all logs?",
                        [("Yes", "YES", "#fecaca"), ("No", "NO", "#dbeafe")]
                    )

                    if act == "YES":
                        clear_logs()
                        self.message_screen(
                            "Clear Logs",
                            "Logs have been cleared.",
                            [("Back", "BACK", "#dbeafe")]
                        )

                elif admin == "BACK":
                    break

        finally:
            self.in_admin_mode = False
            self.touch_session()


    def admin_screen(self):
        self.clear()
        self.root.configure(bg="#edf4f8")

        dark = "#0f172a"
        muted = "#475569"
        card = "#ffffff"
        page_bg = "#edf4f8"

        header = tk.Frame(self.root, bg=page_bg, height=62)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Admin Mode",
            font=font.Font(family="DejaVu Sans", size=22, weight="bold"),
            bg=page_bg,
            fg=dark
        ).pack(side="left", padx=20, pady=14)

        body = tk.Frame(self.root, bg=page_bg)
        body.pack(fill="both", expand=True, padx=20, pady=12)

        panel = tk.Frame(body, bg=card, highlightbackground="#cbd5e1", highlightthickness=1, bd=0)
        panel.pack(fill="both", expand=True)

        tk.Label(
            panel,
            text="System Management",
            font=font.Font(family="DejaVu Sans", size=18, weight="bold"),
            bg=card,
            fg=dark
        ).pack(anchor="w", padx=18, pady=(16, 4))

        tk.Label(
            panel,
            text="Check sensors, test devices, reset weight, or manage logs.",
            font=font.Font(family="DejaVu Sans", size=12),
            bg=card,
            fg=muted
        ).pack(anchor="w", padx=18, pady=(0, 12))

        options = [('Reset Bin Weight', 'RESET_BIN_WEIGHT'), ('Check Sensor Status', 'CHECK_SENSOR_STATUS'), ('Servo Test', 'SERVO_TEST'), ('Camera Test', 'CAMERA_TEST'), ('Test Safety Warning', 'SAFETY_WARNING_TEST'), ('Recycling Log', 'RECYCLING_LOG'), ('Fire Alarm Test', 'FIRE_ALARM_TEST'), ('Users', 'ADMIN_USERS'), ('Clear Logs', 'CLEAR_LOGS'), ('Back', 'BACK')]

        grid = tk.Frame(panel, bg=card)
        grid.pack(expand=True)

        def admin_color(text, action):
            t = str(text).lower()
            a = str(action).lower()
            if "back" in t or "cancel" in t or a in ["back", "main", "cancel"]:
                return "#b91c1c"
            if "clear" in t or "reset" in t:
                return "#92400e"
            if "test" in t:
                return "#1d4ed8"
            if "sensor" in t or "check" in t:
                return "#0f766e"
            return "#334155"

        for i, item in enumerate(options):
            text, action = item
            btn = tk.Button(
                grid,
                text=text,
                width=22,
                height=2,
                font=font.Font(family="DejaVu Sans", size=13, weight="bold"),
                bg=admin_color(text, action),
                fg="white",
                activebackground=admin_color(text, action),
                activeforeground="white",
                relief="flat",
                bd=0,
                highlightthickness=0,
                cursor="hand2",
                command=lambda a=action: self.set_action(a)
            )
            btn.grid(row=i // 2, column=i % 2, padx=12, pady=10)

        return self.wait_action()
    def admin_sensor_status(self):
        while True:
            temp, humid = self.hw.read_temp_humidity()
            dist = self.hw.get_distance_cm()
            weight = self.hw.read_weight_kg()

            self.clear()
            tk.Label(self.root, text="Sensor Status", font=self.font_title).pack(pady=20)

            temp_s = "N/A" if temp is None else f"{temp:.1f}°C"
            humid_s = "N/A" if humid is None else f"{humid:.1f}%"
            dist_s = "N/A" if dist is None else f"{dist:.1f}cm"

            msg = (
                f"Temperature: {temp_s}\n"
                f"Humidity: {humid_s}\n"
                f"Bin Weight: {weight:.3f}kg\n"
                f"Ultrasonic Distance: {dist_s}"
            )

            tk.Label(self.root, text=msg, font=font.Font(family="DejaVu Sans", size=19), justify="left").pack(pady=25)

            frame = tk.Frame(self.root)
            frame.pack()

            self.button(frame, "Refresh", "REFRESH", bg="#dbeafe").pack(side="left", padx=10)
            self.button(frame, "Back", "BACK", bg="#e5e7eb").pack(side="left", padx=10)

            act = self.wait_action()
            if act == "BACK":
                break

    def admin_servo_test(self):
        while True:
            self.clear()
            tk.Label(self.root, text="Servo Test", font=self.font_title).pack(pady=20)
            tk.Label(self.root, text="Check the sorting plate direction.", font=self.font_normal).pack(pady=8)

            for cat in CATEGORIES:
                angle = SERVO_ANGLE_MAP[cat]
                tk.Button(
                    self.root,
                    text=f"{cat} {angle}°",
                    font=font.Font(family="DejaVu Sans", size=14, weight="bold"),
                    width=24,
                    height=1,
                    bg="#fde68a",
                    command=lambda c=cat: self.hw.move_to_category(c)
                ).pack(pady=4)

            frame = tk.Frame(self.root)
            frame.pack(pady=8)

            tk.Button(
                frame,
                text=f"Home {SERVO_HOME_ANGLE}°",
                font=font.Font(family="DejaVu Sans", size=14, weight="bold"),
                width=15,
                height=1,
                bg="#bbf7d0",
                command=self.hw.reset_servo
            ).pack(side="left", padx=8)

            self.button(frame, "Back", "BACK", width=12, height=1, bg="#dbeafe").pack(side="left", padx=8)

            act = self.wait_action()
            if act == "BACK":
                break

    def admin_camera_test(self):
        result = self.auto_capture()

        if result == "CAMERA_ERROR":
            self.message_screen(
                "Camera Error",
                "Please check the camera connection.",
                [("Back", "BACK", "#dbeafe")]
            )
        elif result == "STABILITY_TIMEOUT":
            self.message_screen(
                "Capture Timeout",
                "안정 상태가 감지되지 않았습니다.",
                [("Back", "BACK", "#dbeafe")]
            )
        elif result is not None:
            self.message_screen(
                "Camera Test",
                f"Image saved:\n{result}",
                [("Back", "BACK", "#dbeafe")]
            )

    def reset_system(self):
        self.hw.reset_servo()
        self.hw.led_off()

    def run(self):
        try:
            while True:
                if self.current_user_id is None:
                    entry_action = self.base_screen()

                    if entry_action == "LOGIN":
                        self.login_screen()
                        continue

                    elif entry_action == "REGISTER":
                        self.register_screen()
                        continue

                    elif entry_action == "GUEST":
                        self.start_guest_session()
                        continue

                    elif entry_action == "ADMIN":
                        self.admin_loop()
                        continue

                    else:
                        continue

                action = self.main_screen()

                if action in ["LOGOUT", "AUTO_LOGOUT"]:
                    self.logout()
                    continue

                if action == "START":
                    capture = self.auto_capture()

                    if capture == "AUTO_LOGOUT":
                        self.logout()
                        continue

                    if capture == "CAMERA_ERROR":
                        self.message_screen(
                            "Camera Error",
                            "카메라를 열 수 없습니다.\nPlease check the camera connection.",
                            [("Retry", "TRY_AGAIN", "#dbeafe"), ("Cancel", "CANCEL", "#fecaca")]
                        )
                        continue

                    if capture == "STABILITY_TIMEOUT":
                        self.message_screen(
                            "Auto Capture Failed",
                            "The waste was not stable.\nPlease place it again.",
                            [("Try Again", "TRY_AGAIN", "#dbeafe"), ("Cancel", "CANCEL", "#fecaca")]
                        )
                        continue

                    if capture is None:
                        self.reset_system()
                        continue

                    image_path = str(capture)
                    result = self.classifier.classify(image_path)

                    predicted = result["category"]
                    label = result["label"]
                    conf = result["confidence"]

                    final = None
                    confirmed = None

                    if not result["detected"] or predicted is None:
                        act = self.message_screen(
                            "Classification Failed",
                            "Classification failed.\nPlease try again or select manually.",
                            [
                                ("Try Again", "TRY_AGAIN", "#dbeafe"),
                                ("Select Manually", "MANUAL", "#fde68a"),
                                ("Cancel", "CANCEL", "#fecaca")
                            ]
                        )

                        if act == "AUTO_LOGOUT":
                            self.logout()
                            continue

                        if act == "TRY_AGAIN":
                            continue
                        elif act == "MANUAL":
                            final = self.manual_screen()
                            if final in ["CANCEL", "AUTO_LOGOUT"]:
                                if final == "AUTO_LOGOUT":
                                    self.logout()
                                self.reset_system()
                                continue
                            confirmed = "Manual"
                        else:
                            self.reset_system()
                            continue

                    elif conf < MIN_CONFIDENCE:
                        final = self.manual_screen(
                            title="Low Confidence",
                            msg="AI is not confident enough.\nPlease select the correct category."
                        )

                        if final in ["CANCEL", "AUTO_LOGOUT"]:
                            if final == "AUTO_LOGOUT":
                                self.logout()
                            self.reset_system()
                            continue

                        confirmed = "Manual"

                    else:
                        act = self.result_screen(label, predicted, conf, image_path)

                        if act == "AUTO_LOGOUT":
                            self.logout()
                            continue

                        if act == "YES":
                            final = predicted
                            confirmed = "Yes"
                        elif act == "NO":
                            final = self.manual_screen()

                            if final in ["CANCEL", "AUTO_LOGOUT"]:
                                if final == "AUTO_LOGOUT":
                                    self.logout()
                                self.reset_system()
                                continue

                            confirmed = "Corrected"
                        else:
                            self.reset_system()
                            continue

                    while True:
                        safe, distance = self.hw.is_inlet_safe()

                        if safe:
                            break

                        act = self.safety_warning(distance)

                        if act == "AUTO_LOGOUT":
                            self.logout()
                            final = None
                            break

                        if act == "RETRY":
                            continue
                        else:
                            self.reset_system()
                            final = None
                            break

                    if final is None:
                        continue

                    self.servo_preparing(final)
                    self.hw.move_to_category(final)

                    done = self.disposal_screen(final)

                    if done == "AUTO_LOGOUT":
                        self.logout()
                        self.reset_system()
                        continue

                    if done == "DONE":
                        weight = self.hw.read_weight_kg()

                        if self.is_guest or self.current_user_id == "Guest":
                            user_id = "Guest"
                            earned_points = 0
                            total_points = "N/A"
                        else:
                            user_id = self.current_user_id
                            earned_points = POINT_PER_SORT
                            total_points = add_user_points(user_id, POINT_PER_SORT)

                        save_log(
                            predicted=predicted,
                            final=final,
                            confidence=conf,
                            confirmed=confirmed,
                            weight=weight,
                            image_path=image_path,
                            status="Success",
                            user_id=user_id,
                            earned_points=earned_points,
                            user_total_points=total_points
                        )

                        if self.is_guest or self.current_user_id == "Guest":
                            self.timed_popup(
                                "Register and Earn Points",
                                "Register to earn 10 Point every time you recycle.",
                                duration_sec=5
                            )
                        else:
                            self.play_point_earned_sound()
                            self.timed_popup(
                                "Point Earned",
                                f"+{POINT_PER_SORT} Point earned!\nTotal Point: {total_points}",
                                duration_sec=5
                            )

                    self.reset_system()

                elif action in ["USER_LOG", "STATISTICS"]:
                    if self.is_guest:
                        self.timed_popup(
                            "Login Required",
                            "Register or login to view personal recycling logs and earn points.",
                            duration_sec=5
                        )
                    else:
                        self.user_log_screen()

                elif action == "ADMIN":
                    self.admin_loop()

        except KeyboardInterrupt:
            print("Exiting.")

        finally:
            try:
                self.hide_screen_blank_overlay()
            except Exception:
                pass

            self.reset_system()
            self.root.destroy()

if __name__ == "__main__":
    app = App()
    app.run()

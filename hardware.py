import os
# Raspberry Pi 5에서는 lgpio 기반 GPIO 제어를 권장합니다.
# gpiozero import 전에 설정해야 합니다.
os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")

import time

from config import *

# ============================================================
# 1. 라이브러리 import
# ============================================================

try:
    from gpiozero import LED, DistanceSensor, AngularServo, DigitalInputDevice, DigitalOutputDevice, PWMOutputDevice
    GPIO_OK = True
except Exception as e:
    print("[WARN] GPIO 라이브러리 로드 실패:", e)
    GPIO_OK = False

try:
    import board
    import adafruit_dht
    DHT_OK = True
except Exception as e:
    print("[WARN] DHT 라이브러리 로드 실패:", e)
    DHT_OK = False

# ============================================================
# 2. HX711 로드셀 간단 드라이버
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
# 3. 하드웨어 제어
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

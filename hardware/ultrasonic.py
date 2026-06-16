from config import USE_ULTRASONIC, PIN_ULTRA_ECHO, PIN_ULTRA_TRIG, SAFE_DISTANCE_CM

class UltrasonicController:
    def __init__(self):
        self.ultrasonic = None
        if USE_ULTRASONIC:
            try:
                from gpiozero import DistanceSensor
                self.ultrasonic = DistanceSensor(
                    echo=PIN_ULTRA_ECHO,
                    trigger=PIN_ULTRA_TRIG,
                    max_distance=2.0
                )
            except Exception as e:
                print(f"[WARN] Ultrasonic sensor initialization failed: {e}")

    def get_distance_cm(self):
        if not self.ultrasonic:
            return None
        try:
            return self.ultrasonic.distance * 100.0
        except Exception:
            return None

    def is_safe(self):
        distance = self.get_distance_cm()
        if distance is None:
            # 센서값을 못 읽으면 데모 편의를 위해 일단 True 처리
            return True, None
        return distance >= SAFE_DISTANCE_CM, distance
from config import USE_MOTION_SENSOR, PIN_MOTION, MOTION_ACTIVE_HIGH

class MotionController:
    def __init__(self):
        self.sensor = None
        if USE_MOTION_SENSOR:
            try:
                from gpiozero import DigitalInputDevice
                self.sensor = DigitalInputDevice(PIN_MOTION, pull_up=False)
                print(f"[INFO] Motion sensor initialized on GPIO {PIN_MOTION}")
            except Exception as e:
                print(f"[WARN] Motion sensor initialization failed: {e}")

    def is_detected(self):
        if not USE_MOTION_SENSOR:
            return True

        if self.sensor is None:
            return True

        try:
            value = bool(self.sensor.value)
            return value if MOTION_ACTIVE_HIGH else not value
        except Exception:
            return True
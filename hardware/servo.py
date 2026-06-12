import time
from config import USE_SERVO, PIN_SERVO, SERVO_MIN_PULSE_WIDTH, SERVO_MAX_PULSE_WIDTH, SERVO_HOME_ANGLE, SERVO_MOVE_DELAY_SEC, SERVO_ANGLE_MAP

class ServoController:
    def __init__(self):
        self.servo = None
        if USE_SERVO:
            try:
                from gpiozero import AngularServo
                self.servo = AngularServo(
                    PIN_SERVO,
                    min_angle=0,
                    max_angle=180,
                    min_pulse_width=SERVO_MIN_PULSE_WIDTH,
                    max_pulse_width=SERVO_MAX_PULSE_WIDTH
                )
                self.move(SERVO_HOME_ANGLE)
            except Exception as e:
                print(f"[WARN] Servo initialization failed: {e}")

    def move(self, angle):
        print(f"[Servo] {angle} degrees")
        if self.servo:
            try:
                self.servo.angle = float(angle)
                time.sleep(SERVO_MOVE_DELAY_SEC)
            except Exception as e:
                print(f"[WARN] Servo move failed: {e}")

    def move_to_category(self, category):
        angle = SERVO_ANGLE_MAP.get(category, SERVO_HOME_ANGLE)
        self.move(angle)

    def reset(self):
        self.move(SERVO_HOME_ANGLE)
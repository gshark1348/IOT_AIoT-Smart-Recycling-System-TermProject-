from .led import LEDController
from .buzzer import BuzzerController
from .motion import MotionController
from .servo import ServoController
from .ultrasonic import UltrasonicController
from .dht_sensor import DHTController
from .loadcell import LoadCellController

class Hardware:
    def __init__(self):
        self._led = LEDController()
        self._buzzer = BuzzerController()
        self._motion = MotionController()
        self._servo = ServoController()
        self._ultrasonic = UltrasonicController()
        self._dht = DHTController()
        self._loadcell = LoadCellController()

    # --- LED API ---
    def led_on(self):
        self._led.on()

    def led_off(self):
        self._led.off()

    # --- Buzzer API ---
    def buzzer_on(self, tone_hz=None, duty=None):
        self._buzzer.on(tone_hz, duty)

    def buzzer_off(self):
        self._buzzer.off()

    # --- Motion API ---
    def motion_detected(self):
        return self._motion.is_detected()

    # --- Servo API ---
    def move_servo(self, angle):
        self._servo.move(angle)

    def move_to_category(self, category):
        self._servo.move_to_category(category)

    def reset_servo(self):
        self._servo.reset()

    # --- Ultrasonic API ---
    def get_distance_cm(self):
        return self._ultrasonic.get_distance_cm()

    def is_inlet_safe(self):
        return self._ultrasonic.is_safe()

    # --- DHT API ---
    def read_temp_humidity(self):
        return self._dht.read_temp_humidity()

    # --- Loadcell API ---
    def read_weight_kg(self):
        return self._loadcell.read_weight_kg()

    def tare_loadcell(self):
        return self._loadcell.tare()

    def check_full(self):
        return self._loadcell.check_full()
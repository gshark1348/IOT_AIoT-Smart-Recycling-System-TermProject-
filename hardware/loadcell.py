import time
from config import USE_LOADCELL, PIN_HX711_DT, PIN_HX711_SCK, HX711_CALIBRATION_FACTOR, FULL_WEIGHT_THRESHOLD_KG

class SimpleHX711:
    """HX711 로드셀 값을 읽기 위한 내부 헬퍼 클래스"""
    def __init__(self, dout_pin, sck_pin):
        from gpiozero import DigitalInputDevice, DigitalOutputDevice
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

        self.sck.on()
        self.sck.off()

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


class LoadCellController:
    def __init__(self):
        self.hx711 = None
        if USE_LOADCELL:
            try:
                self.hx711 = SimpleHX711(PIN_HX711_DT, PIN_HX711_SCK)
                self.hx711.tare()
            except Exception as e:
                print(f"[WARN] HX711 initialization failed: {e}")

    def read_weight_kg(self):
        if not self.hx711:
            return 0.0
        try:
            return self.hx711.get_weight_kg()
        except Exception:
            return 0.0

    def tare(self):
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
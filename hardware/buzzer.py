from config import USE_BUZZER, PIN_BUZZER, BUZZER_LOW_LEVEL_TRIGGER, BUZZER_TONE_HZ, BUZZER_DUTY

class BuzzerController:
    def __init__(self):
        self.buzzer = None
        if USE_BUZZER:
            try:
                from gpiozero import PWMOutputDevice
                self.buzzer = PWMOutputDevice(
                    PIN_BUZZER, 
                    active_high=not BUZZER_LOW_LEVEL_TRIGGER, 
                    initial_value=0, 
                    frequency=BUZZER_TONE_HZ
                )
            except Exception as e:
                print(f"[WARN] Buzzer initialization failed: {e}")

    def on(self, tone_hz=None, duty=None):
        if self.buzzer:
            try:
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

    def off(self):
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
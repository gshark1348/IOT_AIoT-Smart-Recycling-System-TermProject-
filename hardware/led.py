from config import USE_LED, PIN_LED

class LEDController:
    def __init__(self):
        self.led = None
        if USE_LED:
            try:
                from gpiozero import LED
                self.led = LED(PIN_LED)
            except Exception as e:
                print(f"[WARN] LED initialization failed: {e}")

    def on(self):
        if self.led:
            self.led.on()

    def off(self):
        if self.led:
            self.led.off()
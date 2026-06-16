from config import USE_DHT, PIN_DHT, DHT_SENSOR_TYPE

class DHTController:
    def __init__(self):
        self.dht = None
        if not USE_DHT:
            return
            
        try:
            import board
            import adafruit_dht
            
            dht_pin = getattr(board, f"D{PIN_DHT}")
            if DHT_SENSOR_TYPE.upper() == "DHT11":
                self.dht = adafruit_dht.DHT11(dht_pin, use_pulseio=False)
            else:
                self.dht = adafruit_dht.DHT22(dht_pin, use_pulseio=False)
        except Exception as e:
            print(f"[WARN] DHT initialization failed: {e}")

    def read_temp_humidity(self):
        if not self.dht:
            return None, None
        try:
            return self.dht.temperature, self.dht.humidity
        except Exception:
            return None, None
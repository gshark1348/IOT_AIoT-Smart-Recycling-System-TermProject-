import cv2
import time

from config import *

try:
    from picamera2 import Picamera2
    PICAMERA_OK = True
except Exception as e:
    print("[WARN] Picamera2 로드 실패:", e)
    PICAMERA_OK = False

# ============================================================
# 카메라 제어
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

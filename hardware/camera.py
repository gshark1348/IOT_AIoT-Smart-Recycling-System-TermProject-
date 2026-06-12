import time
import cv2
import gc
from config import CAMERA_WIDTH, CAMERA_HEIGHT

class CameraController:
    def __init__(self):
        self.picam2 = None
        self.cap = None
        self.use_picamera2 = False

    def start(self):
        try:
            from picamera2 import Picamera2 #type: ignore
            self.picam2 = Picamera2()
            config = self.picam2.create_preview_configuration(
                main={
                    "size": (CAMERA_WIDTH, CAMERA_HEIGHT),
                    "format": "RGB888"
                }
            )
            self.picam2.configure(config)
            self.picam2.start()
            self.use_picamera2 = True
            time.sleep(0.5)
        except Exception as e:
            print("[Camera] Picamera2 failed:", e)
            try:
                if self.picam2 is not None:
                    try:
                        self.picam2.stop()
                    except Exception:
                        pass
                    try:
                        self.picam2.close()
                    except Exception:
                        pass
            except Exception:
                pass
            self.picam2 = None
            
            try:
                self.cap = cv2.VideoCapture(0)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            except Exception:
                pass

        return self.use_picamera2 or (self.cap is not None and self.cap.isOpened())

    def get_frame(self):
        if self.use_picamera2:
            frame_rgb = self.picam2.capture_array()
            return True, frame_rgb
        else:
            if self.cap is not None and self.cap.isOpened():
                ok, frame_bgr = self.cap.read()
                if not ok:
                    return False, None
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                return True, frame_rgb
            return False, None

    def stop(self):
        try:
            if self.picam2 is not None:
                try:
                    self.picam2.stop()
                except Exception:
                    pass
                try:
                    self.picam2.close()
                except Exception:
                    pass
        except Exception:
            pass

        try:
            gc.collect()
        except Exception:
            pass

        try:
            if self.cap is not None:
                self.cap.release()
        except Exception:
            pass
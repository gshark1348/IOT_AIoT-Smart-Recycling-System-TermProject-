from config import *

try:
    from ultralytics import YOLO
    YOLO_OK = True
except Exception as e:
    print("[INFO] ultralytics 미설치 또는 로드 실패. 수동 선택 모드 사용:", e)
    YOLO_OK = False

# ============================================================
# 6. YOLO 분류
# ============================================================

class Classifier:
    def __init__(self):
        self.model = None

        if YOLO_OK and MODEL_FILE.exists():
            try:
                self.model = YOLO(str(MODEL_FILE))
                print("[INFO] YOLO model loaded:", MODEL_FILE)
            except Exception as e:
                print("[WARN] YOLO model load failed:", e)
        else:
            print("[INFO] models/best.pt not found. Manual selection mode will be used.")

    def classify(self, image_path):
        if self.model is None:
            return {
                "detected": False,
                "label": None,
                "category": None,
                "confidence": 0.0,
                "image_path": str(image_path)
            }

        try:
            results = self.model(str(image_path), imgsz=640, conf=0.25, verbose=False)
            result = results[0]

            if result.boxes is None or len(result.boxes) == 0:
                return {
                    "detected": False,
                    "label": None,
                    "category": None,
                    "confidence": 0.0,
                    "image_path": str(image_path)
                }

            best_box = None
            best_conf = -1.0

            for box in result.boxes:
                conf = float(box.conf[0])
                if conf > best_conf:
                    best_conf = conf
                    best_box = box

            cls_id = int(best_box.cls[0])
            label = str(self.model.names[cls_id])
            key = label.strip().lower()

            category = CLASS_TO_CATEGORY.get(key)

            if category is None:
                for cat in CATEGORIES:
                    if key == cat.lower():
                        category = cat
                        break

            return {
                "detected": True,
                "label": label,
                "category": category,
                "confidence": best_conf,
                "image_path": str(image_path)
            }

        except Exception as e:
            print("[WARN] YOLO inference failed:", e)
            return {
                "detected": False,
                "label": None,
                "category": None,
                "confidence": 0.0,
                "image_path": str(image_path)
            }

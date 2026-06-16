import csv
import json
import hashlib
from datetime import datetime
import cv2
import numpy as np

from config import *

# ============================================================
# 파일 저장, 로그, 통계
# ============================================================

def save_capture(frame):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = CAPTURE_DIR / f"{timestamp}.jpg"
    cv2.imwrite(str(path), frame)
    return path


def frame_diff(prev_frame, cur_frame):
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    cur_gray = cv2.cvtColor(cur_frame, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(prev_gray, cur_gray)
    return float(np.mean(diff))


LOG_COLUMNS = [
    "Time",
    "User ID",
    "User Total Points",
    "Predicted Category",
    "Final Category",
    "Method",
    "Confidence",
    "User Confirmed",
    "Earned Points",
    "Bin Weight",
    "Image Path",
    "Status",
]


def hash_pin(pin):
    return hashlib.sha256(str(pin).encode("utf-8")).hexdigest()


def load_users():
    if not USER_FILE.exists():
        return {}

    try:
        with open(USER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data

        return {}

    except Exception as e:
        print("[WARN] Failed to load users:", e)
        return {}


def save_users(users):
    try:
        with open(USER_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        return True

    except Exception as e:
        print("[WARN] Failed to save users:", e)
        return False


def create_user(user_id, pin):
    users = load_users()

    if user_id in users:
        return False, "ID code already exists."

    users[user_id] = {
        "id": user_id,
        "name": f"User {user_id}",
        "pin_hash": hash_pin(pin),
        "points": 0,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    ok = save_users(users)
    return ok, "User registered successfully." if ok else "Failed to save user."

def validate_user(user_id, pin):
    users = load_users()
    user = users.get(user_id)

    if not user:
        return False, None

    if user.get("pin_hash") != hash_pin(pin):
        return False, None

    return True, user


def add_user_points(user_id, points):
    users = load_users()
    user = users.get(user_id)

    if not user:
        return None

    current = int(user.get("points", 0))
    current += int(points)
    user["points"] = current
    users[user_id] = user
    save_users(users)

    return current


def get_user_points(user_id):
    users = load_users()
    user = users.get(user_id)

    if not user:
        return 0

    return int(user.get("points", 0))


def ensure_log_file_schema():
    if not LOG_FILE.exists():
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=LOG_COLUMNS)
            writer.writeheader()
        return

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            old_fields = reader.fieldnames or []
            rows = list(reader)

        if all(col in old_fields for col in LOG_COLUMNS):
            return

        migrated = []

        for row in rows:
            user_id = row.get("User ID", "Guest") or "Guest"
            earned = row.get("Earned Points", "0") or "0"
            total = row.get("User Total Points", "N/A") or "N/A"
            confirmed = row.get("User Confirmed", "") or ""
            method = row.get("Method", "") or ""

            if not method:
                method = "Auto" if confirmed.strip().lower() in ["yes", "auto", "true"] else "Manual"

            migrated.append({
                "Time": row.get("Time", ""),
                "User ID": user_id,
                "User Total Points": total,
                "Predicted Category": row.get("Predicted Category", ""),
                "Final Category": row.get("Final Category", ""),
                "Method": method,
                "Confidence": row.get("Confidence", ""),
                "User Confirmed": confirmed,
                "Earned Points": earned,
                "Bin Weight": row.get("Bin Weight", ""),
                "Image Path": row.get("Image Path", ""),
                "Status": row.get("Status", ""),
            })

        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=LOG_COLUMNS)
            writer.writeheader()
            writer.writerows(migrated)

        print("[INFO] Existing sorting_log.csv migrated to new user log schema.")

    except Exception as e:
        print("[WARN] Failed to migrate log schema:", e)


def save_log(
    predicted,
    final,
    confidence,
    confirmed,
    weight,
    image_path,
    status,
    user_id="Guest",
    earned_points=0,
    user_total_points="N/A"
):
    ensure_log_file_schema()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    confirmed_text = str(confirmed or "")

    method = "Auto" if confirmed_text.strip().lower() in ["yes", "auto", "true"] else "Manual"

    if method == "Auto":
        try:
            conf_text = f"{float(confidence):.3f}"
        except Exception:
            conf_text = "N/A"
    else:
        conf_text = "N/A"

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_COLUMNS)
        writer.writerow({
            "Time": now,
            "User ID": user_id or "Guest",
            "User Total Points": user_total_points if user_total_points is not None else "N/A",
            "Predicted Category": predicted or "",
            "Final Category": final or "",
            "Method": method,
            "Confidence": conf_text,
            "User Confirmed": confirmed or "",
            "Earned Points": str(earned_points),
            "Bin Weight": f"{weight:.3f}kg" if isinstance(weight, (int, float)) else str(weight),
            "Image Path": image_path or "",
            "Status": status,
        })

def clear_logs():
    if LOG_FILE.exists():
        LOG_FILE.unlink()


def today_stats():
    stats = {cat: 0 for cat in CATEGORIES}
    today = datetime.now().strftime("%Y-%m-%d")

    if not LOG_FILE.exists():
        return stats

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            if row.get("Time", "").startswith(today):
                cat = row.get("Final Category", "")
                if cat in stats:
                    stats[cat] += 1

    return stats

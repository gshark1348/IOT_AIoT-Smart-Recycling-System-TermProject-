# AIoT Smart Recycling System with Raspberry Pi 5

An AIoT-based smart recycling kiosk prototype built with **Raspberry Pi 5**, **camera-based waste classification**, **touch display UI**, **YOLO/manual sorting**, **user point rewards**, **motion-based screen control**, **buzzer feedback**, and **CSV logging**.

This project is designed as an integrated smart recycling system that helps users classify waste into major recycling categories and provides sorting guidance, feedback sounds, and operation logs for monitoring and demonstration purposes.

---

## 1. Project Overview

The **AIoT Smart Recycling System** is a Raspberry Pi 5-based recycling kiosk that combines computer vision, sensors, and an interactive LCD interface.

The system captures a waste image using a Raspberry Pi camera or USB camera, attempts to classify it using a YOLO model, and then guides the user through the correct recycling category. If the AI model is missing or the confidence is too low, the system automatically falls back to manual selection mode.

The system also supports optional hardware features such as a servo motor, ultrasonic sensor, DHT temperature/humidity sensor, HX711 load cell, PIR motion sensor, LED, and piezo buzzer.

---

## 2. Key Features

### AI-Based Waste Classification

* Uses a YOLO model when `models/best.pt` exists.
* Automatically switches to manual selection mode if the model is missing.
* Supports confidence-based decision flow.
* Maps YOLO labels to recycling categories.

### Manual Sorting Mode

* Allows the user to manually select the correct waste category.
* Useful when the AI model confidence is low or the model is unavailable.

### Touch Display UI

* Built with Python Tkinter.
* Designed for an 800x480 7-inch LCD touch display.
* Fullscreen kiosk-style interface.
* Includes home screen, camera preview, result screen, statistics screen, user login/register screen, and admin mode.

### Recycling Categories

The system classifies waste into the following categories:

* Plastic
* Can/Metal
* Paper
* Glass
* General Waste

### User Account and Point System

* Users can register with an ID and PIN.
* PINs are stored as SHA-256 hashes.
* Each successful sorting action can reward points.
* Guest mode is also supported.
* User point data is stored in `logs/users.json`.

### CSV Logging

Each sorting result is saved to a CSV file.

Logged information includes:

* Time
* User ID
* User total points
* Predicted category
* Final category
* Sorting method
* Confidence
* User confirmation
* Earned points
* Bin weight
* Image path
* Status

The log file is stored at:

```text
logs/sorting_log.csv
```

### Motion-Based Screen Control

* Uses a PIR motion sensor.
* If no motion is detected for a configured time, the display is turned off or covered with a black overlay.
* When motion is detected again, the screen is restored.
* This helps reduce power usage and screen burn-in during idle time.

### Buzzer Feedback

The system provides buzzer feedback for:

* Button click sound
* Point reward sound
* Fire alarm siren pattern

### Fire Alarm Mode

* Optional DHT temperature monitoring.
* If temperature remains above a configured threshold, the system displays a fire alarm screen and plays an alarm sound.
* The alarm is cleared after the temperature returns to a safe range for a configured duration.

### Admin Mode

Admin mode provides maintenance and testing features such as:

* Sensor status check
* Servo motor test
* Camera test
* Log reset
* System information monitoring

Default admin password:

```text
0000
```

It is recommended to change this value before deployment.

---

## 3. System Workflow

The basic sorting workflow is as follows:

```text
1. User logs in or continues as guest
2. User places waste on the tray
3. User presses the Sort button
4. Camera preview starts
5. System waits until the frame becomes stable
6. Image is captured and saved
7. YOLO classification is attempted
8. If classification is successful:
   - User confirms or corrects the result
9. If classification fails:
   - Manual category selection is shown
10. System saves the result to CSV log
11. User earns points if logged in
12. Result and recycling guide are displayed
13. Servo/LED/buzzer actions are triggered if enabled
```

---

## 4. Hardware Requirements

### Main Hardware

* Raspberry Pi 5
* Raspberry Pi OS
* 7-inch HDMI LCD touch display
* Raspberry Pi Camera Module or USB camera
* MicroSD card
* 5V power supply

### Optional Sensors and Actuators

* PIR motion sensor
* Piezo buzzer
* LED
* Servo motor
* HC-SR04 ultrasonic sensor
* DHT11 or DHT22 temperature/humidity sensor
* HX711 load cell amplifier
* Load cell

---

## 5. GPIO Pin Map

The project uses **BCM GPIO numbering**.

| Component        | GPIO Pin | Physical Pin | Description                     |
| ---------------- | -------: | -----------: | ------------------------------- |
| DHT11/DHT22 DATA |    GPIO4 |        Pin 7 | Temperature and humidity sensor |
| HC-SR04 TRIG     |   GPIO23 |       Pin 16 | Ultrasonic trigger              |
| HC-SR04 ECHO     |   GPIO24 |       Pin 18 | Ultrasonic echo                 |
| Servo Signal     |   GPIO18 |       Pin 12 | Sorting plate servo motor       |
| LED              |   GPIO27 |       Pin 13 | Status LED                      |
| Buzzer           |   GPIO22 |       Pin 15 | Piezo buzzer                    |
| PIR Motion OUT   |   GPIO25 |       Pin 22 | Motion detection sensor         |
| HX711 DT/DOUT    |    GPIO5 |       Pin 29 | Load cell data                  |
| HX711 SCK/CLK    |    GPIO6 |       Pin 31 | Load cell clock                 |

> Important: The HC-SR04 echo pin outputs 5V. Raspberry Pi GPIO pins are 3.3V logic. Use a voltage divider or level shifter for the ECHO pin.

---

## 6. Software Requirements

The project is written in Python and uses the following main libraries:

* Tkinter
* OpenCV
* NumPy
* Pillow
* Picamera2
* gpiozero
* lgpio
* ultralytics
* adafruit-circuitpython-dht

---

## 7. Project Structure

Recommended repository structure:

```text
aiot-smart-recycling/
├── app.py
├── README.md
├── models/
│   └── best.pt
├── captures/
│   └── captured images
├── logs/
│   ├── sorting_log.csv
│   └── users.json
└── .gitignore
```

### Important Files

| File or Directory      | Description                      |
| ---------------------- | -------------------------------- |
| `app.py`               | Main integrated application code |
| `models/best.pt`       | YOLO model file                  |
| `captures/`            | Saved waste images               |
| `logs/sorting_log.csv` | Sorting result log               |
| `logs/users.json`      | User account and point data      |
| `.gitignore`           | Git ignore rules                 |

---

## 8. Installation

### Step 1. Update Raspberry Pi

```bash
sudo apt update
sudo apt upgrade -y
```

### Step 2. Install System Packages

```bash
sudo apt install -y \
  python3-pip \
  python3-venv \
  python3-tk \
  python3-opencv \
  python3-pil \
  python3-picamera2 \
  python3-gpiozero \
  python3-lgpio \
  libatlas-base-dev
```

### Step 3. Create Project Directory

```bash
mkdir -p ~/aiot_smart_recycling
cd ~/aiot_smart_recycling
```

Place `app.py` inside this directory.

### Step 4. Create Required Folders

```bash
mkdir -p models captures logs
```

### Step 5. Create Python Virtual Environment

Using `--system-site-packages` is recommended because Picamera2 and some Raspberry Pi packages are often installed through apt.

```bash
python3 -m venv --system-site-packages venv
source venv/bin/activate
```

### Step 6. Install Python Packages

```bash
pip install --upgrade pip
pip install numpy pillow ultralytics adafruit-circuitpython-dht
```

If OpenCV is not available through apt, install it with pip:

```bash
pip install opencv-python
```

---

## 9. YOLO Model Setup

Place your trained YOLO model at:

```text
models/best.pt
```

The application checks this path automatically:

```python
MODEL_PATH = "models/best.pt"
```

If the model file does not exist, the system will run in manual selection mode.

---

## 10. Label Mapping

The system maps YOLO model labels to recycling categories through `CLASS_TO_CATEGORY`.

Example:

```python
CLASS_TO_CATEGORY = {
    "plastic": "Plastic",
    "plastic bottle": "Plastic",
    "bottle": "Plastic",
    "pet bottle": "Plastic",

    "can": "Can/Metal",
    "metal": "Can/Metal",
    "aluminum can": "Can/Metal",

    "paper": "Paper",
    "cardboard": "Paper",

    "glass": "Glass",
    "glass bottle": "Glass",

    "general waste": "General Waste",
    "trash": "General Waste",
    "waste": "General Waste",
}
```

If your YOLO model uses different class names, update this dictionary.

---

## 11. Configuration

Most user-editable settings are located near the top of `app.py`.

### Sensor Enable Settings

```python
USE_DHT = False
USE_ULTRASONIC = False
USE_SERVO = False
USE_LED = True
USE_BUZZER = True
USE_MOTION_SENSOR = True
USE_LOADCELL = False
```

If a hardware component is not connected, set the corresponding option to `False`.

### Camera Settings

```python
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 10
```

### Classification Confidence

```python
MIN_CONFIDENCE = 0.25
```

If the AI model is too sensitive, increase this value.
If the model often fails to classify objects, decrease this value.

### Frame Stability Settings

```python
FRAME_DIFF_THRESHOLD = 15.0
STABLE_TIME_SEC = 2
STABILITY_TIMEOUT_SEC = 10
```

These values control automatic image capture based on frame stability.

### Motion Screen-Off Settings

```python
MOTION_SCREEN_OFF_SEC = 30
MOTION_CHECK_INTERVAL_MS = 1000
```

If no motion is detected for 30 seconds, the screen is turned off or covered with a black overlay.

### Point Reward

```python
POINT_PER_SORT = 10
```

Each successful sorting action gives 10 points to a logged-in user.

### Admin Password

```python
ADMIN_PASSWORD = "0000"
```

Change this value before using the system in a real environment.

---

## 12. Running the Application

Move to the project directory:

```bash
cd ~/aiot_smart_recycling
```

Activate the virtual environment:

```bash
source venv/bin/activate
```

Run the application:

```bash
python app.py
```

To exit fullscreen mode, press:

```text
ESC
```

---

## 13. Running on Boot

To run the application automatically when Raspberry Pi starts, create a systemd service.

### Step 1. Create Service File

```bash
sudo nano /etc/systemd/system/aiot-smart-recycling.service
```

### Step 2. Add the Following Content

Update the project path if needed.

```ini
[Unit]
Description=AIoT Smart Recycling System
After=graphical.target

[Service]
User=pi
WorkingDirectory=/home/pi/aiot_smart_recycling
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/pi/.Xauthority
ExecStart=/home/pi/aiot_smart_recycling/venv/bin/python /home/pi/aiot_smart_recycling/app.py
Restart=on-failure

[Install]
WantedBy=graphical.target
```

### Step 3. Enable the Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable aiot-smart-recycling.service
sudo systemctl start aiot-smart-recycling.service
```

### Step 4. Check Status

```bash
systemctl status aiot-smart-recycling.service
```

---

## 14. Log Format

The sorting log is saved as:

```text
logs/sorting_log.csv
```

The CSV columns are:

```text
Time
User ID
User Total Points
Predicted Category
Final Category
Method
Confidence
User Confirmed
Earned Points
Bin Weight
Image Path
Status
```

Example log row:

```text
2026-06-10 21:30:12, user01, 120, Plastic, Plastic, Auto, 0.842, Yes, 10, 0.000kg, captures/2026-06-10_21-30-12.jpg, Completed
```

---

## 15. User Data

User account data is saved in:

```text
logs/users.json
```

PIN values are not stored directly.
They are stored as SHA-256 hashes.

Example structure:

```json
{
  "user01": {
    "id": "user01",
    "name": "User user01",
    "pin_hash": "hashed_pin_value",
    "points": 50,
    "created_at": "2026-06-10 21:00:00"
  }
}
```

---

## 16. Admin Mode

Admin mode is used for maintenance and testing.

Typical admin features include:

* Sensor status check
* Servo test
* Camera test
* Log reset
* System path check
* Model status check

Default password:

```text
0000
```

For security, change this value in `app.py`.

---

## 17. Recommended `.gitignore`

Create a `.gitignore` file:

```bash
nano .gitignore
```

Recommended content:

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
venv/
.env

# Logs and generated files
logs/
captures/

# Model weights
models/*.pt
models/*.onnx

# OS files
.DS_Store
Thumbs.db

# IDE files
.vscode/
.idea/
```

If you want to share a small demo model, you may remove `models/*.pt` from `.gitignore`.
However, large model files are usually better managed with Git LFS or released separately.

---

## 18. Troubleshooting

### 1. GPIO does not work on Raspberry Pi 5

This project uses `lgpio` through gpiozero.

Make sure the following environment variable is set before importing gpiozero:

```python
os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")
```

Also install lgpio:

```bash
sudo apt install -y python3-lgpio
```

### 2. Camera does not open

Check whether the camera is detected:

```bash
rpicam-hello --list-cameras
```

If using a USB camera:

```bash
ls /dev/video*
```

### 3. YOLO model is not loaded

Check that the model exists:

```bash
ls models/best.pt
```

If the file does not exist, the system will use manual mode.

### 4. Touch display does not fit the screen

Check these values in `app.py`:

```python
LCD_WIDTH = 800
LCD_HEIGHT = 480
FULLSCREEN = True
```

Adjust them according to your display resolution.

### 5. Display does not turn off with motion sensor

The code attempts to turn off the display using system commands such as `vcgencmd` and `xset`.
If these commands fail depending on the display environment, the system uses a black fullscreen overlay as a fallback.

### 6. Ultrasonic sensor gives unstable values

Check the wiring carefully.
The HC-SR04 ECHO pin must be converted from 5V to 3.3V before connecting to Raspberry Pi GPIO.

### 7. Servo angle does not match the physical sorting path

Adjust this dictionary:

```python
SERVO_ANGLE_MAP = {
    "Plastic": 20,
    "Can/Metal": 55,
    "Paper": 90,
    "Glass": 125,
    "General Waste": 160,
}
```

Use Admin Mode to test and calibrate the servo angles.

---

## 19. Current Limitations

* The classification performance depends on the quality of the YOLO model.
* The load cell requires calibration for accurate weight measurement.
* The ultrasonic sensor and servo motor must be physically adjusted for the actual bin structure.
* The system currently stores logs locally as CSV files.
* The UI is optimized for 800x480 LCD displays.

---

## 20. Future Improvements

Possible future improvements include:

* Web dashboard for remote monitoring
* Database integration instead of CSV logs
* Cloud-based log backup
* More accurate waste detection model
* Multi-object detection
* QR-based user login
* Automatic bin fullness notification
* Improved model training dataset
* Real-time object detection preview
* Mobile app integration

---

## 21. Example Use Cases

This project can be used for:

* AIoT prototype demonstration
* Smart recycling education
* Computer vision-based waste sorting research
* Raspberry Pi sensor integration practice
* University IoT or embedded system projects
* Environmental technology proof-of-concept

---

## 22. License

This project is provided for educational and prototype purposes.

You may modify and extend the code according to your own hardware configuration and project requirements.

---

## 23. Author

Developed as an AIoT smart recycling prototype using Raspberry Pi 5, camera-based classification, sensor integration, and touch display interaction.

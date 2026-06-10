# AIoT Smart Recycling System

Raspberry Pi 5, LCD Touch Display, Camera, YOLO 모델, GPIO 센서를 활용한 **AIoT 기반 스마트 분리수거 시스템**입니다. 사용자가 쓰레기를 올려놓고 Sort 버튼을 누르면 카메라로 이미지를 캡처하고, YOLO 모델을 통해 분류한 뒤, Servo Motor를 이용해 분류판을 해당 카테고리 방향으로 이동시키는 구조입니다. AI 분류 신뢰도가 낮거나 모델이 없는 경우에는 수동 선택 모드로 전환되어 시연 환경에서도 전체 흐름을 테스트할 수 있습니다.

본 프로젝트는 교내 IoT/AIoT 실습 및 전시 시연을 목적으로 제작되었습니다.

---

## 주요 기능

- **LCD Touch Display 기반 GUI**
  - 800×480 해상도 기준 전체 화면 UI
  - Tkinter 기반 터치 인터페이스
  - 사용자 로그인, 회원가입, 게스트 모드 지원

- **카메라 기반 자동 캡처**
  - Raspberry Pi CSI Camera 우선 사용
  - CSI 카메라 사용 실패 시 USB Camera로 대체
  - 프레임 변화량과 안정 상태를 기반으로 쓰레기 이미지 자동 캡처

- **YOLO 기반 쓰레기 분류**
  - `models/best.pt` 파일이 존재하면 YOLO 모델 자동 로드
  - Plastic, Can/Metal, Paper, Glass, General Waste 분류
  - 모델 미탑재 또는 낮은 confidence 상황에서는 수동 선택 모드 제공

- **분류판 제어**
  - Servo Motor를 이용해 분류 카테고리별 각도로 이동
  - 관리자 모드에서 Servo Test 가능

- **센서 기반 안전 및 상태 확인**
  - 초음파 센서를 이용한 투입구 손/이물질 감지 기능
  - DHT 센서 기반 온습도 측정 및 화재 경보 확장 기능
  - HX711 로드셀 기반 수거함 무게 측정 확장 기능
  - PIR Motion Sensor 기반 화면 절전 기능

- **포인트 및 사용자 관리**
  - 사용자 ID/PIN 기반 로그인
  - PIN은 SHA-256 해시로 저장
  - 분리수거 성공 시 사용자에게 포인트 지급
  - 게스트 사용자는 포인트 적립 없이 분류 기능만 사용 가능

- **로그 및 통계 관리**
  - 분류 결과를 CSV 파일로 저장
  - 사용자별 분리수거 로그 조회
  - 관리자용 전체 로그 확인
  - 당일 카테고리별 통계 화면 제공

- **관리자 모드**
  - 센서 상태 확인
  - Servo 테스트
  - 카메라 테스트
  - 초음파 안전 테스트
  - 화재 경보 테스트
  - 사용자 목록 확인
  - 분류 로그 초기화

---

## 사용 기술

| 구분 | 기술 |
|---|---|
| Language | Python 3 |
| GUI | Tkinter |
| Camera | Picamera2, OpenCV |
| AI Model | Ultralytics YOLO |
| GPIO Control | gpiozero, lgpio |
| Image Processing | OpenCV, NumPy, Pillow |
| Data Logging | CSV, JSON |
| Target Board | Raspberry Pi 5 |

---

## 하드웨어 구성

| 부품 | 용도 |
|---|---|
| Raspberry Pi 5 | 메인 제어 보드 |
| 7-inch LCD Touch Display | 사용자 인터페이스 출력 및 터치 입력 |
| Raspberry Pi Camera 또는 USB Camera | 쓰레기 이미지 캡처 |
| Servo Motor | 분류판 각도 제어 |
| LED | 상태 표시 |
| Piezo Buzzer | 버튼 클릭음, 포인트 적립음, 화재 경보음 |
| PIR Motion Sensor | 모션 감지 기반 화면 절전 |
| HC-SR04 Ultrasonic Sensor | 투입구 안전 확인 |
| DHT22/DHT11 | 온습도 및 화재 경보 확장 |
| HX711 + Load Cell | 수거함 무게 측정 확장 |

---

## GPIO Pin Map

GPIO 번호는 **BCM 번호 기준**입니다.

| 기능 | BCM GPIO | 물리 핀 | 설명 |
|---|---:|---:|---|
| DHT22/DHT11 DATA | GPIO4 | Pin 7 | 온습도 센서 데이터 |
| Ultrasonic TRIG | GPIO23 | Pin 16 | 초음파 센서 Trigger |
| Ultrasonic ECHO | GPIO24 | Pin 18 | 초음파 센서 Echo, 전압 분배 필수 |
| Servo Signal | GPIO18 | Pin 12 | 서보모터 PWM 신호 |
| LED | GPIO27 | Pin 13 | 상태 표시 LED |
| Buzzer | GPIO22 | Pin 15 | 피에조 부저 |
| PIR Motion OUT | GPIO25 | Pin 22 | 모션 감지 센서 출력 |
| HX711 DT/DOUT | GPIO5 | Pin 29 | 로드셀 데이터 |
| HX711 SCK/CLK | GPIO6 | Pin 31 | 로드셀 클럭 |

> HC-SR04의 Echo 출력은 5V일 수 있으므로 Raspberry Pi GPIO 보호를 위해 전압 분배 회로를 반드시 구성해야 합니다.

---

## 프로젝트 구조

```bash
aiot_smart_recycling/
├── app.py
├── models/
│   └── best.pt              # YOLO 학습 모델, 직접 추가
├── captures/                # 자동 생성, 캡처 이미지 저장
├── logs/                    # 자동 생성, 로그 및 사용자 정보 저장
│   ├── sorting_log.csv
│   └── users.json
└── README.md
```

`captures/`, `logs/` 폴더는 프로그램 실행 시 자동으로 생성됩니다. `models/` 폴더와 `best.pt` 파일은 사용자가 직접 준비해야 합니다.

---

## 설치 방법

### 1. 시스템 패키지 설치

```bash
sudo apt update
sudo apt upgrade -y

sudo apt install -y \
  python3-pip \
  python3-venv \
  python3-tk \
  python3-opencv \
  python3-picamera2 \
  python3-gpiozero \
  python3-lgpio
```

### 2. 프로젝트 폴더 생성

```bash
mkdir -p ~/aiot_smart_recycling
cd ~/aiot_smart_recycling
```

`app.py` 파일을 해당 폴더에 복사합니다.

### 3. Python 가상환경 생성

```bash
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install --upgrade pip
```

### 4. Python 패키지 설치

```bash
pip install numpy pillow ultralytics adafruit-circuitpython-dht adafruit-blinka
```

Raspberry Pi 환경에서는 `picamera2`, `opencv`, `gpiozero`는 pip보다 apt 패키지로 설치하는 것이 안정적입니다.

---

## YOLO 모델 준비

YOLO 모델을 사용하는 경우 다음 구조로 모델 파일을 배치합니다.

```bash
mkdir -p models
cp best.pt models/best.pt
```

모델 파일이 없으면 프로그램은 자동으로 수동 선택 모드로 동작합니다.

지원 카테고리는 다음과 같습니다.

```python
Plastic
Can/Metal
Paper
Glass
General Waste
```

모델의 클래스 이름이 코드의 `CLASS_TO_CATEGORY`에 등록되어 있어야 정상적으로 카테고리 매핑이 됩니다. 학습 모델의 class name이 다르다면 `app.py` 상단의 `CLASS_TO_CATEGORY`를 수정하십시오.

---

## 실행 방법

```bash
cd ~/aiot_smart_recycling
source .venv/bin/activate
python app.py
```

전체 화면 모드에서 실행되며, `Esc` 키를 누르면 전체 화면이 해제됩니다.

---

## 기본 사용 흐름

1. 프로그램 실행
2. 회원가입, 로그인 또는 게스트 모드 선택
3. 쓰레기를 카메라 앞에 올림
4. `Sort` 버튼 선택
5. 카메라가 프레임 안정 상태를 확인한 뒤 이미지 캡처
6. YOLO 모델이 카테고리 분류
7. confidence가 낮거나 모델이 없으면 수동 선택
8. 초음파 센서로 투입구 안전 여부 확인
9. Servo Motor가 카테고리별 각도로 이동
10. 사용자가 투입 완료를 누르면 로그 저장
11. 로그인 사용자는 포인트 적립

---

## 주요 설정값

`app.py` 상단에서 하드웨어 사용 여부와 기준값을 수정할 수 있습니다.

```python
USE_DHT = False
USE_ULTRASONIC = False
USE_SERVO = False
USE_LED = True
USE_BUZZER = True
USE_MOTION_SENSOR = True
USE_LOADCELL = False
```

하드웨어가 모두 연결되어 있지 않은 경우에도 UI 및 전체 분류 흐름을 테스트할 수 있도록 일부 센서는 기본적으로 비활성화되어 있습니다. 실제 하드웨어를 연결한 뒤 필요한 값을 `True`로 변경하면 됩니다.

### YOLO 설정

```python
MODEL_PATH = "models/best.pt"
MIN_CONFIDENCE = 0.25
```

### 관리자 비밀번호

```python
ADMIN_PASSWORD = "0000"
```

### 화면 절전 설정

```python
MOTION_SCREEN_OFF_SEC = 30
MOTION_CHECK_INTERVAL_MS = 1000
```

PIR Motion Sensor에서 30초 동안 움직임이 감지되지 않으면 화면이 꺼지거나 검은색 오버레이로 대체됩니다. 움직임이 다시 감지되면 화면이 복구됩니다.

### 포인트 설정

```python
POINT_PER_SORT = 10
```

로그인한 사용자가 분리수거를 성공적으로 완료하면 10 Point가 적립됩니다.

---

## Servo 각도 설정

실제 분류판 구조에 맞게 각도를 조정해야 합니다.

```python
SERVO_ANGLE_MAP = {
    "Plastic": 20,
    "Can/Metal": 55,
    "Paper": 90,
    "Glass": 125,
    "General Waste": 160,
}
```

관리자 모드의 Servo Test 기능을 활용하여 실제 분류함 위치에 맞도록 값을 보정하십시오.

---

## 로그 파일

분류 기록은 다음 파일에 저장됩니다.

```bash
logs/sorting_log.csv
```

저장되는 주요 항목은 다음과 같습니다.

| 항목 | 설명 |
|---|---|
| Time | 분류 시간 |
| User ID | 사용자 ID 또는 Guest |
| User Total Points | 사용자 누적 포인트 |
| Predicted Category | AI 예측 카테고리 |
| Final Category | 최종 선택 카테고리 |
| Method | Auto 또는 Manual |
| Confidence | AI confidence |
| User Confirmed | 사용자 확인 여부 |
| Earned Points | 적립 포인트 |
| Bin Weight | 수거함 무게 |
| Image Path | 캡처 이미지 경로 |
| Status | 처리 상태 |

사용자 정보는 다음 파일에 저장됩니다.

```bash
logs/users.json
```

PIN은 원문이 아닌 SHA-256 해시로 저장됩니다.

---

## 관리자 모드

초기 관리자 비밀번호는 다음과 같습니다.

```text
0000
```

관리자 모드에서 사용할 수 있는 기능은 다음과 같습니다.

- 센서 상태 확인
- 초음파 안전 테스트
- Servo Motor 테스트
- 카메라 테스트
- 화재 경보 테스트
- 수거함 무게 초기화
- 사용자 목록 확인
- 전체 분류 로그 확인
- 로그 초기화

GitHub 공개 전에는 `ADMIN_PASSWORD` 값을 반드시 변경하는 것을 권장합니다.

---

## GitHub 업로드 시 제외 권장 파일

개인정보, 실행 로그, 캡처 이미지, 학습 모델은 용량 또는 개인정보 문제로 GitHub에 직접 올리지 않는 것을 권장합니다.

`.gitignore` 예시는 다음과 같습니다.

```gitignore
# Python
__pycache__/
*.pyc
.venv/

# Runtime data
captures/
logs/*.csv
logs/users.json

# Model files
models/*.pt
models/*.onnx

# OS / Editor
.DS_Store
.vscode/
.idea/
```

모델 파일을 함께 관리해야 한다면 Git LFS 사용을 권장합니다.

---

## 주의사항

- Raspberry Pi 5에서는 GPIO 제어를 위해 `lgpio` 기반 pin factory를 사용합니다.
- HC-SR04 Echo 핀은 Raspberry Pi GPIO에 직접 연결하지 말고 전압 분배 회로를 사용해야 합니다.
- 로드셀 무게 측정은 실제 하드웨어 환경에 맞게 `HX711_CALIBRATION_FACTOR` 보정이 필요합니다.
- Servo Motor 각도는 분류함 구조에 따라 반드시 재조정해야 합니다.
- `USE_DHT`, `USE_ULTRASONIC`, `USE_SERVO`, `USE_LOADCELL` 값이 `False`이면 해당 하드웨어 기능은 시연용 흐름으로만 동작합니다.
- 공개 저장소에 업로드할 경우 관리자 비밀번호, 사용자 로그, 캡처 이미지는 제외하는 것이 좋습니다.

---

## 향후 개선 방향

- 분류 모델 정확도 향상을 위한 데이터셋 추가 수집
- 카테고리별 객체 검출 박스 시각화 개선
- 관리자 웹 대시보드 연동
- 수거함 가득 참 알림 기능 고도화
- 포인트 시스템 DB 연동
- 사용자별 친환경 기여도 통계 제공
- 시스템 자동 실행 서비스 등록

---

## License

This project is for educational and demonstration purposes.  
라이선스는 프로젝트 공개 범위에 맞게 별도로 지정할 수 있습니다.

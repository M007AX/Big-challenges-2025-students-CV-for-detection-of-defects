from flask import Blueprint, Response
import cv2
from ultralytics import YOLO
import threading
import torch
import time
import requests
from datetime import datetime, timezone

video_bp = Blueprint('video', __name__)

# Проверяем доступность GPU
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"🖥️  Используемое устройство: {device}")
if device == 'cuda':
    print(f"📊 GPU: {torch.cuda.get_device_name(0)}")
    print(f"📈 CUDA версия: {torch.version.cuda}")

model = YOLO('yolov8n.pt').to(device)

cap1 = None
cap2 = None

frame_lock1 = threading.Lock()
frame_lock2 = threading.Lock()
current_frame1 = None
current_frame2 = None

MAX_FPS = 15
FRAME_TIME = 1.0 / MAX_FPS

# Адрес сервера для отправки координат
SERVER_URL = 'http://127.0.0.1:5001/api/coordinates/receive'

# Последнее время отправки (раз в секунду)
last_send_time = {}


def init_camera(camera_id, camera_num):
    global cap1, cap2

    try:
        if camera_num == 1:
            if cap1:
                cap1.release()
            cap1 = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            cap1.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap1.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            last_send_time[1] = 0
            print(f"✓ Камера 1 инициализирована: ID {camera_id}")
        else:
            if cap2:
                cap2.release()
            cap2 = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            cap2.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap2.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            last_send_time[2] = 0
            print(f"✓ Камера 2 инициализирована: ID {camera_id}")
    except Exception as e:
        print(f"✗ Ошибка инициализации камеры {camera_num}: {e}")


def detect_persons(frame):
    """Детекция людей и возврат их координат"""
    persons = []

    try:
        results = model(frame, conf=0.5, verbose=False, device=device)

        for result in results:
            for box in result.boxes:
                if int(box.cls) == 0:  # person
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])

                    # Центр объекта
                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2

                    persons.append({
                        'x': center_x,
                        'y': center_y,
                        'confidence': conf
                    })
    except Exception as e:
        print(f"✗ Ошибка детекции: {e}")

    return persons


def send_coordinates(persons, camera_num):
    current_time = time.time()

    if camera_num in last_send_time:
        if current_time - last_send_time[camera_num] < 1: # частота отправки сигнала
            return

    last_send_time[camera_num] = current_time

    # НОВОЕ: отправляем данные даже если людей нет
    utc_time = datetime.now(timezone.utc).isoformat()

    if persons:  # Человек(и) найдены
        person = persons[0]
        data = {
            'camera_id': camera_num,
            'x': person['x'],
            'y': person['y'],
            'confidence': person['confidence'],
            'has_person': True,  # ← НОВОЕ
            'timestamp': utc_time
        }
        print(f"✓ Камера {camera_num}: Найден человек X={person['x']}, Y={person['y']}")
    else:  # Людей не найдено
        data = {
            'camera_id': camera_num,
            'x': 320,  # Центр
            'y': 240,  # Центр
            'confidence': 0,
            'has_person': False,  # ← НОВОЕ
            'timestamp': utc_time
        }
        print(f"⚠️  Камера {camera_num}: Человек не найден")

    try:
        response = requests.post(SERVER_URL, json=data, timeout=2)
        if response.status_code != 200:
            print(f"✗ Ошибка отправки: {response.status_code}")
    except Exception as e:
        print(f"✗ Ошибка подключения: {e}")


def process_frame(frame, camera_num):
    """Обработка кадра: детекция, рисование боксов"""
    frame_copy = frame.copy()

    persons = detect_persons(frame)

    # Отправляем координаты на сервер
    send_coordinates(persons, camera_num)

    # Рисуем боксы вокруг людей
    for person_data in persons:
        # Получаем дополнительные данные через еще один запрос (если нужны координаты бокса)
        results = model(frame, conf=0.5, verbose=False, device=device)
        for result in results:
            for box in result.boxes:
                if int(box.cls) == 0:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])
                    cv2.rectangle(frame_copy, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame_copy, f'Person: {conf:.2f}', (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    return frame_copy


def update_frames_camera1():
    global current_frame1
    last_time = time.time()

    while True:
        if cap1 is None:
            continue

        current_time = time.time()
        if current_time - last_time < FRAME_TIME:
            time.sleep(0.001)
            continue

        last_time = current_time

        ret, frame = cap1.read()
        if not ret:
            continue

        processed = process_frame(frame, 1)

        with frame_lock1:
            current_frame1 = processed


def update_frames_camera2():
    global current_frame2
    last_time = time.time()

    while True:
        if cap2 is None:
            continue

        current_time = time.time()
        if current_time - last_time < FRAME_TIME:
            time.sleep(0.001)
            continue

        last_time = current_time

        ret, frame = cap2.read()
        if not ret:
            continue

        processed = process_frame(frame, 2)

        with frame_lock2:
            current_frame2 = processed


@video_bp.route('/cameras', methods=['GET'])
def get_cameras():
    from flask import jsonify
    max_tested = 10
    available_cameras = []
    for i in range(max_tested):
        test_cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if test_cap is None or not test_cap.isOpened():
            test_cap.release()
            continue
        available_cameras.append({"id": i, "name": f"Camera {i}"})
        test_cap.release()
    return jsonify(available_cameras)


@video_bp.route('/select_camera/<int:camera_num>/<int:camera_id>', methods=['POST'])
def select_camera(camera_num, camera_id):
    from flask import jsonify
    init_camera(camera_id, camera_num)
    return jsonify({"camera_num": camera_num, "camera_id": camera_id})


@video_bp.route('/feed1')
def video_feed1():
    def generate():
        while True:
            with frame_lock1:
                if current_frame1 is None:
                    continue
                ret, buffer = cv2.imencode('.jpg', current_frame1)
                frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@video_bp.route('/feed2')
def video_feed2():
    def generate():
        while True:
            with frame_lock2:
                if current_frame2 is None:
                    continue
                ret, buffer = cv2.imencode('.jpg', current_frame2)
                frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


init_camera(0, 1)
init_camera(0, 2)
print(f"⏱️  Ограничение FPS: {MAX_FPS} кадров/сек")
print(f"📡 Сервер координат: {SERVER_URL}")
threading.Thread(target=update_frames_camera1, daemon=True).start()
threading.Thread(target=update_frames_camera2, daemon=True).start()

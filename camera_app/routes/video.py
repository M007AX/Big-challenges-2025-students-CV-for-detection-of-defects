from flask import Blueprint, Response, jsonify
import cv2
from ultralytics import YOLO
import threading
import torch
import time
import requests
from datetime import datetime, timezone
import platform
import os

video_bp = Blueprint('video', __name__)

# Проверяем доступность GPU
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"🖥️  Используемое устройство: {device}")
if device == 'cuda':
    print(f"📊 GPU: {torch.cuda.get_device_name(0)}")
    print(f"📈 CUDA версия: {torch.version.cuda}")

# Выбор backend камеры в зависимости от ОС
OS_NAME = platform.system()
if OS_NAME == 'Windows':
    CAMERA_BACKEND = cv2.CAP_DSHOW       # DirectShow для Windows
elif OS_NAME == 'Linux':
    CAMERA_BACKEND = cv2.CAP_V4L2        # V4L2 для Linux
else:
    CAMERA_BACKEND = cv2.CAP_ANY         # Пусть OpenCV сам выберет backend

print(f"🎥  ОС: {OS_NAME}, backend камеры: {CAMERA_BACKEND}")

model = YOLO('/home/sirius/PycharmProjects/Big-challenges-2025-students-CV-for-detection-of-defects1/brak_ok_no_gaus.pt').to(device)

cap1 = None
cap2 = None

frame_lock1 = threading.Lock()
frame_lock2 = threading.Lock()
current_frame1 = None
current_frame2 = None

MAX_FPS = 60
FRAME_TIME = 1.0 / MAX_FPS

# Адрес сервера для отправки координат
SERVER_URL = 'http://127.0.0.1:5001/api/coordinates/receive'

# Последнее время отправки (раз в секунду)
last_send_time = {}


def init_camera(camera_id, camera_num):
    """
    Инициализация камеры с заданным ID и номером (1 или 2).
    Делает кроссплатформенный выбор backend и проверяет isOpened().
    """
    global cap1, cap2

    try:
        if camera_num == 1:
            # Закрываем предыдущий объект, если был
            if cap1 is not None:
                cap1.release()

            cap1 = cv2.VideoCapture(camera_id, CAMERA_BACKEND)

            if not cap1.isOpened():
                print(f"✗ Камера 1 не открылась: ID {camera_id}")
                cap1.release()
                cap1 = None
                return

            cap1.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
            cap1.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
            last_send_time[1] = 0
            print(f"✓ Камера 1 инициализирована: ID {camera_id}")

        else:
            if cap2 is not None:
                cap2.release()

            cap2 = cv2.VideoCapture(camera_id, CAMERA_BACKEND)

            if not cap2.isOpened():
                print(f"✗ Камера 2 не открылась: ID {camera_id}")
                cap2.release()
                cap2 = None
                return

            cap2.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
            cap2.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
            last_send_time[2] = 0
            print(f"✓ Камера 2 инициализирована: ID {camera_id}")

    except Exception as e:
        print(f"✗ Ошибка инициализации камеры {camera_num}: {e}")


def detect_persons(frame):
    """Детекция людей и возврат их координат"""
    persons = []

    try:
        results = model(frame, conf=0.5, verbose=False, device=device)
        class_thresholds = {
            0: 0.9,
            1: 0.75
        }

        for result in results:
            for box in result.boxes:
                if int(box.cls) == 0 and float(box.conf[0]) >= 0.9 or (int(box.cls) == 1):  # person
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])

                    # Центр объекта
                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2

                    persons.append({
                        'x': center_x,
                        'y': center_y,
                        'confidence': int(box.cls)
                    })
    except Exception as e:
        print(f"✗ Ошибка детекции: {e}")

    return persons


def send_coordinates(persons, camera_num):
    """Отправка координат на сервер раз в N секунд"""
    current_time = time.time()

    if camera_num in last_send_time:
        # Раз в 10 секунд, как у тебя в исходнике
        if current_time - last_send_time[camera_num] < 0.02:
            return

    last_send_time[camera_num] = current_time

    # Отправляем данные даже если людей нет
    utc_time = datetime.now(timezone.utc).isoformat()

    if persons and persons[0]['confidence'] == 0:  # Человек(и) найдены
        person = persons[0]
        data = {
            'camera_id': camera_num,
            'x': person['x'],
            'y': person['y'],
            'confidence': person['confidence'],
            'has_person': True,
            'timestamp': utc_time
        }
        print(f"✓ Камера {camera_num}: Найден cup X={person['x']}, Y={person['y']}")
    else:  # Людей не найдено
        data = {
            'camera_id': camera_num,
            'x': 320,   # Центр
            'y': 240,   # Центр
            'confidence': 0,
            'has_person': False,
            'timestamp': utc_time
        }
        print(f"⚠️  Камера {camera_num}: cup не найден")

    try:
        if persons and 520 > persons[0]['x'] > 400:
            response = requests.post(SERVER_URL, json=data, timeout=2)
            if response.status_code != 200:
                print(f"✗ Ошибка отправки: {response.status_code}")
    except Exception as e:
        print(f"✗ Ошибка подключения: {e}")


def process_frame(frame, camera_num):
    """Обработка кадра: детекция, отправка координат, рисование боксов"""
    frame_copy = frame.copy()

    cups = detect_persons(frame)

    # Отправляем координаты на сервер
    send_coordinates(cups, camera_num)

    # Рисуем боксы вокруг людей
    if cups:
        try:
            results = model(frame, conf=0.5, verbose=False, device=device)
            for result in results:
                for box in result.boxes:
                    if int(box.cls) == 0:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        conf = float(box.conf[0])
                        cv2.rectangle(frame_copy, (x1, y1), (x2, y2),
                                      (0, 0, 255), 2)
                        cv2.putText(frame_copy, f'Cup break: {conf:.2f}',
                                    (x1, y1 - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    1, (0, 0, 255), 2)
                    if int(box.cls) == 1:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        conf = float(box.conf[0])
                        cv2.rectangle(frame_copy, (x1, y1), (x2, y2),
                                      (0, 255, 0), 2)
                        cv2.putText(frame_copy, f'Cup ok: {conf:.2f}',
                                    (x1, y1 - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    1, (0, 255, 0), 2)
        except Exception as e:
            print(f"✗ Ошибка при отрисовке боксов: {e}")
    #os.makedirs('saved_frames', exist_ok=True)
    #filename = f'saved_frames/frame_cam1_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.jpg'
    #cv2.imwrite(filename, frame)
    return frame_copy


def update_frames_camera1():
    global current_frame1, cap1
    last_time = time.time()

    while True:
        if cap1 is None or not cap1.isOpened():
            time.sleep(0.1)
            continue

        current_time = time.time()
        if current_time - last_time < FRAME_TIME:
            time.sleep(0.02)
            continue

        last_time = current_time

        ret, frame = cap1.read()
        #os.makedirs('saved_frames', exist_ok=True)
        #filename = f'saved_frames/frame_cam1_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.jpg'
        #cv2.imwrite(filename, frame)
        if not ret:
            # Можно попробовать переподключить, если нужно
            time.sleep(0.05)
            continue

        processed = process_frame(frame, 1)

        with frame_lock1:
            current_frame1 = processed


def update_frames_camera2():
    global current_frame2, cap2
    last_time = time.time()

    while True:
        if cap2 is None or not cap2.isOpened():
            time.sleep(0.1)
            continue

        current_time = time.time()
        if current_time - last_time < FRAME_TIME:
            time.sleep(0.02)
            continue

        last_time = current_time

        ret, frame = cap2.read()
        #os.makedirs('saved_frames', exist_ok=True)
        #filename = f'saved_frames/frame_cam2_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.jpg'
        #cv2.imwrite(filename, frame)
        if not ret:
            time.sleep(0.05)
            continue

        processed = process_frame(frame, 2)

        with frame_lock2:
            current_frame2 = processed


@video_bp.route('/cameras', methods=['GET'])
def get_cameras():
    """
    Получение списка доступных камер.
    Использует тот же backend, что и основная инициализация.
    """
    max_tested = 10
    available_cameras = []

    for i in range(max_tested):
        test_cap = cv2.VideoCapture(i, CAMERA_BACKEND)
        if not test_cap.isOpened():
            test_cap.release()
            continue

        available_cameras.append({"id": i, "name": f"Camera {i}"})
        test_cap.release()

    return jsonify(available_cameras)


@video_bp.route('/select_camera/<int:camera_num>/<int:camera_id>', methods=['POST'])
def select_camera(camera_num, camera_id):
    """
    Выбор камеры для потока 1 или 2.
    """
    init_camera(camera_id, camera_num)
    return jsonify({"camera_num": camera_num, "camera_id": camera_id})


@video_bp.route('/feed1')
def video_feed1():
    def generate():
        while True:
            with frame_lock1:
                if current_frame1 is None:
                    time.sleep(0.01)
                    continue
                ret, buffer = cv2.imencode('.jpg', current_frame1)
                if not ret:
                    continue
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
                    time.sleep(0.01)
                    continue
                ret, buffer = cv2.imencode('.jpg', current_frame2)
                if not ret:
                    continue
                frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# Стартовая инициализация камер (подкорректируй индексы под свою систему)
init_camera('/dev/video1', 1) # !!!!!! пробовать разные
init_camera('/dev/video4', 2)

print(f"⏱️  Ограничение FPS: {MAX_FPS} кадров/сек")
print(f"📡 Сервер координат: {SERVER_URL}")

threading.Thread(target=update_frames_camera1, daemon=True).start()
threading.Thread(target=update_frames_camera2, daemon=True).start()

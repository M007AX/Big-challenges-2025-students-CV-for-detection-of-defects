from flask import Blueprint, Response
import cv2
from ultralytics import YOLO
import threading
import torch
import time

video_bp = Blueprint('video', __name__)

# Проверяем доступность GPU
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"🖥️  Используемое устройство: {device}")
if device == 'cuda':
    print(f"📊 GPU: {torch.cuda.get_device_name(0)}")
    print(f"📈 CUDA версия: {torch.version.cuda}")

# Загружаем модель один раз с указанием устройства
model = YOLO('yolov8n.pt').to(device)

cap1 = None
cap2 = None

frame_lock1 = threading.Lock()
frame_lock2 = threading.Lock()
current_frame1 = None
current_frame2 = None

offset_point = {'x': None, 'y': None}

# Ограничение FPS
MAX_FPS = 15  # Максимум 15 кадров в секунду
FRAME_TIME = 1.0 / MAX_FPS  # Время между кадрами в секундах


def init_camera(camera_id, camera_num):
    """Инициализация камеры"""
    global cap1, cap2

    try:
        if camera_num == 1:
            if cap1:
                cap1.release()
            cap1 = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            cap1.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap1.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            print(f"✓ Камера 1 инициализирована: ID {camera_id}")
        else:
            if cap2:
                cap2.release()
            cap2 = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
            cap2.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap2.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            print(f"✓ Камера 2 инициализирована: ID {camera_id}")
    except Exception as e:
        print(f"✗ Ошибка инициализации камеры {camera_num}: {e}")


def process_frame(frame):
    """Обработка кадра с GPU ускорением"""
    frame_copy = frame.copy()

    try:
        # Используем device параметр для GPU обработки
        results = model(frame, conf=0.5, verbose=False, device=device)

        for result in results:
            for box in result.boxes:
                if int(box.cls) == 0:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])

                    cv2.rectangle(frame_copy, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame_copy, f'Person: {conf:.2f}', (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    except Exception as e:
        print(f"✗ Ошибка детекции: {e}")

    if offset_point['x'] is not None and offset_point['y'] is not None:
        x = offset_point['x']
        y = offset_point['y']
        cv2.circle(frame_copy, (x, y), 10, (255, 0, 0), -1)
        cv2.putText(frame_copy, f'X:{x} Y:{y}', (x + 15, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

    return frame_copy


def update_frames_camera1():
    """Поток для камеры 1 с ограничением FPS"""
    global current_frame1
    last_time = time.time()

    while True:
        if cap1 is None:
            continue

        # Ограничение FPS
        current_time = time.time()
        if current_time - last_time < FRAME_TIME:
            time.sleep(0.001)
            continue

        last_time = current_time

        ret, frame = cap1.read()
        if not ret:
            continue

        processed = process_frame(frame)

        with frame_lock1:
            current_frame1 = processed


def update_frames_camera2():
    """Поток для камеры 2 с ограничением FPS"""
    global current_frame2
    last_time = time.time()

    while True:
        if cap2 is None:
            continue

        # Ограничение FPS
        current_time = time.time()
        if current_time - last_time < FRAME_TIME:
            time.sleep(0.001)
            continue

        last_time = current_time

        ret, frame = cap2.read()
        if not ret:
            continue

        processed = process_frame(frame)

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
    print(f"Смена камеры: {camera_num}, ID: {camera_id}")
    init_camera(camera_id, camera_num)
    return jsonify({"camera_num": camera_num, "camera_id": camera_id, "status": "ok"})


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


@video_bp.route('/status', methods=['GET'])
def get_status():
    """Возвращает статус GPU и FPS"""
    from flask import jsonify

    gpu_available = torch.cuda.is_available()
    gpu_count = torch.cuda.device_count() if gpu_available else 0
    gpu_name = torch.cuda.get_device_name(0) if gpu_available else "N/A"

    return jsonify({
        'device': device,
        'gpu_available': gpu_available,
        'gpu_count': gpu_count,
        'gpu_name': gpu_name,
        'cuda_version': torch.version.cuda if gpu_available else None,
        'max_fps': MAX_FPS,
        'frame_time_ms': round(FRAME_TIME * 1000, 2)
    })


# Инициализация
init_camera(0, 1)
init_camera(0, 2)
print(f"⏱️  Ограничение FPS: {MAX_FPS} кадров/сек ({FRAME_TIME * 1000:.2f}ms между кадрами)")
threading.Thread(target=update_frames_camera1, daemon=True).start()
threading.Thread(target=update_frames_camera2, daemon=True).start()

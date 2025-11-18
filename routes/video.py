from flask import Blueprint, Response
import cv2
from ultralytics import YOLO
import threading

video_bp = Blueprint('video', __name__)

model = YOLO('yolov8n.pt')
cap = None
frame_lock = threading.Lock()
current_frame = None

# Координаты смещенной точки (стационарная)
offset_point = {'x': None, 'y': None}


def init_camera(camera_id=0):
    global cap
    if cap:
        cap.release()
    cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)


def update_frames():
    global current_frame

    while True:
        if cap is None:
            continue

        ret, frame = cap.read()
        if not ret:
            continue

        frame_copy = frame.copy()

        # Рисуем обнаруженных людей
        results = model(frame, conf=0.5, verbose=False)

        for result in results:
            for box in result.boxes:
                if int(box.cls) == 0:  # person
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])

                    # Зелёный боксе вокруг человека
                    cv2.rectangle(frame_copy, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame_copy, f'Стаканчик: {conf:.2f}', (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Рисуем смещенную точку (если установлена)
        if offset_point['x'] is not None and offset_point['y'] is not None:
            x = offset_point['x']
            y = offset_point['y']
            if x % 2 == 0 and y% 2 == 0:
                cv2.circle(frame_copy, (x, y), 10, (255, 0, 0), -1)  # Синяя точка
                cv2.putText(frame_copy, f'X:{x} Y:{y}', (x + 15, y),           # текст для синей точки
                            cv2.FONT_HERSHEY_SIMPLEX, 0.2, (255, 0, 0), 1)
            else:
                cv2.circle(frame_copy, (x, y), 10, (0, 255, 0), -1)  # Синяя точка
                cv2.putText(frame_copy, f'X:{x} Y:{y}', (x + 15, y),           # текст для синей точки
                            cv2.FONT_HERSHEY_SIMPLEX, 0.2, (0, 255, 0), 1)

        with frame_lock:
            current_frame = frame_copy


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


@video_bp.route('/select_camera/<int:camera_id>', methods=['POST'])
def select_camera(camera_id):
    from flask import jsonify
    init_camera(camera_id)
    return jsonify({"selected_camera": camera_id})


@video_bp.route('/feed')
def video_feed():
    def generate():
        while True:
            with frame_lock:
                if current_frame is None:
                    continue
                ret, buffer = cv2.imencode('.jpg', current_frame)
                frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


init_camera(0)
threading.Thread(target=update_frames, daemon=True).start()

from flask import Flask, render_template, Response, request, jsonify
import cv2
from ultralytics import YOLO
import threading

app = Flask(__name__)

model = YOLO('yolov8n.pt')

# Глобальные переменные камеры и кадра
cap = None
frame_lock = threading.Lock()
current_frame = None


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

        results = model(frame, conf=0.5, verbose=False)
        for result in results:
            for box in result.boxes:
                if int(box.cls) == 0:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])
                    label = "Person"
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"{label}: {conf:.2f}", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        with frame_lock:
            current_frame = frame


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video_feed')
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


@app.route('/api/cameras')
def get_cameras():
    """Возвращает список доступных камер"""
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


@app.route('/api/select_camera', methods=['POST'])
def select_camera():
    """Выбор камеры для захвата"""
    global cap
    camera_id = request.json.get('camera_id', 0)
    init_camera(camera_id)
    return jsonify({"selected_camera": camera_id})


if __name__ == '__main__':
    init_camera(0)  # Инициализация камеры по умолчанию
    threading.Thread(target=update_frames, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)

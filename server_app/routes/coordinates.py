from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
import threading
import serial
import time
import queue

from server_app.routes.arduino import rotation

coord_bp = Blueprint('coordinates', __name__)

coordinates_storage = {
    1: [],
    2: []
}

storage_lock = threading.Lock()
MAX_RECORDS = 1000

# Последовательный порт (подкорректируй, если нужно)
ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
time.sleep(2)


# Пример строк для отправки
data_to_send2 = "7,170,100"
data_to_send1 = "7,120,100"


ser.write(data_to_send2.encode())



# ===== Очередь задач для управления сервоприводом =====
rotation_queue: "queue.Queue[dict]" = queue.Queue()


def rotation_worker():
    """Фоновый поток, который крутит сервопривод, не блокируя Flask."""
    while True:
        task = rotation_queue.get()  # блокируется, пока нет задач
        if task is None:
            break  # возможность аккуратного завершения при необходимости

        try:
            # Здесь можно использовать параметры из task при необходимости
            # например, task['camera_id'], task['x'], task['y'], ...
            time.sleep(2)
            rotation(ser, data_to_send1, data_to_send2)
            while not rotation_queue.empty():
                rotation_queue.get()
        except Exception as e:
            print(f"✗ Ошибка в rotation_worker: {e}")
        finally:
            rotation_queue.task_done()



# Запускаем рабочий поток один раз при импорте модуля
rotation_thread = threading.Thread(target=rotation_worker, daemon=True)
rotation_thread.start()


@coord_bp.route('/receive', methods=['POST'])
def receive_coordinates(x1=1000000, y1=1000000):
    """Получение координат с камеры (не блокирует видео)."""
    data = request.json or {}

    camera_id = data.get('camera_id')
    x = data.get('x')
    y = data.get('y')
    confidence = data.get('confidence', 0.8)
    has_person = data.get('has_person', True)  # Есть ли объект в кадре
    timestamp = data.get('timestamp') or datetime.now(timezone.utc).isoformat()

    record = {
        'camera_id': camera_id,
        'x': x,
        'y': y,
        'confidence': confidence,
        'has_person': has_person,
        'timestamp': timestamp
    }

    with storage_lock:
        if camera_id not in coordinates_storage:
            coordinates_storage[camera_id] = []

        coordinates_storage[camera_id].append(record)

        if len(coordinates_storage[camera_id]) > MAX_RECORDS:
            coordinates_storage[camera_id].pop(0)

    print(f"📍 Камера {camera_id}: X={x}, Y={y}, Has_Person={has_person}")

    # ====== ГЛАВНАЯ ЛОГИКА ======
    # Если объект ЕСТЬ в кадре — ставим задачу в очередь для фонового потока
    if has_person and abs(x1 - x) > 0.2 and abs(y1 - y) > 0.2:
        x1 = x
        y1 = x
        rotation_queue.put({
            'camera_id': camera_id,
            'x': x,
            'y': y,
            'confidence': confidence,
            'timestamp': timestamp
        })

    # ВАЖНО: отвечаем сразу, не дожидаясь окончания движения сервы
    return jsonify({'status': 'ok', 'has_person': has_person})


@coord_bp.route('/get_latest', methods=['GET'])
def get_latest():
    """Получить последние координаты по всем камерам."""
    with storage_lock:
        latest = {}
        for camera_id, records in coordinates_storage.items():
            if records:
                latest[camera_id] = records[-1]

    return jsonify(latest)


@coord_bp.route('/get_history/<int:camera_id>', methods=['GET'])
def get_history(camera_id):
    """Получить историю координат для конкретной камеры."""
    limit = request.args.get('limit', 100, type=int)

    with storage_lock:
        if camera_id in coordinates_storage:
            records = coordinates_storage[camera_id][-limit:]
            return jsonify({
                'camera_id': camera_id,
                'records': records,
                'total': len(records)
            })
        else:
            return jsonify({'error': 'Camera not found'}), 404


@coord_bp.route('/clear/<int:camera_id>', methods=['POST'])
def clear_history(camera_id):
    """Очистить историю для конкретной камеры."""
    with storage_lock:
        if camera_id in coordinates_storage:
            coordinates_storage[camera_id] = []
            return jsonify({'status': 'ok'})
        else:
            return jsonify({'error': 'Camera not found'}), 404


@coord_bp.route('/stats', methods=['GET'])
def get_stats():
    """Получить статистику по всем камерам."""
    with storage_lock:
        stats = {}
        for camera_id, records in coordinates_storage.items():
            if records:
                total = len(records)
                with_person = len([r for r in records if r['has_person']])

                stats[camera_id] = {
                    'total_records': total,
                    'records_with_person': with_person,
                    'records_without_person': total - with_person
                }

    return jsonify(stats)

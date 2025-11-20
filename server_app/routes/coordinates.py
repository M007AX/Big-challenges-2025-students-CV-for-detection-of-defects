from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
import threading
import serial
import time
from server_app.routes.arduino import rotation

coord_bp = Blueprint('coordinates', __name__)

coordinates_storage = {
    1: [],
    2: []
}

storage_lock = threading.Lock()
MAX_RECORDS = 1000

ser = serial.Serial('COM3', 115200, timeout=1)
time.sleep(2)
# Пример отправки данных
data_to_send1 = "7,90,100"
data_to_send2 = "7,-90,100"




@coord_bp.route('/receive', methods=['POST'])
def receive_coordinates():
    """Получение координат с камеры"""
    data = request.json

    camera_id = data.get('camera_id')
    x = data.get('x')
    y = data.get('y')
    confidence = data.get('confidence', 0.8)
    has_person = data.get('has_person', True)  # Есть ли человек в кадре
    timestamp = data.get('timestamp')

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
    # Если человек ЕСТЬ в кадре - начинаем отслеживание
    if has_person:
        rotation(ser, data_to_send1, data_to_send2)

    return jsonify({'status': 'ok', 'has_person': has_person})


@coord_bp.route('/get_latest', methods=['GET'])
def get_latest():
    """Получить последние координаты"""
    with storage_lock:
        latest = {}
        for camera_id, records in coordinates_storage.items():
            if records:
                latest[camera_id] = records[-1]

    return jsonify(latest)


@coord_bp.route('/get_history/<int:camera_id>', methods=['GET'])
def get_history(camera_id):
    """Получить историю координат"""
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
    """Очистить историю"""
    with storage_lock:
        if camera_id in coordinates_storage:
            coordinates_storage[camera_id] = []
            return jsonify({'status': 'ok'})


@coord_bp.route('/stats', methods=['GET'])
def get_stats():
    """Получить статистику"""
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


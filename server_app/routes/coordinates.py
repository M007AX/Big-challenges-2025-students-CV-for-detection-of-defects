from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
import threading

coord_bp = Blueprint('coordinates', __name__)

# Хранилище координат
coordinates_storage = {
    1: [],
    2: []
}

storage_lock = threading.Lock()

# Максимум записей в памяти
MAX_RECORDS = 1000


@coord_bp.route('/receive', methods=['POST'])
def receive_coordinates():
    """Получение координат с камеры"""
    data = request.json

    camera_id = data.get('camera_id')
    x = data.get('x')
    y = data.get('y')
    confidence = data.get('confidence')
    timestamp = data.get('timestamp')

    record = {
        'camera_id': camera_id,
        'x': x,
        'y': y,
        'confidence': confidence,
        'timestamp': timestamp
    }

    with storage_lock:
        if camera_id not in coordinates_storage:
            coordinates_storage[camera_id] = []

        coordinates_storage[camera_id].append(record)

        # Ограничиваем размер хранилища
        if len(coordinates_storage[camera_id]) > MAX_RECORDS:
            coordinates_storage[camera_id].pop(0)

    print(f"📍 Получены координаты: Камера={camera_id}, X={x}, Y={y}, Time={timestamp}")

    return jsonify({'status': 'ok', 'message': 'Координаты получены'})


@coord_bp.route('/get_latest', methods=['GET'])
def get_latest():
    """Получить последние координаты для обеих камер"""
    with storage_lock:
        latest = {}
        for camera_id, records in coordinates_storage.items():
            if records:
                latest[camera_id] = records[-1]  # Последняя запись

    return jsonify(latest)


@coord_bp.route('/get_history/<int:camera_id>', methods=['GET'])
def get_history(camera_id):
    """Получить историю координат для конкретной камеры"""
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


@coord_bp.route('/get_all', methods=['GET'])
def get_all():
    """Получить все координаты для всех камер"""
    with storage_lock:
        all_data = {}
        for camera_id, records in coordinates_storage.items():
            all_data[camera_id] = {
                'total_records': len(records),
                'latest': records[-1] if records else None
            }

    return jsonify(all_data)


@coord_bp.route('/clear/<int:camera_id>', methods=['POST'])
def clear_history(camera_id):
    """Очистить историю для камеры"""
    with storage_lock:
        if camera_id in coordinates_storage:
            coordinates_storage[camera_id] = []
            return jsonify({'status': 'ok', 'message': f'История камеры {camera_id} очищена'})
        else:
            return jsonify({'error': 'Camera not found'}), 404


@coord_bp.route('/stats', methods=['GET'])
def get_stats():
    """Получить статистику"""
    with storage_lock:
        stats = {}
        for camera_id, records in coordinates_storage.items():
            if records:
                x_values = [r['x'] for r in records]
                y_values = [r['y'] for r in records]
                stats[camera_id] = {
                    'total_records': len(records),
                    'avg_x': round(sum(x_values) / len(x_values), 2),
                    'avg_y': round(sum(y_values) / len(y_values), 2),
                    'min_x': min(x_values),
                    'max_x': max(x_values),
                    'min_y': min(y_values),
                    'max_y': max(y_values)
                }

    return jsonify(stats)

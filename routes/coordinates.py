from flask import Blueprint, request, jsonify

coord_bp = Blueprint('coordinates', __name__)


@coord_bp.route('/send', methods=['POST'])
def send_coordinates():
    from routes.video import offset_point

    data = request.json
    x = int(data.get('x', 0))
    y = int(data.get('y', 0))

    x_new = x + 20
    y_new = y + 20

    offset_point['x'] = x_new
    offset_point['y'] = y_new

    print("=" * 50)
    print(f"📍 КООРДИНАТЫ ОТПРАВЛЕНЫ")
    print(f"Исходные: X={x}, Y={y}")
    print(f"Смещение +20px: X={x_new}, Y={y_new}")
    print("=" * 50)

    return jsonify({
        'status': 'ok',
        'original': {'x': x, 'y': y},
        'modified': {'x': x_new, 'y': y_new}
    })

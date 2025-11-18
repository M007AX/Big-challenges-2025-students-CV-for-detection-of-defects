from flask import Flask
from routes.video import video_bp
from routes.coordinates import coord_bp

app = Flask(__name__)

# Регистрируем blueprints
app.register_blueprint(video_bp, url_prefix='/api/video')
app.register_blueprint(coord_bp, url_prefix='/api/coords')

@app.route('/')
def index():
    from flask import render_template
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

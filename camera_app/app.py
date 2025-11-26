from flask import Flask
from routes.video import video_bp

app = Flask(__name__)

app.register_blueprint(video_bp, url_prefix='/api/video')

@app.route('/')
def index():
    from flask import render_template
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

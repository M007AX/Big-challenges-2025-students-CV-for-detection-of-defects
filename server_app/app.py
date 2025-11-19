from flask import Flask
from routes.coordinates import coord_bp

app = Flask(__name__)

app.register_blueprint(coord_bp, url_prefix='/api/coordinates')

@app.route('/')
def index():
    from flask import render_template
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)

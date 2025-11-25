from multiprocessing import Process
from camera_app.app import create_app as create_app_camera
from server_app.app import create_app as create_app_server
from werkzeug.serving import run_simple

def run_flask_app(app, port):
    run_simple('0.0.0.0', port, app, use_reloader=False)

if __name__ == '__main__':
    app1 = create_app_camera()
    app2 = create_app_server()

    p1 = Process(target=run_flask_app, args=(app1, 5000))
    p2 = Process(target=run_flask_app, args=(app2, 5001))

    p1.start()
    p2.start()

    p1.join()
    p2.join()

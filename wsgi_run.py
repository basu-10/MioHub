from flask_app import app
from waitress import serve

if __name__ == "__main__":
    print("Starting WSGI server with Waitress...")
    print("serving on http://localhost:5555")
    serve(app, host='0.0.0.0', port=5555)
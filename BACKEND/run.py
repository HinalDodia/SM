from invest import create_app
from flask_cors import CORS

app = create_app()
# Move CORS here if not in __init__.py, but don't do both.
CORS(app, resources={r"/*": {"origins": "*"}}) 

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

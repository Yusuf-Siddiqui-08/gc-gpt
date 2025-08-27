import os
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS

# Paths
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
BUILD_DIR = os.path.join(BASE_DIR, 'client', 'build')
STATIC_DIR = os.path.join(BUILD_DIR, 'static')

# Create Flask app configured to serve the React build
app = Flask(
    __name__,
    static_folder=STATIC_DIR,  # for /static/* assets
    static_url_path='/static'
)
CORS(app)


@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'service': 'flask-react-starter',
        'build_exists': os.path.exists(BUILD_DIR)
    })


# Serve the React app's index.html for root and all other client-side routes
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    # If the request is for a file within the build folder, serve it directly
    requested_path = os.path.join(BUILD_DIR, path)
    if path and os.path.exists(requested_path) and os.path.isfile(requested_path):
        # Serve files like favicon.ico, asset-manifest.json, etc.
        return send_from_directory(BUILD_DIR, path)

    # Fallback to index.html for client-side routing
    index_path = os.path.join(BUILD_DIR, 'index.html')
    if os.path.exists(index_path):
        return send_from_directory(BUILD_DIR, 'index.html')

    # Build missing: inform the user clearly
    return (
        'React build not found. Please create client/build/index.html or run your React build.\n'
        'Expected directory: ' + BUILD_DIR,
        404,
        {'Content-Type': 'text/plain; charset=utf-8'}
    )


if __name__ == '__main__':
    # Read host and port from env if provided (useful for deployment)
    host = os.environ.get('FLASK_RUN_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_RUN_PORT', '5000'))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'

    print(f"Starting Flask server on http://{host}:{port}")
    print(f"Serving static files from: {BUILD_DIR}")
    app.run(host=host, port=port, debug=debug)

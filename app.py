import os
import sqlite3
import random
import secrets
from flask import (
    Flask,
    send_from_directory,
    jsonify,
    request,
    session,
)
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

# Paths
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
BUILD_DIR = os.path.join(BASE_DIR, 'client', 'build')
STATIC_DIR = os.path.join(BUILD_DIR, 'static')
DATABASE = os.path.join(BASE_DIR, 'users.db')
SQL_DIR = os.path.join(BASE_DIR, 'sql')

# SQL loader
_SQL_CACHE = {}

def load_sql(name: str) -> str:
    """Load an .sql file from the sql directory and cache it by name.
    Example: load_sql('get_user_by_username') loads sql\get_user_by_username.sql
    """
    if name in _SQL_CACHE:
        return _SQL_CACHE[name]
    path = os.path.join(SQL_DIR, f"{name}.sql")
    with open(path, 'r', encoding='utf-8') as f:
        sql = f.read().strip()
    _SQL_CACHE[name] = sql
    return sql

# Create Flask app configured to serve the React build + JSON APIs
app = Flask(
    __name__,
    static_folder=STATIC_DIR,  # for /static/* assets
    static_url_path='/static'
)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
CORS(app)


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def random_profile_color() -> str:
    """Generate a random hex color like #A1B2C3."""
    return f"#{random.randint(0, 0xFFFFFF):06x}"




def update_user_profile_color(user_id: int, color: str):
    with get_db_connection() as conn:
        conn.execute(load_sql('update_user_profile_color'), (color, user_id))
        conn.commit()


def init_db():
    os.makedirs(BASE_DIR, exist_ok=True)
    with get_db_connection() as conn:
        # Create base tables if they don't exist
        conn.execute(load_sql('create_table_users'))
        conn.execute(load_sql('create_table_chats'))
        conn.execute(load_sql('create_table_chat_members'))

        # Ensure columns exist on users (lightweight auto-migration)
        cur = conn.execute(load_sql('pragma_table_info_users'))
        cols = [row[1] for row in cur.fetchall()]
        if 'profile_color' not in cols:
            conn.execute(load_sql('alter_table_add_profile_color'))
        if 'username' not in cols:
            # add username column for existing DBs
            conn.execute(load_sql('alter_table_add_username'))
            # backfill usernames for existing rows deterministically (no dependency on removed fields)
            cur2 = conn.execute("SELECT id FROM users WHERE username IS NULL OR username = ''")
            rows = cur2.fetchall()
            for r in rows:
                uid = r[0]
                base = f'user{uid}'
                candidate = base
                # ensure uniqueness
                while True:
                    c = conn.execute("SELECT id FROM users WHERE username = ?", (candidate,)).fetchone()
                    if not c:
                        break
                    candidate = f"{base}{uid}"
                conn.execute("UPDATE users SET username = ? WHERE id = ?", (candidate, uid))
            # add unique index for username
            try:
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username COLLATE NOCASE)")
            except Exception:
                pass
        conn.commit()


def get_user_by_username(username: str):
    if not username:
        return None
    with get_db_connection() as conn:
        cur = conn.execute(load_sql('get_user_by_username'), (username,))
        row = cur.fetchone()
        return dict(row) if row else None




def create_user(name: str, username: str, password_hash: str, profile_color: str = None):
    with get_db_connection() as conn:
        cur = conn.execute(
            load_sql('insert_user'),
            (name, username, password_hash, profile_color),
        )
        conn.commit()
        return cur.lastrowid


@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'service': 'flask-react-starter',
        'build_exists': os.path.exists(BUILD_DIR)
    })


@app.route('/api/me', methods=['GET'])
def me():
    user = session.get('user')
    if user and not user.get('profile_color'):
        # Try to backfill color into session from DB using username
        db_user = get_user_by_username(user.get('username'))
        color = db_user.get('profile_color') if db_user else None
        if not color and db_user:
            color = random_profile_color()
            try:
                update_user_profile_color(db_user['id'], color)
            except Exception:
                pass
        if color:
            user = {**user, 'profile_color': color}
            session['user'] = user
    return jsonify({'user': user})


@app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    username = (data.get('username') or '').strip().lower()
    password = data.get('password') or ''

    if not name or not username or not password:
        return jsonify({'error': 'Name, username, and password are required.'}), 400

    # Ensure username is unique; append numeric suffix if needed
    candidate = username
    if get_user_by_username(candidate):
        # Try to find an available variant: username, username1, username2, ... up to 1000
        for i in range(1, 1001):
            cand = f"{username}{i}"
            if not get_user_by_username(cand):
                candidate = cand
                break
        else:
            return jsonify({'error': 'Unable to generate a unique username. Please try a different one.'}), 409
    username = candidate

    password_hash = generate_password_hash(password)
    color = random_profile_color()

    # Robust insert with retries: handle race conditions or DB collation mismatches by
    # attempting to create the user and, on username uniqueness violations, retrying
    # with incremented suffixes up to 1000.
    base_username = username
    user_id = None
    last_error = None
    for i in range(0, 1001):
        cand = base_username if i == 0 else f"{base_username}{i}"
        try:
            user_id = create_user(name, cand, password_hash, color)
            username = cand
            break
        except sqlite3.IntegrityError as e:
            # Inspect the error to decide whether to retry or fail immediately
            msg = str(e).lower()
            last_error = msg
            if 'users.username' in msg or 'unique constraint failed: users.username' in msg or 'idx_users_username' in msg:
                # Try next suffix
                continue
            # Unknown integrity error
            return jsonify({'error': 'Unable to create user.'}), 409
    else:
        return jsonify({'error': 'Unable to generate a unique username. Please try a different one.'}), 409

    session['user'] = {
        'id': user_id,
        'name': name,
        'username': username,
        'profile_color': color,
    }
    return jsonify({'user': session['user']}), 201


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip().lower()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'error': 'Username and password are required.'}), 400

    user = get_user_by_username(username)

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid credentials.'}), 401

    color = user.get('profile_color')
    if not color:
        color = random_profile_color()
        try:
            update_user_profile_color(user['id'], color)
        except Exception:
            # If update fails, still proceed with a generated color for the session
            pass
    session['user'] = {
        'name': user['name'],
        'username': user['username'],
        'profile_color': color,
    }
    return jsonify({'user': session['user']}), 200


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.pop('user', None)
    return ('', 204)


@app.route('/api/profile', methods=['POST'])
def api_update_profile():
    user_session = session.get('user')
    if not user_session:
        return jsonify({'error': 'Not authenticated.'}), 401

    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    username = (data.get('username') or '').strip().lower()
    password = data.get('password') or ''
    profile_color = (data.get('profile_color') or '').strip() or None

    # Load current user from DB
    db_user = get_user_by_username(user_session.get('username'))
    if not db_user:
        return jsonify({'error': 'User not found.'}), 404

    # Compose new values
    new_name = name or db_user['name']
    new_username = username or db_user['username']
    if not new_name or not new_username:
        return jsonify({'error': 'Name and username cannot be empty.'}), 400

    # Check unique username if changed
    if new_username != db_user['username']:
        with get_db_connection() as conn:
            cur = conn.execute(load_sql('select_user_id_by_username'), (new_username,))
            if cur.fetchone():
                return jsonify({'error': 'An account with that username already exists.'}), 409

    # Perform update
    with get_db_connection() as conn:
        updates = []
        params = []
        if new_name != db_user['name']:
            updates.append('name = ?')
            params.append(new_name)
        if new_username != db_user['username']:
            updates.append('username = ?')
            params.append(new_username)
        if profile_color and profile_color != (db_user.get('profile_color') or ''):
            updates.append('profile_color = ?')
            params.append(profile_color)
        if password:
            updates.append('password_hash = ?')
            params.append(generate_password_hash(password))
        if updates:
            sql = load_sql('update_user_dynamic').format(set_clause=', '.join(updates))
            params.append(db_user['id'])
            conn.execute(sql, tuple(params))
            conn.commit()

    updated = {
        'name': new_name,
        'username': new_username,
        'profile_color': profile_color or db_user.get('profile_color'),
    }
    session['user'] = updated
    return jsonify({'user': updated}), 200


# Chat helpers and APIs

def _generate_chat_id(conn) -> str:
    # Generate an 8-char hex id and ensure uniqueness
    while True:
        cid = secrets.token_hex(4)
        cur = conn.execute("SELECT 1 FROM chats WHERE id = ?", (cid,))
        if not cur.fetchone():
            return cid


def _list_user_chats(username: str):
    with get_db_connection() as conn:
        cur = conn.execute(load_sql('list_user_chats'), (username,))
        rows = [dict(row) for row in cur.fetchall()]
        return rows


@app.route('/api/chats', methods=['GET'])
def api_list_chats():
    user_session = session.get('user')
    if not user_session:
        return jsonify({'error': 'Not authenticated.'}), 401
    username = user_session.get('username')
    items = _list_user_chats(username)
    return jsonify({'chats': items})


@app.route('/api/chats', methods=['POST'])
def api_create_chat():
    user_session = session.get('user')
    if not user_session:
        return jsonify({'error': 'Not authenticated.'}), 401
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    password = data.get('password') or ''
    if not name or not password:
        return jsonify({'error': 'Name and password are required.'}), 400
    username = user_session.get('username')
    with get_db_connection() as conn:
        chat_id = _generate_chat_id(conn)
        pw_hash = generate_password_hash(password)
        conn.execute(load_sql('insert_chat'), (chat_id, name, pw_hash, username))
        conn.execute(load_sql('insert_chat_member'), (chat_id, username))
        conn.commit()
    return jsonify({'chat': {'id': chat_id, 'name': name}}), 201


@app.route('/api/chats/join', methods=['POST'])
def api_join_chat():
    user_session = session.get('user')
    if not user_session:
        return jsonify({'error': 'Not authenticated.'}), 401
    data = request.get_json(silent=True) or {}
    chat_id = (data.get('chat_id') or '').strip()
    password = data.get('password') or ''
    if not chat_id or not password:
        return jsonify({'error': 'Chat ID and password are required.'}), 400
    with get_db_connection() as conn:
        cur = conn.execute(load_sql('get_chat_by_id'), (chat_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Chat not found.'}), 404
        chat = dict(row)
        if not check_password_hash(chat['password_hash'], password):
            return jsonify({'error': 'Invalid chat password.'}), 403
        username = user_session.get('username')
        conn.execute(load_sql('insert_chat_member'), (chat_id, username))
        conn.commit()
        return jsonify({'chat': {'id': chat_id, 'name': chat['name']}}), 200


@app.route('/api/admin/clear-db', methods=['POST'])
def api_admin_clear_db():
    # Protected endpoint to wipe users and chats. Requires ADMIN_TOKEN env and matching token in header or query.
    admin_token = os.environ.get('ADMIN_TOKEN')
    provided = request.headers.get('X-Admin-Token') or request.args.get('token') or (request.get_json(silent=True) or {}).get('token')
    if not admin_token:
        return jsonify({'error': 'ADMIN_TOKEN is not configured on the server.'}), 500
    if not provided or provided != admin_token:
        return jsonify({'error': 'Forbidden'}), 403

    with get_db_connection() as conn:
        # Count existing rows
        users_before = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        chats_before = conn.execute('SELECT COUNT(*) FROM chats').fetchone()[0]
        members_before = conn.execute('SELECT COUNT(*) FROM chat_members').fetchone()[0]
        # Wipe in safe order (members -> chats -> users), though no FKs are enforced.
        conn.execute('DELETE FROM chat_members')
        conn.execute('DELETE FROM chats')
        conn.execute('DELETE FROM users')
        conn.commit()
    # Clear session to avoid stale references
    session.pop('user', None)

    return jsonify({
        'cleared': True,
        'counts': {
            'users': users_before,
            'chats': chats_before,
            'chat_members': members_before,
        }
    }), 200

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


# Initialize DB on startup
init_db()

# Optionally clear databases on startup if env var is set to 1

def _clear_db_on_start_if_needed():
    flag = os.environ.get('CLEAR_DB_ON_START', '0')
    if str(flag).strip() == '1':
        with get_db_connection() as conn:
            # Wipe in safe order (members -> chats -> users)
            conn.execute('DELETE FROM chat_members')
            conn.execute('DELETE FROM chats')
            conn.execute('DELETE FROM users')
            conn.commit()
        print('Cleared databases on startup because CLEAR_DB_ON_START=1')


if __name__ == '__main__':
    # Read host and port from env if provided (useful for deployment)
    host = os.environ.get('FLASK_RUN_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_RUN_PORT', '5000'))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'

    # Optionally clear DBs only when running as the main program (avoid clearing on import/reloader)
    _clear_db_on_start_if_needed()

    print(f"Starting Flask server on http://{host}:{port}")
    print(f"Serving static files from: {BUILD_DIR}")
    app.run(host=host, port=port, debug=debug)

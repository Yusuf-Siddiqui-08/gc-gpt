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
from ChatAgent import ChatAgent
from ResponseFormatter import ResponseFormatter

# Try importing PostgreSQL support
try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False

# Paths
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
BUILD_DIR = os.path.join(BASE_DIR, 'client', 'build')
STATIC_DIR = os.path.join(BUILD_DIR, 'static')
DATABASE = os.path.join(BASE_DIR, 'app.db')
SQL_DIR = os.path.join(BASE_DIR, 'sql')

# Database configuration
def _get_pg_dsn():
    """Build PostgreSQL DSN from environment variables.
    Supports DATABASE_URL or individual PG* variables."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    host = os.getenv("PGHOST")
    if not host:
        return None
    port = os.getenv("PGPORT", "5432")
    database = os.getenv("PGDATABASE")
    user = os.getenv("PGUSER")
    password = os.getenv("PGPASSWORD")
    sslmode = os.getenv("PGSSLMODE", "prefer")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}?sslmode={sslmode}"

def _is_postgres():
    """Check if PostgreSQL is configured and available."""
    if not HAS_PSYCOPG:
        return False
    dsn = _get_pg_dsn()
    if not dsn:
        return False
    try:
        conn = psycopg2.connect(dsn)
        conn.close()
        return True
    except Exception:
        return False

USE_POSTGRES = _is_postgres()

# ChatAgent configuration
DEFAULT_AI_MODEL_ID = "deepseek-v3.1:671b-cloud"
AVAILABLE_AI_MODELS = [
    {
        "id": "deepseek-v3.1:671b-cloud",
        "display_name": "DeepSeek-V3.1 (671b Cloud)",
        "short_label": "DeepSeek V3",
        "emoji": "🌀",
        "icon_key": "DeepSeek",
        "brand_color": "#2b68ff",
    },
    {
        "id": "gpt-oss:20b-cloud",
        "display_name": "GPT-OSS (20b Cloud)",
        "short_label": "GPT-OSS 20B",
        "emoji": "⚙️",
        "icon_key": "OpenAI",
        "brand_color": "#0e9c86",
    },
    {
        "id": "gpt-oss:120b-cloud",
        "display_name": "GPT-OSS (120b Cloud)",
        "short_label": "GPT-OSS 120B",
        "emoji": "🧠",
        "icon_key": "OpenAI",
        "brand_color": "#0e9c86",
    },
    {
        "id": "kimi-k2:1t-cloud",
        "display_name": "Kimi-K2 (1t Cloud)",
        "short_label": "Kimi-K2 1T",
        "emoji": "🌌",
        "icon_key": "Kimi",
        "brand_color": "#5b5bed",
    },
    {
        "id": "qwen3-coder:480b-cloud",
        "display_name": "Qwen3-Coder (480b Cloud)",
        "short_label": "Qwen3 Coder",
        "emoji": "💻",
        "icon_key": "Qwen",
        "brand_color": "#00c1de",
    },
    {
        "id": "glm-4.6:cloud",
        "display_name": "GLM-4.6 (Cloud)",
        "short_label": "GLM 4.6",
        "emoji": "⚡",
        "icon_key": "GLMV",
        "brand_color": "#00b578",
    },
    {
        "id": "qwen3-vl:235b-cloud",
        "display_name": "Qwen3-VL (235b Cloud)",
        "short_label": "Qwen3 VL",
        "emoji": "🖼️",
        "icon_key": "Qwen",
        "brand_color": "#00c1de",
    }
]
AI_MODEL_LOOKUP = {model['id']: model for model in AVAILABLE_AI_MODELS}


def get_ai_model_config(model_id=None):
    if not model_id or model_id not in AI_MODEL_LOOKUP:
        return AI_MODEL_LOOKUP[DEFAULT_AI_MODEL_ID]
    return AI_MODEL_LOOKUP[model_id]


def get_chat_agent(messages=None, model_id=None):
    model_cfg = get_ai_model_config(model_id)
    return ChatAgent(model=model_cfg['id'], messages=messages)

# SQL loader
_SQL_CACHE = {}

def load_sql(name: str) -> str:
    """Load SQL text by key from sql/postgres.sql or sql/main.sql.
    Sections are marked by lines starting with "-- name: <key>".
    Key caches results for the lifetime of the process.
    """
    if name in _SQL_CACHE:
        return _SQL_CACHE[name]

    # Choose SQL file based on database type
    sql_file = 'postgres.sql' if USE_POSTGRES else 'main.sql'
    master_path = os.path.join(SQL_DIR, sql_file)

    if os.path.exists(master_path) and '_MASTER_PARSED' not in _SQL_CACHE:
        try:
            with open(master_path, 'r', encoding='utf-8') as f:
                content = f.read()
            current_key = None
            buffer = []
            def flush():
                if current_key is not None:
                    _SQL_CACHE[current_key] = '\n'.join(buffer).strip()
            for line in content.splitlines():
                if line.strip().lower().startswith('-- name:'):
                    # new section begins
                    flush()
                    current_key = line.split(':', 1)[1].strip()
                    buffer = []
                else:
                    buffer.append(line)
            flush()
            _SQL_CACHE['_MASTER_PARSED'] = '1'
        except Exception as e:
            # Surface an explicit error if SQL file cannot be parsed/read
            raise RuntimeError(f"Failed to load or parse {sql_file}: {e}")

    if name in _SQL_CACHE:
        return _SQL_CACHE[name]

    # No fallback to individual files; explicit error helps catch typos/missing queries
    available = [k for k in _SQL_CACHE.keys() if not k.startswith('_')]
    raise KeyError(f"SQL key '{name}' not found in {sql_file}. Available keys: {available}")

# Create Flask app configured to serve the React build + JSON APIs
app = Flask(
    __name__,
    static_folder=STATIC_DIR,  # for /static/* assets
    static_url_path='/static'
)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-me')

# Configure session cookies for production (Railway deployment)
# These settings ensure sessions work correctly with HTTPS and cross-origin requests
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() == 'true'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Allow cookies with same-site navigation
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours

CORS(app, supports_credentials=True, origins=['*'])  # Enable credentials for CORS


def get_db_connection():
    """Get database connection (PostgreSQL or SQLite)."""
    if USE_POSTGRES:
        conn = psycopg2.connect(_get_pg_dsn())
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn
    else:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn


def row_to_dict(row, cursor=None):
    """Convert database row to dictionary."""
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, 'keys'):
        return dict(row)
    if cursor and hasattr(cursor, 'description'):
        return dict(zip([desc[0] for desc in cursor.description], row))
    return dict(row)


def random_profile_color() -> str:
    """Generate a random hex color like #A1B2C3."""
    return f"#{random.randint(0, 0xFFFFFF):06x}"




def update_user_profile_color(user_id: int, color: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(load_sql('update_user_profile_color'), (color, user_id))
        conn.commit()
    finally:
        conn.close()


def init_db():
    os.makedirs(BASE_DIR, exist_ok=True)
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Create base tables if they don't exist
        cur.execute(load_sql('create_table_users'))
        cur.execute(load_sql('create_table_chats'))
        cur.execute(load_sql('create_table_chat_members'))
        # Create messages table and index
        try:
            cur.execute(load_sql('create_table_messages'))
            cur.execute(load_sql('create_index_messages_chat'))
        except Exception:
            pass

        # Ensure columns exist on messages (lightweight auto-migration)
        if not USE_POSTGRES:
            try:
                cur_msg = cur.execute("PRAGMA table_info(messages)")
                msg_cols = [row[1] for row in cur_msg.fetchall()]
                if 'edited_at' not in msg_cols:
                    cur.execute("ALTER TABLE messages ADD COLUMN edited_at TIMESTAMP")
                if 'original_content' not in msg_cols:
                    cur.execute("ALTER TABLE messages ADD COLUMN original_content TEXT")
                if 'ai_model_id' not in msg_cols:
                    cur.execute("ALTER TABLE messages ADD COLUMN ai_model_id TEXT")
            except Exception:
                pass
        else:
            # PostgreSQL: Check columns differently
            try:
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'messages'")
                msg_cols = [row[0] if isinstance(row, tuple) else row['column_name'] for row in cur.fetchall()]
                if 'edited_at' not in msg_cols:
                    cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP")
                if 'original_content' not in msg_cols:
                    cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS original_content TEXT")
                if 'ai_model_id' not in msg_cols:
                    cur.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS ai_model_id TEXT")
            except Exception:
                pass

        # Ensure columns exist on users (lightweight auto-migration)
        if not USE_POSTGRES:
            cur.execute(load_sql('pragma_table_info_users'))
            cols = [row[1] for row in cur.fetchall()]
        else:
            cur.execute(load_sql('pragma_table_info_users'))
            cols = [row[0] if isinstance(row, tuple) else row['column_name'] for row in cur.fetchall()]

        if 'profile_color' not in cols:
            cur.execute(load_sql('alter_table_add_profile_color'))
        if 'username' not in cols:
            # add username column for existing DBs
            cur.execute(load_sql('alter_table_add_username'))
            # backfill usernames for existing rows deterministically
            placeholder = "?" if not USE_POSTGRES else "%s"
            cur.execute(f"SELECT id FROM users WHERE username IS NULL OR username = ''")
            rows = cur.fetchall()
            for r in rows:
                uid = r[0] if isinstance(r, tuple) else r['id']
                base = f'user{uid}'
                candidate = base
                # ensure uniqueness
                while True:
                    cur.execute(f"SELECT id FROM users WHERE username = {placeholder}", (candidate,))
                    c = cur.fetchone()
                    if not c:
                        break
                    candidate = f"{base}{uid}"
                cur.execute(f"UPDATE users SET username = {placeholder} WHERE id = {placeholder}", (candidate, uid))
            # add unique index for username
            try:
                if USE_POSTGRES:
                    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(LOWER(username))")
                else:
                    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username COLLATE NOCASE)")
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()


def get_user_by_username(username: str):
    if not username:
        return None
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(load_sql('get_user_by_username'), (username,))
        row = cur.fetchone()
        return row_to_dict(row, cur) if row else None
    finally:
        conn.close()




def create_user(name: str, username: str, password_hash: str, profile_color: str = None):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            load_sql('insert_user'),
            (name, username, password_hash, profile_color),
        )
        if USE_POSTGRES:
            result = cur.fetchone()
            user_id = result[0] if isinstance(result, tuple) else result['id']
        else:
            user_id = cur.lastrowid
        conn.commit()
        return user_id
    finally:
        conn.close()


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
    model_id = session.get('ai_model_id') or DEFAULT_AI_MODEL_ID
    return jsonify({'user': user, 'ai_model_id': model_id})


@app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    requested_username = (data.get('username') or '').strip().lower()
    password = data.get('password') or ''

    if not name or not requested_username or not password:
        return jsonify({'error': 'Name, username, and password are required.'}), 400

    # Allocate a unique username by attempting insertions until one succeeds.
    base = requested_username
    password_hash = generate_password_hash(password)
    color = random_profile_color()

    candidate = base
    max_attempts = 50
    user_id = None
    for attempt in range(max_attempts):
        if attempt > 0:
            candidate = f"{base}{attempt}"
        try:
            user_id = create_user(name, candidate, password_hash, color)
            break
        except sqlite3.IntegrityError:
            # Likely a unique username collision; try next candidate.
            continue
    else:
        # If we exhausted attempts, something unusual is happening (e.g., DB issues).
        return jsonify({'error': 'Unable to allocate a unique username at this time. Please try again later.'}), 500

    session['user'] = {
        'id': user_id,
        'name': name,
        'username': candidate,
        'profile_color': color,
    }
    session.permanent = True
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
        return jsonify({'error': 'Invalid username or password.'}), 401

    color = user.get('profile_color')
    if not color:
        color = random_profile_color()
        try:
            update_user_profile_color(user['id'], color)
        except Exception:
            pass

    session['user'] = {
        'name': user['name'],
        'username': user['username'],
        'profile_color': color,
    }
    session.permanent = True
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
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(load_sql('select_user_id_by_username'), (new_username,))
            if cur.fetchone():
                return jsonify({'error': 'An account with that username already exists.'}), 409
        finally:
            conn.close()

    # Perform update
    conn = get_db_connection()
    try:
        updates = []
        params = []
        placeholder = "?" if not USE_POSTGRES else "%s"
        if new_name != db_user['name']:
            updates.append(f'name = {placeholder}')
            params.append(new_name)
        if new_username != db_user['username']:
            updates.append(f'username = {placeholder}')
            params.append(new_username)
        if profile_color and profile_color != (db_user.get('profile_color') or ''):
            updates.append(f'profile_color = {placeholder}')
            params.append(profile_color)
        if password:
            updates.append(f'password_hash = {placeholder}')
            params.append(generate_password_hash(password))
        if updates:
            sql = load_sql('update_user_dynamic').replace('/*SET_CLAUSE*/', ', '.join(updates))
            params.append(db_user['id'])
            cur = conn.cursor()
            cur.execute(sql, tuple(params))
            conn.commit()
    finally:
        conn.close()

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
        cur = conn.cursor()
        placeholder = "?" if not USE_POSTGRES else "%s"
        cur.execute(f"SELECT 1 FROM chats WHERE id = {placeholder}", (cid,))
        if not cur.fetchone():
            return cid


def _list_user_chats(username: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(load_sql('list_user_chats'), (username,))
        rows = [row_to_dict(row, cur) for row in cur.fetchall()]
        return rows
    finally:
        conn.close()


def _get_chat_members(chat_id: str):
    """Return members for a chat ordered by most recently joined (as a proxy for activity)."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(load_sql('list_chat_members'), (chat_id,))
        members = [row_to_dict(row, cur) for row in cur.fetchall()]
        return members
    finally:
        conn.close()


def _is_member(chat_id: str, username: str) -> bool:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        placeholder = "?" if not USE_POSTGRES else "%s"
        cur.execute(f"SELECT 1 FROM chat_members WHERE chat_id = {placeholder} AND user_username = {placeholder}", (chat_id, username))
        return cur.fetchone() is not None
    finally:
        conn.close()


def _compute_avatar_layout(members):
    """Compute avatar composition layout for UI.
    Returns a dict with keys: type, users (list of usernames used), and positions (list of dicts)
    where positions[i] corresponds to users[i] and provides x,y,r,overlap,zIndex.
    X,y,r are normalized 0..1 units within a square, overlapping allowed.
    """
    users = [m['username'] for m in members]
    n = len(users)
    layout = {
        'type': None,
        'users': [],
        'positions': []
    }
    if n <= 0:
        return layout
    if n == 1:
        u = users[0]
        layout['type'] = 'single'
        layout['users'] = [u]
        layout['positions'] = [
            {'x': 0.5, 'y': 0.5, 'r': 0.5, 'overlap': 0.0, 'zIndex': 1}
        ]
        return layout
    if n == 2:
        # two-circle venn without the center (slight overlap)
        sel = users[:2]
        layout['type'] = 'double'
        layout['users'] = sel
        layout['positions'] = [
            {'x': 0.40, 'y': 0.50, 'r': 0.50, 'overlap': 0.15, 'zIndex': 1},
            {'x': 0.60, 'y': 0.50, 'r': 0.50, 'overlap': 0.15, 'zIndex': 2}
        ]
        return layout
    # 3 or more: pick the last three active (members already ordered by joined_at desc)
    sel = users[:3]
    layout['type'] = 'triple'
    layout['users'] = sel
    # Tri-venn: equilateral triangle arrangement with overlaps
    layout['positions'] = [
        {'x': 0.50, 'y': 0.36, 'r': 0.45, 'overlap': 0.18, 'zIndex': 2},  # top
        {'x': 0.34, 'y': 0.64, 'r': 0.45, 'overlap': 0.18, 'zIndex': 1},  # bottom-left
        {'x': 0.66, 'y': 0.64, 'r': 0.45, 'overlap': 0.18, 'zIndex': 3},  # bottom-right
    ]
    return layout


@app.route('/api/chats', methods=['GET'])
def api_list_chats():
    user_session = session.get('user')
    if not user_session:
        return jsonify({'error': 'Not authenticated.'}), 401
    username = user_session.get('username') or ''
    items = _list_user_chats(username)
    # Enrich each chat with members and a computed avatar layout
    enriched = []
    for chat in items:
        chat_id = chat['id']
        members = _get_chat_members(chat_id)
        layout = _compute_avatar_layout(members)
        # Provide member meta with fallback avatar data (initials and color) for frontend use
        member_slim = []
        for m in members:
            uname = m.get('username') or ''
            display_name = m.get('name') or uname
            color = m.get('profile_color') or random_profile_color()
            initials = ''.join([part[0].upper() for part in display_name.split() if part][:2]) or (uname[:2].upper())
            member_slim.append({
                'username': uname,
                'name': display_name,
                'profile_color': color,
                'initials': initials,
            })
        enriched.append({
            **chat,
            'members': member_slim,
            'avatar_layout': layout,
        })
    return jsonify({'chats': enriched})


@app.route('/api/chats/<chat_id>', methods=['GET'])
def api_get_chat(chat_id):
    user_session = session.get('user')
    if not user_session:
        return jsonify({'error': 'Not authenticated.'}), 401
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(load_sql('get_chat_by_id'), (chat_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Chat not found.'}), 404
        if not _is_member(chat_id, user_session.get('username')):
            return jsonify({'error': 'Forbidden'}), 403
        chat = row_to_dict(row, cur)
    finally:
        conn.close()
    members = _get_chat_members(chat_id)
    return jsonify({'chat': {**chat, 'members': members}})


@app.route('/api/chats/<chat_id>/messages', methods=['GET'])
def api_list_messages(chat_id):
    user_session = session.get('user')
    if not user_session:
        return jsonify({'error': 'Not authenticated.'}), 401
    username = user_session.get('username') or ''
    if not _is_member(chat_id, username):
        return jsonify({'error': 'Forbidden'}), 403

    # Optional lightweight change-detection mode
    since_id = request.args.get('since_id', type=int)
    check_only = request.args.get('check_only', default=0, type=int) == 1
    if check_only and since_id is not None:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            placeholder = "?" if not USE_POSTGRES else "%s"
            cur.execute(f"SELECT MAX(id) FROM messages WHERE chat_id = {placeholder}", (chat_id,))
            result = cur.fetchone()
            latest_id = result[0] if result else None
        finally:
            conn.close()
        has_updates = latest_id is not None and latest_id > since_id
        return jsonify({'has_updates': has_updates, 'latest_id': latest_id})

    # Content-based pagination: load messages until reaching target content length
    before_id = request.args.get('before_id', type=int)
    # Target content length: ~50KB for initial load, ~30KB for subsequent loads
    target_chars = request.args.get('max_chars', default=50000 if before_id is None else 30000, type=int)
    # Cap at reasonable limits
    target_chars = max(10000, min(100000, target_chars))

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(load_sql('list_messages_by_content_length'), (chat_id, before_id, before_id))
        all_rows = cur.fetchall()

        # Accumulate messages until we reach target content length
        selected_rows = []
        cumulative_length = 0
        min_messages = 5  # Always load at least 5 messages (unless fewer exist)
        max_messages = 100  # Never load more than 100 messages at once

        for row in all_rows:
            row_dict = row_to_dict(row, cur)
            content_len = row_dict.get('content_length', 0)

            # Always include the first min_messages
            if len(selected_rows) < min_messages:
                selected_rows.append(row_dict)
                cumulative_length += content_len
            # After min_messages, check if we've reached the target
            elif cumulative_length < target_chars and len(selected_rows) < max_messages:
                selected_rows.append(row_dict)
                cumulative_length += content_len
            else:
                # We've reached our target
                break
    finally:
        conn.close()

    # Reverse to chronological ascending for rendering
    selected_rows.reverse()

    # Annotate which messages belong to the current user to help UI alignment
    current_username = (user_session.get('username') or '').lower()
    for m in selected_rows:
        uname = (m.get('user_username') or m.get('username') or m.get('sender_username') or '').lower()
        m['is_self'] = (uname == current_username)

        if m.get('sender_username') == 'AI':
            meta = get_ai_model_config(m.get('ai_model_id'))
            m['sender_name'] = f"AI - {meta['display_name']}"
            m['sender_profile_color'] = '#3b82f6'
            m['ai_brand_color'] = meta.get('brand_color', '#7c3aed')

        m.pop('content_length', None)

    return jsonify({
        'messages': selected_rows,
        'has_more': len(all_rows) > len(selected_rows),
        'total_chars_loaded': cumulative_length
    })


@app.route('/api/chats/<chat_id>/messages', methods=['POST'])
def api_send_message(chat_id):
    user_session = session.get('user')
    if not user_session:
        return jsonify({'error': 'Not authenticated.'}), 401
    username = user_session.get('username')
    if not _is_member(chat_id, username):
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    reply_to = data.get('reply_to')
    if not content:
        return jsonify({'error': 'Message content is required.'}), 400
    if reply_to is not None and not isinstance(reply_to, int):
        reply_to = None
    
    # Store the user's message
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(load_sql('insert_message'), (chat_id, username, content, reply_to, None))
        if USE_POSTGRES:
            result = cur.fetchone()
            msg_id = result[0] if isinstance(result, tuple) else result['id']
        else:
            msg_id = cur.lastrowid
        conn.commit()
        cur2 = conn.cursor()
        cur2.execute(load_sql('get_message_by_id'), (msg_id,))
        row = cur2.fetchone()
    finally:
        conn.close()
    msg = row_to_dict(row, cur2)
    # hydrate sender meta
    sender = get_user_by_username(username)
    msg['sender_name'] = sender.get('name') if sender else username
    msg['sender_profile_color'] = sender.get('profile_color') if sender else random_profile_color()
    # mark as self for alignment on the client
    msg['is_self'] = True
    
    # Check if message starts with /AI
    if content.startswith('/AI'):
        # Extract the actual message without /AI prefix
        ai_query = content[3:].strip()
        if ai_query:
            try:
                model_id = session.get('ai_model_id') or DEFAULT_AI_MODEL_ID

                # Get chat history for context (excluding the current message we just inserted)
                conn3 = get_db_connection()
                try:
                    cur = conn3.cursor()
                    cur.execute(load_sql('list_messages_for_chat'), (chat_id, msg_id, msg_id, 50))
                    history_rows = [row_to_dict(r, cur) for r in cur.fetchall()]
                finally:
                    conn3.close()
                
                # Build message history for ChatAgent
                chat_history = []
                for h_msg in reversed(history_rows[-10:]):  # Use last 10 messages for context
                    role = "assistant" if h_msg.get('user_username') == 'AI' else "user"
                    chat_history.append({
                        "role": role,
                        "content": h_msg.get('content', '')
                    })
                
                # Filter chat history to only include messages relevant to the current query
                filtered_history = ChatAgent.filter_relevant_messages(
                    query=ai_query,
                    messages=chat_history,
                    model=model_id,
                    max_messages=6
                )

                agent = get_chat_agent(messages=filtered_history, model_id=model_id)
                response = agent.send_message(ai_query)
                ai_response = agent.get_last_assistant_message()

                # Extract response time from the response (in seconds)
                response_time_ns = response.get('total_duration', 0) if response else 0
                response_time_s = response_time_ns / 1_000_000_000  # Convert nanoseconds to seconds

                if ai_response:
                    # Format the AI response (convert markdown to HTML)
                    formatted_response = ResponseFormatter.format(ai_response)

                    # Insert AI response as a message from "AI" user
                    conn2 = get_db_connection()
                    try:
                        cur2 = conn2.cursor()
                        cur2.execute(load_sql('insert_message'), (chat_id, 'AI', formatted_response, msg_id, model_id))
                        if USE_POSTGRES:
                            result = cur2.fetchone()
                            ai_msg_id = result[0] if isinstance(result, tuple) else result['id']
                        else:
                            ai_msg_id = cur2.lastrowid
                        conn2.commit()
                        cur2.execute(load_sql('get_message_by_id'), (ai_msg_id,))
                        ai_row = cur2.fetchone()
                        ai_msg = row_to_dict(ai_row, cur2)
                    finally:
                        conn2.close()
                    ai_meta = get_ai_model_config(model_id)
                    ai_msg['sender_name'] = f"AI - {ai_meta['display_name']} ({response_time_s:.1f}s)"
                    ai_msg['sender_profile_color'] = '#3b82f6'  # Blue color for AI
                    ai_msg['is_self'] = False
                    
                    # Return both messages
                    return jsonify({'message': msg, 'ai_message': ai_msg}), 201
            except Exception as e:
                # If AI processing fails, just return the user's message
                print(f"AI processing error: {e}")
                pass
    
    return jsonify({'message': msg}), 201


@app.route('/api/chats/<chat_id>/messages/<int:message_id>', methods=['PUT'])
def api_edit_message(chat_id, message_id):
    user_session = session.get('user')
    if not user_session:
        return jsonify({'error': 'Not authenticated.'}), 401
    username = user_session.get('username')
    if not _is_member(chat_id, username):
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    if not content:
        return jsonify({'error': 'Message content is required.'}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        placeholder = "?" if not USE_POSTGRES else "%s"
        # Check if message exists and user owns it
        cur.execute(f"SELECT sender_username, content FROM messages WHERE id = {placeholder} AND chat_id = {placeholder}", (message_id, chat_id))
        msg = cur.fetchone()
        if not msg:
            return jsonify({'error': 'Message not found.'}), 404

        msg_sender = msg[0] if isinstance(msg, tuple) else msg['sender_username']

        if msg_sender.lower() != username.lower():
            return jsonify({'error': 'You can only edit your own messages.'}), 403

        # Update the message
        cur.execute(load_sql('update_message'), (content, message_id, message_id))
        conn.commit()

        # Get updated message
        cur2 = conn.cursor()
        cur2.execute(f"SELECT id, chat_id, sender_username, content, reply_to, created_at, edited_at, original_content FROM messages WHERE id = {placeholder}", (message_id,))
        row = cur2.fetchone()
    finally:
        conn.close()

    updated_msg = row_to_dict(row, cur2)
    sender = get_user_by_username(username)
    updated_msg['sender_name'] = sender.get('name') if sender else username
    updated_msg['sender_profile_color'] = sender.get('profile_color') if sender else random_profile_color()
    updated_msg['is_self'] = True

    return jsonify({'message': updated_msg}), 200


@app.route('/api/chats/<chat_id>/messages/<int:message_id>', methods=['DELETE'])
def api_delete_message(chat_id, message_id):
    user_session = session.get('user')
    if not user_session:
        return jsonify({'error': 'Not authenticated.'}), 401
    username = user_session.get('username')
    if not _is_member(chat_id, username):
        return jsonify({'error': 'Forbidden'}), 403

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        placeholder = "?" if not USE_POSTGRES else "%s"
        # Check if message exists
        cur.execute(f"SELECT sender_username, reply_to FROM messages WHERE id = {placeholder} AND chat_id = {placeholder}", (message_id, chat_id))
        msg = cur.fetchone()
        if not msg:
            return jsonify({'error': 'Message not found.'}), 404

        msg_sender = msg[0] if isinstance(msg, tuple) else msg['sender_username']
        reply_to_id = msg[1] if isinstance(msg, tuple) else msg['reply_to']

        # Allow deletion if:
        # 1. User owns the message, OR
        # 2. It's an AI message replying to the user's message
        is_owner = msg_sender.lower() == username.lower()
        is_ai_reply_to_user = False

        if msg_sender == 'AI' and reply_to_id:
            # Check if this AI message is replying to the user's message
            cur2 = conn.cursor()
            cur2.execute(f"SELECT sender_username FROM messages WHERE id = {placeholder}", (reply_to_id,))
            parent_msg = cur2.fetchone()
            parent_username = parent_msg[0] if isinstance(parent_msg, tuple) else parent_msg['sender_username'] if parent_msg else None
            if parent_msg and parent_username.lower() == username.lower():
                is_ai_reply_to_user = True

        if not is_owner and not is_ai_reply_to_user:
            return jsonify({'error': 'You can only delete your own messages or AI responses to your messages.'}), 403

        # Delete the message
        cur.execute(load_sql('delete_message'), (message_id,))
        conn.commit()
    finally:
        conn.close()

    return ('', 204)


@app.route('/api/chats/<chat_id>/messages/<int:message_id>/reply_to', methods=['PATCH'])
def api_update_reply_to(chat_id, message_id):
    user_session = session.get('user')
    if not user_session:
        return jsonify({'error': 'Not authenticated.'}), 401
    username = user_session.get('username')
    if not _is_member(chat_id, username):
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json(silent=True) or {}
    new_reply_to = data.get('reply_to')

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        placeholder = "?" if not USE_POSTGRES else "%s"
        # Check if message exists
        cur.execute(f"SELECT sender_username, reply_to FROM messages WHERE id = {placeholder} AND chat_id = {placeholder}", (message_id, chat_id))
        msg = cur.fetchone()
        if not msg:
            return jsonify({'error': 'Message not found.'}), 404

        msg_sender = msg[0] if isinstance(msg, tuple) else msg['sender_username']
        # Allow updating reply_to if it's an AI message
        if msg_sender != 'AI':
            return jsonify({'error': 'Can only update reply_to for AI messages.'}), 403

        # Update reply_to
        cur.execute(f"UPDATE messages SET reply_to = {placeholder} WHERE id = {placeholder}", (new_reply_to, message_id))
        conn.commit()
    finally:
        conn.close()

    return jsonify({'success': True}), 200


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
    username = user_session.get('username') or ''
    conn = get_db_connection()
    try:
        chat_id = _generate_chat_id(conn)
        pw_hash = generate_password_hash(password)
        cur = conn.cursor()
        cur.execute(load_sql('insert_chat'), (chat_id, name, pw_hash, username))
        cur.execute(load_sql('insert_chat_member'), (chat_id, username))
        conn.commit()
    finally:
        conn.close()
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
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(load_sql('get_chat_by_id'), (chat_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Chat not found.'}), 404
        chat = row_to_dict(row, cur)
        if not check_password_hash(chat['password_hash'], password):
            return jsonify({'error': 'Invalid chat password.'}), 403
        username = user_session.get('username') or ''
        cur.execute(load_sql('insert_chat_member'), (chat_id, username))
        conn.commit()
        return jsonify({'chat': {'id': chat_id, 'name': chat['name']}}), 200
    finally:
        conn.close()


@app.route('/api/admin/clear-db', methods=['POST'])
def api_admin_clear_db():
    # Protected endpoint to wipe users and chats. Requires ADMIN_TOKEN env and matching token in the header or query.
    admin_token = os.environ.get('ADMIN_TOKEN')
    provided = request.headers.get('X-Admin-Token') or request.args.get('token') or (request.get_json(silent=True) or {}).get('token')
    if not admin_token:
        return jsonify({'error': 'ADMIN_TOKEN is not configured on the server.'}), 500
    if not provided or provided != admin_token:
        return jsonify({'error': 'Forbidden'}), 403

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Count existing rows
        cur.execute('SELECT COUNT(*) FROM users')
        users_before = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM chats')
        chats_before = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM chat_members')
        members_before = cur.fetchone()[0]
        # Wipe in a safe order (members -> chats -> users), though no FKs are enforced.
        cur.execute('DELETE FROM chat_members')
        cur.execute('DELETE FROM chats')
        cur.execute('DELETE FROM users')
        conn.commit()
    finally:
        conn.close()
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

@app.route('/api/ai/models', methods=['GET'])
def api_list_ai_models():
    return jsonify({
        'models': AVAILABLE_AI_MODELS,
        'default_model_id': DEFAULT_AI_MODEL_ID,
        'active_model_id': session.get('ai_model_id') or DEFAULT_AI_MODEL_ID
    })


@app.route('/api/ai/model', methods=['POST'])
def api_set_ai_model():
    data = request.get_json(silent=True) or {}
    requested_model = (data.get('model_id') or '').strip()
    if requested_model not in AI_MODEL_LOOKUP:
        return jsonify({'error': 'Unknown AI model.'}), 400
    session['ai_model_id'] = requested_model
    return jsonify({'model': get_ai_model_config(requested_model)})


# Serve the React app's index.html for root and all other client-side routes
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    # Explicitly handle /static/* paths first - serve from BUILD_DIR/static
    if path.startswith('static/'):
        # Extract the relative path after 'static/'
        static_path = path[7:]  # Remove 'static/' prefix
        static_file = os.path.join(STATIC_DIR, static_path)
        if os.path.exists(static_file) and os.path.isfile(static_file):
            # Determine directory and filename for send_from_directory
            dir_path = os.path.dirname(static_file)
            file_name = os.path.basename(static_file)
            return send_from_directory(dir_path, file_name)

    # If the request is for a file within the build folder, serve it directly
    requested_path = os.path.join(BUILD_DIR, path)
    if path and os.path.exists(requested_path) and os.path.isfile(requested_path):
        # Serve files like favicon.ico, asset-manifest.json, etc.
        return send_from_directory(BUILD_DIR, path)

    # Fallback to index.html for client-side routing
    index_path = os.path.join(BUILD_DIR, 'index.html')
    if os.path.exists(index_path):
        # Serve the original index.html as generated by the client build
        try:
            return send_from_directory(BUILD_DIR, 'index.html')
        except Exception:
            # If any issue occurs, attempt to read and return the file contents
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    html = f.read()
                return html, 200, {'Content-Type': 'text/html; charset=utf-8'}
            except Exception:
                # As a last resort, 404
                return 'index.html not found', 404

    # Build missing: no non-React fallback. Return 404 to enforce React-only frontend.
    return 'Frontend build missing. Please build the React app.', 404


# Initialize DB on startup
init_db()

# Optionally clear databases on startup if env var is set to 1

def _clear_db_on_start_if_needed():
    flag = os.environ.get('CLEAR_DB_ON_START', '0')
    if str(flag).strip() == '1':
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            # Wipe in safe order (members -> chats -> users)
            cur.execute('DELETE FROM chat_members')
            cur.execute('DELETE FROM chats')
            cur.execute('DELETE FROM users')
            conn.commit()
        finally:
            conn.close()
        print('Cleared databases on startup because CLEAR_DB_ON_START=1')


if __name__ == '__main__':
    # Read host and port from env if provided (useful for deployment)
    # Railway and other cloud platforms require binding to 0.0.0.0 and using PORT env var
    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', os.environ.get('FLASK_RUN_PORT', '8080')))

    # Optionally clear DBs only when running as the main program (avoid clearing on import/reloader)
    _clear_db_on_start_if_needed()

    print(f"Starting Flask server on http://{host}:{port}")
    print(f"Serving static files from: {BUILD_DIR}")
    if USE_POSTGRES:
        print("Database: PostgreSQL (production mode)")
    else:
        print(f"Database: SQLite at {DATABASE} (development mode)")
    app.run(host=host, port=port, debug=False)

import os
import sqlite3
import random
import secrets
import re
import markdown
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

# Paths
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
BUILD_DIR = os.path.join(BASE_DIR, 'client', 'build')
STATIC_DIR = os.path.join(BUILD_DIR, 'static')
DATABASE = os.path.join(BASE_DIR, 'app.db')
SQL_DIR = os.path.join(BASE_DIR, 'sql')

# ChatAgent configuration
CHAT_MODEL = "deepseek-v3.1:671b-cloud"
CHAT_MODEL_DISPLAY_NAME = "DeepSeek-V3.1 (671b Cloud)"

def get_chat_agent(messages=None):
    return ChatAgent(model=CHAT_MODEL, messages=messages)

# SQL loader
_SQL_CACHE = {}

def load_sql(name: str) -> str:
    """Load SQL text by key from sql/main.sql.
    Sections are marked by lines starting with "-- name: <key>".
    Key caches results for the lifetime of the process.
    """
    if name in _SQL_CACHE:
        return _SQL_CACHE[name]

    # Try loading from main.sql once and cache all entries
    master_path = os.path.join(SQL_DIR, 'main.sql')
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
            # Surface an explicit error if main.sql cannot be parsed/read
            raise RuntimeError(f"Failed to load or parse main.sql: {e}")

    if name in _SQL_CACHE:
        return _SQL_CACHE[name]

    # No fallback to individual files; explicit error helps catch typos/missing queries
    available = [k for k in _SQL_CACHE.keys() if not k.startswith('_')]
    raise KeyError(f"SQL key '{name}' not found in main.sql. Available keys: {available}")

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
        # Create messages table and index
        try:
            conn.execute(load_sql('create_table_messages'))
            conn.execute(load_sql('create_index_messages_chat'))
        except Exception:
            pass

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
            sql = load_sql('update_user_dynamic').replace('/*SET_CLAUSE*/', ', '.join(updates))
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


def format_ai_response(text: str) -> str:
    """Format AI response by converting markdown to HTML with support for tables, LaTeX, code blocks, etc."""
    if not text:
        return text

    # Protect LaTeX equations by replacing them with placeholders
    latex_blocks = []

    def save_latex_display(match):
        """Save display math equations \\[ ... \\] or $$ ... $$"""
        latex_blocks.append(('display', match.group(1)))
        # Use HTML comments as placeholders to survive markdown processing
        return f"<!--LATEX_DISPLAY_{len(latex_blocks) - 1}-->"

    def save_latex_inline(match):
        """Save inline math equations \\( ... \\) or $ ... $"""
        latex_blocks.append(('inline', match.group(1)))
        return f"<!--LATEX_INLINE_{len(latex_blocks) - 1}-->"

    # Match and save LaTeX display equations: \[ ... \] or $$ ... $$
    text = re.sub(r'\\\[(.*?)\\\]', save_latex_display, text, flags=re.DOTALL)
    text = re.sub(r'\$\$(.*?)\$\$', save_latex_display, text, flags=re.DOTALL)

    # Match and save inline equations: \( ... \) or $ ... $
    text = re.sub(r'\\\((.*?)\\\)', save_latex_inline, text, flags=re.DOTALL)
    text = re.sub(r'(?<!\$)\$(?!\$)([^$\n]+?)\$', save_latex_inline, text)

    # Use markdown library with extensions for tables, fenced code blocks, and other features
    html = markdown.markdown(
        text,
        extensions=[
            'extra',      # Includes tables, fenced code blocks, abbreviations, etc.
            'nl2br',      # Convert newlines to <br> tags
            'sane_lists', # Better list handling
        ]
    )

    # Add styling to tables
    html = html.replace('<table>', '<table style="border-collapse: collapse; width: 100%; margin: 10px 0; border: 1px solid #ddd;">')
    html = html.replace('<th>', '<th style="border: 1px solid #ddd; padding: 8px; background-color: #f2f2f2; text-align: left; color: #000;">')
    html = html.replace('<td>', '<td style="border: 1px solid #ddd; padding: 8px;">')

    # Add styling to code blocks
    html = html.replace('<code>', '<code style="background-color: #f4f4f4; padding: 2px 4px; border-radius: 3px; font-family: monospace;">')
    html = html.replace('<pre>', '<pre style="background-color: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; margin: 10px 0;">')

    # Add styling to headers
    html = html.replace('<h1>', '<h1 style="margin-top: 20px; margin-bottom: 10px; font-size: 2em; font-weight: bold;">')
    html = html.replace('<h2>', '<h2 style="margin-top: 18px; margin-bottom: 8px; font-size: 1.5em; font-weight: bold;">')
    html = html.replace('<h3>', '<h3 style="margin-top: 16px; margin-bottom: 6px; font-size: 1.25em; font-weight: bold;">')
    html = html.replace('<h4>', '<h4 style="margin-top: 14px; margin-bottom: 4px; font-size: 1.1em; font-weight: bold;">')

    # Add styling to horizontal rules
    html = html.replace('<hr />', '<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;" />')
    html = html.replace('<hr>', '<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">')

    # Add styling to lists
    html = html.replace('<ul>', '<ul style="margin: 10px 0; padding-left: 20px;">')
    html = html.replace('<ol>', '<ol style="margin: 10px 0; padding-left: 20px;">')
    html = html.replace('<li>', '<li style="margin: 4px 0;">')

    # Add target="_blank" to all links
    html = re.sub(r'<a href="([^"]*)">', r'<a href="\1" target="_blank" rel="noopener noreferrer">', html)

    # Restore LaTeX equations with proper delimiters for MathJax/KaTeX
    for i, (latex_type, latex_content) in enumerate(latex_blocks):
        if latex_type == 'display':
            # Use display math delimiters that MathJax/KaTeX will recognize
            placeholder = f"<!--LATEX_DISPLAY_{i}-->"
            latex_html = f'<div class="math-display" style="margin: 15px 0; text-align: center; overflow-x: auto;">\\[{latex_content}\\]</div>'
            html = html.replace(placeholder, latex_html)
        else:  # inline
            # Use inline math delimiters
            placeholder = f"<!--LATEX_INLINE_{i}-->"
            latex_html = f'<span class="math-inline">\\({latex_content}\\)</span>'
            html = html.replace(placeholder, latex_html)

    return html




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


def _get_chat_members(chat_id: str):
    """Return members for a chat ordered by most recently joined (as a proxy for activity)."""
    with get_db_connection() as conn:
        cur = conn.execute(load_sql('list_chat_members'), (chat_id,))
        members = [dict(row) for row in cur.fetchall()]
        return members


def _is_member(chat_id: str, username: str) -> bool:
    with get_db_connection() as conn:
        cur = conn.execute("SELECT 1 FROM chat_members WHERE chat_id = ? AND user_username = ?", (chat_id, username))
        return cur.fetchone() is not None


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
    with get_db_connection() as conn:
        cur = conn.execute(load_sql('get_chat_by_id'), (chat_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Chat not found.'}), 404
        if not _is_member(chat_id, user_session.get('username')):
            return jsonify({'error': 'Forbidden'}), 403
        chat = dict(row)
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
        with get_db_connection() as conn:
            latest_id = conn.execute("SELECT MAX(id) FROM messages WHERE chat_id = ?", (chat_id,)).fetchone()[0]
        has_updates = latest_id is not None and latest_id > since_id
        return jsonify({'has_updates': has_updates, 'latest_id': latest_id})

    # pagination: before_id for backwards pagination (older messages)
    before_id = request.args.get('before_id', type=int)
    limit = request.args.get('limit', default=50, type=int)
    limit = max(1, min(200, limit))
    with get_db_connection() as conn:
        cur = conn.execute(load_sql('list_messages_for_chat'), (chat_id, before_id, before_id, limit))
        rows = [dict(r) for r in cur.fetchall()]
    # Reverse to chronological ascending for rendering
    rows.reverse()
    # Annotate which messages belong to the current user to help UI alignment
    current_username = (user_session.get('username') or '').lower()
    for m in rows:
        uname = (m.get('user_username') or m.get('username') or m.get('sender_username') or '').lower()
        m['is_self'] = (uname == current_username)
    return jsonify({'messages': rows})


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
    with get_db_connection() as conn:
        cur = conn.execute(load_sql('insert_message'), (chat_id, username, content, reply_to))
        msg_id = cur.lastrowid
        conn.commit()
        cur2 = conn.execute(load_sql('get_message_by_id'), (msg_id,))
        row = cur2.fetchone()
    msg = dict(row)
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
                # Get chat history for context (excluding the current message we just inserted)
                with get_db_connection() as conn:
                    cur = conn.execute(load_sql('list_messages_for_chat'), (chat_id, msg_id, msg_id, 20))
                    history_rows = [dict(r) for r in cur.fetchall()]
                
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
                    model=CHAT_MODEL,
                    max_messages=6  # Limit to most recent relevant messages
                )

                # Create ChatAgent with filtered history and send message
                agent = get_chat_agent(messages=filtered_history)
                response = agent.send_message(ai_query)
                ai_response = agent.get_last_assistant_message()
                
                if ai_response:
                    # Format the AI response (convert markdown to HTML)
                    formatted_response = format_ai_response(ai_response)

                    # Insert AI response as a message from "AI" user
                    with get_db_connection() as conn:
                        cur = conn.execute(load_sql('insert_message'), (chat_id, 'AI', formatted_response, msg_id))
                        ai_msg_id = cur.lastrowid
                        conn.commit()
                        cur2 = conn.execute(load_sql('get_message_by_id'), (ai_msg_id,))
                        ai_row = cur2.fetchone()
                    
                    ai_msg = dict(ai_row)
                    ai_msg['sender_name'] = f'AI - {CHAT_MODEL_DISPLAY_NAME}'
                    ai_msg['sender_profile_color'] = '#3b82f6'  # Blue color for AI
                    ai_msg['is_self'] = False
                    
                    # Return both messages
                    return jsonify({'message': msg, 'ai_message': ai_msg}), 201
            except Exception as e:
                # If AI processing fails, just return the user's message
                print(f"AI processing error: {e}")
                pass
    
    return jsonify({'message': msg}), 201


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
        username = user_session.get('username') or ''
        conn.execute(load_sql('insert_chat_member'), (chat_id, username))
        conn.commit()
        return jsonify({'chat': {'id': chat_id, 'name': chat['name']}}), 200


@app.route('/api/admin/clear-db', methods=['POST'])
def api_admin_clear_db():
    # Protected endpoint to wipe users and chats. Requires ADMIN_TOKEN env and matching token in the header or query.
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
        # Wipe in a safe order (members -> chats -> users), though no FKs are enforced.
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
        with get_db_connection() as conn:
            # Wipe in safe order (members -> chats -> users)
            conn.execute('DELETE FROM chat_members')
            conn.execute('DELETE FROM chats')
            conn.execute('DELETE FROM users')
            conn.commit()
        print('Cleared databases on startup because CLEAR_DB_ON_START=1')


if __name__ == '__main__':
    # Read host and port from env if provided (useful for deployment)
    # Railway and other cloud platforms require binding to 0.0.0.0 and using PORT env var
    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', os.environ.get('FLASK_RUN_PORT', '8080')))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'

    # Optionally clear DBs only when running as the main program (avoid clearing on import/reloader)
    _clear_db_on_start_if_needed()

    print(f"Starting Flask server on http://{host}:{port}")
    print(f"Serving static files from: {BUILD_DIR}")
    app.run(host=host, port=port, debug=debug)
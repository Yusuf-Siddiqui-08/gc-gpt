-- Master SQL file containing all queries used by the application
-- Use markers "-- name: <key>" to define each query block.

-- name: create_table_users
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    profile_color TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- name: create_table_chats
CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    creator_username TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- name: create_table_chat_members
CREATE TABLE IF NOT EXISTS chat_members (
    chat_id TEXT NOT NULL,
    user_username TEXT NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, user_username)
);

-- name: pragma_table_info_users
PRAGMA table_info(users);

-- name: alter_table_add_profile_color
ALTER TABLE users ADD COLUMN profile_color TEXT;

-- name: alter_table_add_username
ALTER TABLE users ADD COLUMN username TEXT;

-- name: get_user_by_username
SELECT id, username, name, password_hash, profile_color
FROM users
WHERE LOWER(username) = LOWER(?);

-- name: insert_user
INSERT INTO users (name, username, password_hash, profile_color)
VALUES (?, ?, ?, ?);

-- name: update_user_profile_color
UPDATE users SET profile_color = ? WHERE id = ?;

-- name: update_user_dynamic
UPDATE users SET /*SET_CLAUSE*/ WHERE id = ?;

-- name: select_user_id_by_username
SELECT id FROM users WHERE LOWER(username) = LOWER(?);

-- name: list_user_chats
SELECT
  c.id,
  c.name,
  c.created_at,
  c.creator_username
FROM chats c
JOIN chat_members m ON m.chat_id = c.id
WHERE m.user_username = ?
ORDER BY datetime(c.created_at) DESC;

-- name: list_chat_members
SELECT u.username, u.name, COALESCE(u.profile_color, '') AS profile_color,
       m.joined_at
FROM chat_members m
JOIN users u ON u.username = m.user_username
WHERE m.chat_id = ?
ORDER BY datetime(m.joined_at) DESC;

-- name: insert_chat
INSERT INTO chats (id, name, password_hash, creator_username)
VALUES (?, ?, ?, ?);

-- name: insert_chat_member
INSERT OR IGNORE INTO chat_members (chat_id, user_username)
VALUES (?, ?);

-- name: get_chat_by_id
SELECT id, name, password_hash, creator_username, created_at
FROM chats
WHERE id = ?;

-- name: create_table_messages
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    sender_username TEXT NOT NULL,
    content TEXT NOT NULL,
    reply_to INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    edited_at TIMESTAMP,
    original_content TEXT
);

-- name: create_index_messages_chat
CREATE INDEX IF NOT EXISTS idx_messages_chat_created ON messages(chat_id, datetime(created_at));

-- name: insert_message
INSERT INTO messages (chat_id, sender_username, content, reply_to)
VALUES (?, ?, ?, ?);

-- name: list_messages_for_chat
SELECT m.id, m.chat_id, m.sender_username, m.content, m.reply_to, m.created_at, m.edited_at, m.original_content,
       u.name AS sender_name, COALESCE(u.profile_color, '') AS sender_profile_color
FROM messages m
LEFT JOIN users u ON u.username = m.sender_username
WHERE m.chat_id = ? AND (m.id < ? OR ? IS NULL)
ORDER BY m.id DESC
LIMIT ?;

-- name: get_message_by_id
SELECT id, chat_id, sender_username, content, reply_to, created_at
FROM messages
WHERE id = ?;

-- name: list_messages_by_content_length
SELECT m.id, m.chat_id, m.sender_username, m.content, m.reply_to, m.created_at, m.edited_at, m.original_content,
       u.name AS sender_name, COALESCE(u.profile_color, '') AS sender_profile_color,
       LENGTH(m.content) AS content_length
FROM messages m
LEFT JOIN users u ON u.username = m.sender_username
WHERE m.chat_id = ? AND (m.id < ? OR ? IS NULL)
ORDER BY m.id DESC;

-- name: update_message
UPDATE messages
SET content = ?, edited_at = CURRENT_TIMESTAMP, original_content = COALESCE(original_content, (SELECT content FROM messages WHERE id = ?))
WHERE id = ?;

-- name: delete_message
DELETE FROM messages WHERE id = ?;

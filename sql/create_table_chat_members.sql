CREATE TABLE IF NOT EXISTS chat_members (
    chat_id TEXT NOT NULL,
    user_username TEXT NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, user_username)
);
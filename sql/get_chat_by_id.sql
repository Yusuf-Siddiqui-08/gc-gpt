SELECT id, name, password_hash, creator_username, created_at
FROM chats
WHERE id = ?;
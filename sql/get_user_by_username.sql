SELECT id, username, name, password_hash, profile_color
FROM users
WHERE LOWER(username) = LOWER(?);
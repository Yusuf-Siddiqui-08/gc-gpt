SELECT
  c.id,
  c.name,
  c.created_at,
  c.creator_username
FROM chats c
JOIN chat_members m ON m.chat_id = c.id
WHERE m.user_username = ?
ORDER BY datetime(c.created_at) DESC;

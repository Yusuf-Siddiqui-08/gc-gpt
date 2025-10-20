// React and ReactDOM are loaded via CDN in index.html
const { useState, useEffect, useRef, useMemo } = React;

// Derived avatar style used for user initials
const avatarStyle = {
  width: 24,
  height: 24,
  borderRadius: '50%',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontWeight: 700,
  color: '#fff',
  fontSize: 12
};

// Minimal inline styles fallback used by auth/settings forms.
const styles = {
  panel: { background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 12, padding: 24 },
  label: { display: 'grid', gap: 6, fontSize: 14, color: '#9ca3af' },
  input: { padding: '10px 12px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.06)', color: '#e5e7eb', outline: 'none' },
  btn: { display: 'inline-block', padding: '8px 12px', borderRadius: 8, background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.35)', color: '#cfe1ff', fontWeight: 600, cursor: 'pointer' },
  btnPrimary: { background: '#3b82f6', borderColor: '#3b82f6', color: '#fff' },
  linkBtn: { background: 'transparent', border: 'none', color: '#e5e7eb', padding: 0, cursor: 'pointer' },
  error: { padding: '10px 12px', borderRadius: 8, marginBottom: 12, background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.35)', color: '#fecaca' },
  authForm: { display: 'grid', gap: 12, maxWidth: 420 },
};

function nameInitials(name) {
  const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
  if (parts.length === 2) return (parts[0].charAt(0) + parts[1].charAt(0)).toUpperCase();
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

function colorFromString(s) {
  // deterministic fallback color if profile_color is missing
  let hash = 0;
  const str = String(s || 'user');
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash |= 0; // Convert to 32bit int
  }
  const color = '#' + ((hash >>> 0) & 0x00FFFFFF).toString(16).padStart(6, '0');
  return color;
}

function navigate(path) {
  const guard = window.__confirmBeforeNavigate;
  if (typeof guard === 'function') {
    const ok = guard(path);
    if (!ok) return;
  }
  if (window.location.pathname !== path) {
    window.history.pushState({}, '', path);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }
}

function usePathname() {
  const [path, setPath] = useState(window.location.pathname);
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);
  return [path, (p) => navigate(p)];
}

async function api(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
    credentials: 'same-origin',
  });
  let data = null;
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) {
    data = await res.json().catch(() => ({}));
  } else {
    data = {};
  }
  if (!res.ok) {
    const err = new Error((data && data.error) || `Request failed (${res.status})`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

function Navbar({ user, onLogout, go }) {
  const [open, setOpen] = useState(false);
  const boxRef = useRef(null);
  useEffect(() => {
    function onDocClick(e) {
      if (!boxRef.current) return;
      if (!boxRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('click', onDocClick);
    return () => document.removeEventListener('click', onDocClick);
  }, []);

  return React.createElement('nav', { className: 'gcapp-navbar' },
    React.createElement('a', { className: 'gcapp-brand', onClick: () => go('/') }, 'Group Chat GPT'),
    React.createElement('div', { className: 'gcapp-navRight' },
      user ? React.createElement('div', { ref: boxRef, className: 'gcapp-rel' },
        React.createElement('button', {
          onClick: () => setOpen((v) => !v),
          className: 'userBox',
          title: user.username
        },
          React.createElement('span', {
            className: 'gcapp-avatar',
            style: { background: (user && user.profile_color) ? user.profile_color : colorFromString(user?.username || user?.name) },
            'aria-hidden': 'true'
          }, nameInitials(user?.name)),
          React.createElement('span', null, user.name)
        ),
        open && React.createElement('div', { className: 'gcapp-dropdown' },
          React.createElement('button', { onClick: () => { setOpen(false); go('/settings'); }, className: 'gcapp-dropdown-item' }, 'Profile settings'),
          React.createElement('button', { onClick: () => { setOpen(false); go('/my-conversations'); }, className: 'gcapp-dropdown-item' }, 'My Conversations'),
          React.createElement('button', { onClick: () => { setOpen(false); onLogout(); }, className: 'gcapp-dropdown-item' }, 'Log out')
        )
      ) : React.createElement('div', { className: 'userBox' },
        React.createElement('a', {
          href: '#',
          className: 'gcapp-btn',
          onClick: (e) => { e.preventDefault(); go('/login'); },
          role: 'button',
          'aria-label': 'Log in',
          title: 'Log in'
        }, 'Log in')
      )
    )
  );
}

function Home({ user }) {
  return React.createElement('div', { className: 'gcapp-panel' },
    user ? React.createElement('div', null,
      React.createElement('h1', { className: 'mt-0' }, `Welcome back, ${user.name}!`),
      React.createElement('p', null, 'You are now logged in.')
    ) : React.createElement('div', null,
      React.createElement('h1', { className: 'mt-0' }, 'Welcome!'),
      React.createElement('p', null, 'Please log in or sign up to continue.')
    )
  );
}

function Conversations({ user }) {
  const [items, setItems] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const res = await api('GET', '/api/chats');
        if (!alive) return;
        setItems(res.chats || []);
        setError('');
      } catch (err) {
        if (!alive) return;
        if (err.status === 401) {
          setItems([]);
          setError('Please log in to manage chats.');
        } else {
          setError('Failed to load chats.');
        }
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  return React.createElement('div', { className: 'gcapp-panel' },
    React.createElement('div', { className: 'flex-sb-center gap-12' },
      React.createElement('h2', { className: 'm-0' }, 'My Conversations'),
      React.createElement('button', {
        className: 'btn primary',
        onClick: () => { if (user) setShowModal(true); else navigate('/login'); }
      }, 'New Chat')
    ),
    error && React.createElement('div', { className: 'gcapp-error mt-10' }, error),
    loading ? React.createElement('p', { className: 'mt-12' }, 'Loading…') :
    items.length === 0 ? React.createElement('p', { className: 'mt-12', style: { color: 'var(--muted)' } }, 'No conversations yet.') :
    React.createElement('div', { className: 'grid-10 mt-12' },
      items.map((c) => React.createElement('div', {
        key: c.id,
        className: 'gcapp-row clickable',
        onClick: () => navigate(`/chat/${c.id}`)
      },
        React.createElement('div', null,
          React.createElement('div', { className: 'fw-700' }, c.name || 'Untitled'),
          React.createElement('div', { className: 'muted small' }, `ID: ${c.id}${c.created_at ? ` · Created ${c.created_at}` : ''}`)
        ),
        React.createElement('div', null,
          React.createElement('button', {
            className: 'btn outline',
            onClick: (e) => {
              e.stopPropagation();
              navigator.clipboard?.writeText(c.id)
            }
          }, 'Copy ID')
        )
      ))
    ),
    showModal && React.createElement(ChatModal, {
      onClose: () => setShowModal(false),
      onChanged: async () => {
        try {
          const res = await api('GET', '/api/chats');
          setItems(res.chats || []);
        } catch {}
      }
    })
  );
}

function Modal({ title, onClose, children }) {
  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose?.(); }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return React.createElement('div', {
    className: 'modal-backdrop',
    role: 'dialog',
    'aria-modal': 'true',
    style: { display: 'flex' },
    onClick: (e) => { if (e.target === e.currentTarget) onClose?.(); }
  },
    React.createElement('div', { className: 'modal' },
      React.createElement('header', null,
        React.createElement('strong', null, title),
        React.createElement('button', {
          className: 'btn outline',
          type: 'button',
          onClick: onClose,
          'aria-label': 'Close'
        }, 'Close')
      ),
      children
    )
  );
}

function ChatModal({ onClose, onChanged }) {
  const [step, setStep] = useState('choose'); // 'choose' | 'create' | 'join'
  const [createName, setCreateName] = useState('');
  const [createPw, setCreatePw] = useState('');
  const [joinId, setJoinId] = useState('');
  const [joinPw, setJoinPw] = useState('');
  const [error, setError] = useState('');

  async function handleCreate(e) {
    e.preventDefault();
    setError('');
    if (!createName || !createPw) { setError('Name and password are required.'); return; }
    try {
      const res = await api('POST', '/api/chats', { name: createName, password: createPw });
      alert(`Chat created. Share this ID with others: ${res.chat?.id || ''}`);
      onClose?.();
      onChanged?.();
    } catch (err) {
      setError(err.data?.error || 'Failed to create chat.');
    }
  }

  async function handleJoin(e) {
    e.preventDefault();
    setError('');
    if (!joinId || !joinPw) { setError('Chat ID and password are required.'); return; }
    try {
      const res = await api('POST', '/api/chats/join', { chat_id: joinId, password: joinPw });
      alert(`Joined chat: ${res.chat?.name || joinId}`);
      onClose?.();
      onChanged?.();
    } catch (err) {
      setError(err.data?.error || 'Failed to join chat.');
    }
  }

  return React.createElement(Modal, { title: 'New Chat', onClose },
    step === 'choose' && React.createElement('div', { className: 'body' },
      React.createElement('div', { className: 'row' },
        React.createElement('label', null, 'What would you like to do?'),
        React.createElement('div', { className: 'muted small' }, 'Create a brand new chat or join an existing one using its ID and password.')
      ),
      React.createElement('div', { style: { display: 'flex', gap: 8, flexWrap: 'wrap' } },
        React.createElement('button', { className: 'btn primary', onClick: () => setStep('create') }, 'Create new chat'),
        React.createElement('button', { className: 'btn outline', onClick: () => setStep('join') }, 'Join with code')
      )
    ),
    step === 'create' && React.createElement('form', { onSubmit: handleCreate },
      React.createElement('div', { className: 'body' },
        error && React.createElement('div', { className: 'error' }, error),
        React.createElement('div', { className: 'row' },
          React.createElement('label', null, 'Chat name',
            React.createElement('input', {
              className: 'input',
              type: 'text',
              value: createName,
              onChange: (e) => setCreateName(e.target.value),
              required: true
            })
          )
        ),
        React.createElement('div', { className: 'row' },
          React.createElement('label', null, 'Chat password',
            React.createElement('input', {
              className: 'input',
              type: 'password',
              value: createPw,
              onChange: (e) => setCreatePw(e.target.value),
              required: true
            })
          )
        )
      ),
      React.createElement('div', { className: 'actions' },
        React.createElement('button', {
          type: 'button',
          className: 'btn outline',
          onClick: () => { setError(''); setStep('choose'); }
        }, 'Back'),
        React.createElement('button', { type: 'submit', className: 'btn primary' }, 'Create')
      )
    ),
    step === 'join' && React.createElement('form', { onSubmit: handleJoin },
      React.createElement('div', { className: 'body' },
        error && React.createElement('div', { className: 'error' }, error),
        React.createElement('div', { className: 'row' },
          React.createElement('label', null, 'Chat ID',
            React.createElement('input', {
              className: 'input',
              type: 'text',
              value: joinId,
              onChange: (e) => setJoinId(e.target.value),
              required: true
            })
          )
        ),
        React.createElement('div', { className: 'row' },
          React.createElement('label', null, 'Chat password',
            React.createElement('input', {
              className: 'input',
              type: 'password',
              value: joinPw,
              onChange: (e) => setJoinPw(e.target.value),
              required: true
            })
          )
        )
      ),
      React.createElement('div', { className: 'actions' },
        React.createElement('button', {
          type: 'button',
          className: 'btn outline',
          onClick: () => { setError(''); setStep('choose'); }
        }, 'Back'),
        React.createElement('button', { type: 'submit', className: 'btn primary' }, 'Join')
      )
    )
  );
}

function MyConversations({ user }) {
  return React.createElement(Conversations, { user });
}

function MessageItem({ msg, prevSenderId, onEdit, onDelete }) {
  const [showOriginal, setShowOriginal] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isHovering, setIsHovering] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const menuRef = useRef(null);

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setShowMenu(false);
      }
    }
    if (showMenu) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [showMenu]);

  const handleEditClick = () => {
    setShowMenu(false);
    // Extract text content from HTML for editing
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = msg.content;
    let textContent = tempDiv.textContent || tempDiv.innerText || '';

    // Remove /AI prefix if present (so user edits the actual message content)
    if (textContent.startsWith('/AI ')) {
      textContent = textContent.substring(4); // Remove '/AI '
    }

    setEditContent(textContent);
    setIsEditing(true);
  };

  const handleDeleteClick = () => {
    setShowMenu(false);
    onDelete(msg.id);
  };

  const handleSaveEdit = async () => {
    if (editContent.trim() && !isSaving) {
      setIsSaving(true);
      try {
        await onEdit(msg.id, editContent.trim());
        setIsEditing(false);
      } finally {
        setIsSaving(false);
      }
    }
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditContent('');
  };

  return React.createElement('div', {
    className: 'message-bubble',
    style: {
      display: 'flex',
      flexDirection: 'column',
      alignItems: msg.is_self ? 'flex-end' : 'flex-start',
      gap: 4,
      width: '100%'
    },
    onMouseEnter: () => setIsHovering(true),
    onMouseLeave: () => setIsHovering(false)
  },
    React.createElement('div', {
      style: { fontSize: 12, color: 'var(--muted)', display: 'flex', gap: 8, alignItems: 'center' }
    },
      msg.sender_name || msg.user_username,
      msg.edited_at && React.createElement('span', {
        onClick: () => setShowOriginal(!showOriginal),
        style: {
          fontWeight: 'bold',
          cursor: 'pointer',
          color: '#3b82f6',
          userSelect: 'none'
        },
        title: showOriginal ? 'Hide original message' : 'Show original message'
      }, 'Edited')
    ),
    showOriginal && msg.original_content && React.createElement('div', {
      style: {
        maxWidth: '70%',
        padding: '12px 16px',
        borderRadius: 18,
        background: 'rgba(128,128,128,0.3)',
        color: '#999',
        wordWrap: 'break-word',
        fontStyle: 'italic',
        marginBottom: 4,
        border: '1px dashed rgba(255,255,255,0.2)'
      },
      dangerouslySetInnerHTML: { __html: msg.original_content }
    }),
    isEditing ? React.createElement('div', {
      style: {
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        width: '100%',
        maxWidth: '70%'
      }
    },
      React.createElement('textarea', {
        value: editContent,
        onChange: (e) => setEditContent(e.target.value),
        style: {
          padding: '12px 16px',
          borderRadius: 12,
          border: '1px solid rgba(255,255,255,0.12)',
          background: 'rgba(255,255,255,0.08)',
          color: 'var(--text)',
          outline: 'none',
          minHeight: '80px',
          resize: 'vertical',
          fontFamily: 'inherit'
        }
      }),
      React.createElement('div', { style: { display: 'flex', gap: 8 } },
        React.createElement('button', {
          className: 'btn primary',
          onClick: handleSaveEdit,
          disabled: isSaving,
          style: { fontSize: 12, padding: '6px 12px' }
        }, isSaving ? 'Thinking...' : 'Save'),
        !isSaving && React.createElement('button', {
          className: 'btn outline',
          onClick: handleCancelEdit,
          style: { fontSize: 12, padding: '6px 12px' }
        }, 'Cancel')
      )
    ) : React.createElement('div', {
      style: {
        display: 'flex',
        alignItems: 'flex-start',
        gap: 8,
        maxWidth: '70%',
        position: 'relative'
      }
    },
      // 3-dot menu button (shown on hover for user's own messages)
      msg.is_self && isHovering && React.createElement('div', {
        ref: menuRef,
        style: {
          position: 'relative',
          display: 'flex',
          alignItems: 'center'
        }
      },
        React.createElement('button', {
          onClick: (e) => {
            e.stopPropagation();
            setShowMenu(!showMenu);
          },
          style: {
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            fontSize: 16,
            padding: 4,
            color: 'var(--muted)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 24,
            height: 24
          },
          title: 'Message options'
        }, '⋮'),
        // Dropdown menu
        showMenu && React.createElement('div', {
          style: {
            position: 'absolute',
            top: '100%',
            left: 0,
            background: 'rgba(20,20,25,0.98)',
            border: '1px solid rgba(255,255,255,0.15)',
            borderRadius: 12,
            padding: '6px',
            minWidth: 150,
            zIndex: 1000,
            boxShadow: '0 8px 24px rgba(0,0,0,0.5), 0 2px 8px rgba(0,0,0,0.3)',
            marginTop: 6,
            backdropFilter: 'blur(10px)'
          }
        },
          React.createElement('button', {
            onClick: handleEditClick,
            style: {
              width: '100%',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              padding: '10px 12px',
              color: 'var(--text)',
              textAlign: 'left',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              fontSize: 14,
              borderRadius: 8,
              transition: 'background 0.15s ease'
            },
            onMouseEnter: (e) => e.target.style.background = 'rgba(255,255,255,0.12)',
            onMouseLeave: (e) => e.target.style.background = 'transparent',
            title: 'Edit message'
          }, '✏️', ' Edit'),
          React.createElement('button', {
            onClick: handleDeleteClick,
            style: {
              width: '100%',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              padding: '10px 12px',
              color: '#ef4444',
              textAlign: 'left',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              fontSize: 14,
              borderRadius: 8,
              transition: 'background 0.15s ease'
            },
            onMouseEnter: (e) => {
              e.target.style.background = 'rgba(239,68,68,0.15)';
              e.target.style.color = '#fca5a5';
            },
            onMouseLeave: (e) => {
              e.target.style.background = 'transparent';
              e.target.style.color = '#ef4444';
            },
            title: 'Delete message'
          }, '🗑️', ' Delete')
        )
      ),
      React.createElement('div', {
        style: {
          flex: 1,
          padding: '12px 16px',
          borderRadius: 18,
          background: msg.is_self ? 'var(--primary)' : 'rgba(255,255,255,0.08)',
          color: msg.is_self ? '#fff' : undefined,
          wordWrap: 'break-word'
        },
        dangerouslySetInnerHTML: { __html: msg.content }
      })
    )
  );
}

function Chat({ chatId, user, go }) {
  const [chat, setChat] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [aiEnabled, setAiEnabled] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [hasMoreMessages, setHasMoreMessages] = useState(true);

  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const lastMessageCountRef = useRef(0);
  const lastTypesetIdRef = useRef(0);
  const isInitialLoadRef = useRef(true);
  const previousScrollHeightRef = useRef(0);

  useEffect(() => {
    if (!user) {
      go('/login');
      return;
    }
    loadChat();
  }, [chatId, user]);

  // Optimized MathJax typesetting - only process new messages
  useEffect(() => {
    if (!window.MathJax || !window.MathJax.typesetPromise) return;

    const newMessageCount = messages.length;
    if (newMessageCount <= lastMessageCountRef.current) return;

    // Only typeset new messages
    const newMessagesStartIndex = lastMessageCountRef.current;
    lastMessageCountRef.current = newMessageCount;

    // Use requestIdleCallback for better performance
    const typesetNewMessages = () => {
      const container = messagesContainerRef.current;
      if (!container) return;

      // Find only the new message elements
      const allMessageElements = container.querySelectorAll('.message-bubble');
      const newElements = Array.from(allMessageElements).slice(newMessagesStartIndex);

      if (newElements.length > 0) {
        window.MathJax.typesetPromise(newElements).catch((err) => {
          console.error('MathJax typeset error:', err);
        });
      }
    };

    if (window.requestIdleCallback) {
      window.requestIdleCallback(typesetNewMessages, { timeout: 500 });
    } else {
      setTimeout(typesetNewMessages, 0);
    }
  }, [messages.length]);

  // Auto-scroll to bottom on initial load or when new messages arrive
  useEffect(() => {
    if (messagesEndRef.current && messages.length > 0) {
      // On initial load, scroll immediately to bottom
      if (isInitialLoadRef.current) {
        messagesEndRef.current.scrollIntoView({ behavior: 'auto' });
        isInitialLoadRef.current = false;
      } else {
        // For new messages, smooth scroll
        messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }
  }, [messages.length]);

  // Infinite scroll: load older messages when scrolling to top
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      // Check if user scrolled near the top (within 100px)
      if (container.scrollTop < 100 && hasMoreMessages && !loadingOlder && messages.length > 0) {
        loadOlderMessages();
      }
    };

    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
  }, [messages, hasMoreMessages, loadingOlder]);

  async function loadChat() {
    try {
      setLoading(true);
      isInitialLoadRef.current = true;
      const [chatRes, messagesRes] = await Promise.all([
        api('GET', `/api/chats/${chatId}`),
        api('GET', `/api/chats/${chatId}/messages?max_chars=50000`)
      ]);
      setChat(chatRes.chat);
      setMessages(messagesRes.messages || []);
      setHasMoreMessages(messagesRes.has_more !== false);
      setError('');
      lastMessageCountRef.current = 0; // Reset counter for initial load
    } catch (err) {
      if (err.status === 403) {
        setError('You are not a member of this chat.');
      } else if (err.status === 404) {
        setError('Chat not found.');
      } else {
        setError('Failed to load chat.');
      }
    } finally {
      setLoading(false);
    }
  }

  async function loadOlderMessages() {
    if (loadingOlder || !hasMoreMessages || messages.length === 0) return;

    setLoadingOlder(true);
    const container = messagesContainerRef.current;
    const oldScrollHeight = container?.scrollHeight || 0;
    previousScrollHeightRef.current = oldScrollHeight;

    try {
      const oldestMessageId = messages[0].id;
      const res = await api('GET', `/api/chats/${chatId}/messages?before_id=${oldestMessageId}&max_chars=30000`);
      const olderMessages = res.messages || [];

      if (olderMessages.length === 0 || res.has_more === false) {
        setHasMoreMessages(false);
      } else {
        setMessages(prev => [...olderMessages, ...prev]);

        // Maintain scroll position after loading older messages
        setTimeout(() => {
          if (container) {
            const newScrollHeight = container.scrollHeight;
            const scrollDiff = newScrollHeight - oldScrollHeight;
            container.scrollTop = scrollDiff;
          }
        }, 0);
      }
    } catch (err) {
      console.error('Failed to load older messages:', err);
    } finally {
      setLoadingOlder(false);
    }
  }

  async function sendMessage(e) {
    e.preventDefault();
    if (!newMessage.trim() || sending) return;

    setSending(true);
    try {
      const messageContent = aiEnabled
        ? `/AI ${newMessage.trim()}`
        : newMessage.trim();

      const res = await api('POST', `/api/chats/${chatId}/messages`, {
        content: messageContent
      });
      setNewMessage('');
      // Reset AI toggle after sending
      setAiEnabled(false);
      // Add the new message to the list
      setMessages(prev => [...prev, res.message]);

      // If there's an AI response, add it too
      if (res.ai_message) {
        setMessages(prev => [...prev, res.ai_message]);
      }
    } catch (err) {
      alert('Failed to send message: ' + (err.data?.error || err.message));
    } finally {
      setSending(false);
    }
  }

  async function handleEditMessage(messageId, newContent) {
    try {
      // Find the message being edited
      const msgIndex = messages.findIndex(m => m.id === messageId);
      if (msgIndex === -1) return;

      const originalMessage = messages[msgIndex];
      const wasAiPrompt = originalMessage.content.includes('/AI');

      // Check if the next message is an AI response to this message
      const nextMessage = msgIndex < messages.length - 1 ? messages[msgIndex + 1] : null;
      const isNextAiResponse = nextMessage && nextMessage.sender_username === 'AI' && nextMessage.reply_to === messageId;

      // If this was an AI prompt and we're editing it, delete the AI response and resend
      if (wasAiPrompt && isNextAiResponse) {
        if (!confirm('Editing this message will delete the AI response and send a new prompt. Continue?')) {
          return;
        }
        // Delete the AI response
        await api('DELETE', `/api/chats/${chatId}/messages/${nextMessage.id}`);
        // Remove AI message from state
        setMessages(prev => prev.filter(m => m.id !== nextMessage.id));
      }

      // Update the message - keep /AI prefix if it was an AI prompt
      const contentToSave = wasAiPrompt ? `/AI ${newContent}` : newContent;
      const res = await api('PUT', `/api/chats/${chatId}/messages/${messageId}`, {
        content: contentToSave
      });

      // Update the message in state
      setMessages(prev => prev.map(m => m.id === messageId ? { ...res.message, is_self: m.is_self } : m));

      // If it was an AI prompt, generate new AI response
      if (wasAiPrompt) {
        setSending(true);
        try {
          // Send the /AI prompt to get the AI response
          // This will create a duplicate user message, so we'll need to delete it
          const aiRes = await api('POST', `/api/chats/${chatId}/messages`, {
            content: `/AI ${newContent}`
          });

          const duplicateMessageId = aiRes.message?.id;
          const aiMessageId = aiRes.ai_message?.id;

          // Delete the duplicate user message that was just created
          if (duplicateMessageId) {
            try {
              await api('DELETE', `/api/chats/${chatId}/messages/${duplicateMessageId}`);
            } catch (deleteErr) {
              console.error('Failed to delete duplicate message:', deleteErr);
            }
          }

          // Update the AI response's reply_to to point to the original edited message
          if (aiMessageId) {
            try {
              await api('PATCH', `/api/chats/${chatId}/messages/${aiMessageId}/reply_to`, {
                reply_to: messageId
              });
              // Update the AI message in our local state to reflect the correct reply_to
              if (aiRes.ai_message) {
                aiRes.ai_message.reply_to = messageId;
              }
            } catch (patchErr) {
              console.error('Failed to update AI message reply_to:', patchErr);
            }
          }

          // Only add the AI response
          if (aiRes.ai_message) {
            setMessages(prev => [...prev, aiRes.ai_message]);
          }
        } catch (err) {
          console.error('Failed to get new AI response:', err);
        } finally {
          setSending(false);
        }
      }
    } catch (err) {
      alert('Failed to edit message: ' + (err.data?.error || err.message));
    }
  }

  async function handleDeleteMessage(messageId) {
    try {
      // Find the message being deleted
      const msgIndex = messages.findIndex(m => m.id === messageId);
      if (msgIndex === -1) return;

      const messageToDelete = messages[msgIndex];

      // Check if the next message is an AI response to this message
      const nextMessage = msgIndex < messages.length - 1 ? messages[msgIndex + 1] : null;
      const isNextAiResponse = nextMessage && nextMessage.sender_username === 'AI' && nextMessage.reply_to === messageId;

      // Ask for confirmation
      let shouldDeleteAi = false;
      if (isNextAiResponse) {
        const confirmMsg = 'This message has an AI response. Delete both the message and AI response?';
        if (!confirm(confirmMsg)) return;
        shouldDeleteAi = true;
      } else {
        if (!confirm('Are you sure you want to delete this message?')) return;
      }

      // If there's an AI response, delete it FIRST (before deleting the parent message)
      // This way the backend can still verify that the AI message is replying to the user's message
      if (shouldDeleteAi && nextMessage) {
        try {
          await api('DELETE', `/api/chats/${chatId}/messages/${nextMessage.id}`);
          setMessages(prev => prev.filter(m => m.id !== nextMessage.id));
        } catch (err) {
          console.error('Failed to delete AI response:', err);
          alert('Failed to delete AI response: ' + (err.data?.error || err.message));
          return; // Don't proceed to delete the user message if AI deletion failed
        }
      }

      // Now delete the user's message
      await api('DELETE', `/api/chats/${chatId}/messages/${messageId}`);
      setMessages(prev => prev.filter(m => m.id !== messageId));

    } catch (err) {
      alert('Failed to delete message: ' + (err.data?.error || err.message));
    }
  }

  // Memoize message list rendering
  const messageElements = useMemo(() => {
    if (messages.length === 0) {
      return React.createElement('div', {
        style: {
          textAlign: 'center',
          color: 'var(--muted)',
          marginTop: 40
        }
      }, 'No messages yet. Start the conversation!');
    }

    return messages.map((msg, index) => {
      const prevMsg = index > 0 ? messages[index - 1] : null;
      const prevSenderId = prevMsg ? (prevMsg.user_username || prevMsg.sender_username) : null;

      return React.createElement(MessageItem, {
        key: msg.id,
        msg: msg,
        prevSenderId: prevSenderId,
        onEdit: handleEditMessage,
        onDelete: handleDeleteMessage
      });
    });
  }, [messages]);

  if (loading) {
    return React.createElement('div', { className: 'gcapp-panel' }, 'Loading chat...');
  }

  if (error) {
    return React.createElement('div', { className: 'gcapp-panel' },
      React.createElement('div', { className: 'gcapp-error' }, error),
      React.createElement('button', {
        className: 'btn primary',
        onClick: () => go('/my-conversations')
      }, 'Back to Conversations')
    );
  }

  return React.createElement('div', { style: { height: '100%', display: 'flex', flexDirection: 'column', paddingBottom: '20px' } },
    React.createElement('div', {
      style: {
        padding: '16px 24px',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        background: 'rgba(255,255,255,0.05)'
      }
    },
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 12 } },
        React.createElement('button', {
          className: 'btn outline',
          onClick: () => go('/my-conversations')
        }, '← Back'),
        React.createElement('div', null,
          React.createElement('h2', { style: { margin: 0 } }, chat?.name || 'Chat'),
          React.createElement('div', { className: 'muted small' }, `ID: ${chatId}`)
        )
      )
    ),
    React.createElement('div', {
      ref: messagesContainerRef,
      style: {
        flex: 1,
        padding: '20px',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 0,
        position: 'relative'
      }
    },
      loadingOlder && React.createElement('div', {
        style: {
          textAlign: 'center',
          padding: '10px',
          color: 'var(--muted)',
          fontSize: '14px'
        }
      }, 'Loading older messages...'),
      messageElements,
      React.createElement('div', { ref: messagesEndRef })
    ),
    React.createElement('form', {
      onSubmit: sendMessage,
      style: {
        padding: '16px 20px',
        marginTop: '20px',
        borderRadius: '16px',
        border: '1px solid rgba(255,255,255,0.12)',
        background: 'rgba(255,255,255,0.08)',
        display: 'flex',
        gap: 12,
        alignItems: 'center',
        flexShrink: 0
      }
    },
      // AI Toggle Button
      React.createElement('button', {
        type: 'button',
        onClick: () => setAiEnabled(!aiEnabled),
        'aria-label': aiEnabled ? 'AI mode enabled' : 'Enable AI mode',
        title: aiEnabled ? 'AI mode enabled - next message will include /AI' : 'Enable AI mode',
        style: {
          width: 44,
          height: 44,
          borderRadius: '50%',
          border: aiEnabled ? '2px solid #3b82f6' : '1px solid rgba(255,255,255,0.12)',
          background: aiEnabled ? 'rgba(59,130,246,0.2)' : 'rgba(255,255,255,0.06)',
          color: aiEnabled ? '#3b82f6' : 'rgba(255,255,255,0.5)',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 20,
          transition: 'all 0.2s ease',
          flexShrink: 0
        }
      },
        React.createElement('span', {
          style: {
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: 'system-ui, -apple-system, sans-serif'
          }
        }, '🤖')
      ),
      React.createElement('input', {
        type: 'text',
        value: newMessage,
        onChange: (e) => setNewMessage(e.target.value),
        placeholder: aiEnabled ? 'Message with AI...' : 'Type a message...',
        disabled: sending,
        style: {
          flex: 1,
          padding: '12px 16px',
          borderRadius: 25,
          border: aiEnabled ? '1px solid rgba(59,130,246,0.3)' : '1px solid rgba(255,255,255,0.12)',
          background: 'rgba(255,255,255,0.06)',
          color: 'var(--text)',
          outline: 'none'
        }
      }),
      React.createElement('button', {
        type: 'submit',
        disabled: sending || !newMessage.trim(),
        className: 'btn primary',
        style: { borderRadius: 25 }
      }, sending ? 'Thinking...' : 'Send')
    )
  );
}

function Login({ onLoggedIn, go }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    try {
      const res = await api('POST', '/api/login', { username, password });
      onLoggedIn(res.user);
      go('/');
    } catch (err) {
      setError(err.data?.error || 'Login failed.');
    }
  }

  return React.createElement('div', { className: 'gcapp-panel' },
    React.createElement('h2', { className: 'mt-0' }, 'Log in'),
    error && React.createElement('div', { className: 'gcapp-error' }, error),
    React.createElement('form', { onSubmit: handleSubmit, className: 'gcapp-authForm', autoComplete: 'on' },
      React.createElement('label', { style: styles.label }, 'Username',
        React.createElement('input', {
          style: styles.input,
          type: 'text',
          required: true,
          value: username,
          onChange: (e) => setUsername(e.target.value),
          autoComplete: 'username'
        })
      ),
      React.createElement('label', { style: styles.label }, 'Password',
        React.createElement('input', {
          style: styles.input,
          type: 'password',
          required: true,
          value: password,
          onChange: (e) => setPassword(e.target.value),
          autoComplete: 'current-password'
        })
      ),
      React.createElement('button', { type: 'submit', style: { ...styles.btn, ...styles.btnPrimary } }, 'Log in')
    ),
    React.createElement('div', { style: { marginTop: 12 } },
      React.createElement('button', {
        style: styles.linkBtn,
        onClick: (e) => { e.preventDefault(); go('/signup'); },
        'aria-label': 'Don\'t have an account? Sign up',
        title: 'Don\'t have an account? Sign up'
      }, 'Don\'t have an account? Sign up')
    )
  );
}

function Signup({ onLoggedIn, go }) {
  const [name, setName] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    try {
      const res = await api('POST', '/api/signup', { name, username, password });
      onLoggedIn(res.user);
      go('/');
    } catch (err) {
      setError(err.data?.error || 'Sign up failed.');
    }
  }

  return React.createElement('div', { style: styles.panel },
    React.createElement('h2', { style: { marginTop: 0 } }, 'Sign up'),
    error && React.createElement('div', { style: styles.error }, error),
    React.createElement('form', { onSubmit: handleSubmit, style: styles.authForm, autoComplete: 'on' },
      React.createElement('label', { style: styles.label }, 'Name',
        React.createElement('input', {
          style: styles.input,
          type: 'text',
          required: true,
          value: name,
          onChange: (e) => setName(e.target.value),
          autoComplete: 'name'
        })
      ),
      React.createElement('label', { style: styles.label }, 'Username',
        React.createElement('input', {
          style: styles.input,
          type: 'text',
          required: true,
          value: username,
          onChange: (e) => setUsername(e.target.value),
          autoComplete: 'username'
        })
      ),
      React.createElement('label', { style: styles.label }, 'Password',
        React.createElement('input', {
          style: styles.input,
          type: 'password',
          required: true,
          value: password,
          onChange: (e) => setPassword(e.target.value),
          autoComplete: 'new-password'
        })
      ),
      React.createElement('button', { type: 'submit', style: { ...styles.btn, ...styles.btnPrimary } }, 'Create account')
    )
  );
}

function ProfileSettings({ user, onSaved, go }) {
  const [name, setName] = useState(user?.name || '');
  const [username, setUsername] = useState(user?.username || '');
  const [password, setPassword] = useState('');
  const [profileColor, setProfileColor] = useState(user?.profile_color || colorFromString(user?.username || user?.name));
  const initial = useRef({ name: user?.name || '', username: user?.username || '', profileColor: user?.profile_color || '' });

  const dirty = name !== initial.current.name || username !== initial.current.username || password.length > 0 || (profileColor || '') !== (initial.current.profileColor || '');

  useEffect(() => {
    function beforeUnload(e) {
      if (dirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    }
    window.addEventListener('beforeunload', beforeUnload);
    const guard = (nextPath) => {
      if (!dirty) return true;
      return window.confirm('You have unsaved changes. Click "Cancel" to stay and Apply changes.');
    };
    window.__confirmBeforeNavigate = guard;
    return () => {
      window.removeEventListener('beforeunload', beforeUnload);
      if (window.__confirmBeforeNavigate === guard) window.__confirmBeforeNavigate = null;
    };
  }, [dirty]);

  async function handleApply() {
    try {
      const res = await api('POST', '/api/profile', { name, username, password, profile_color: profileColor });
      onSaved(res.user);
      initial.current = { name: res.user.name, username: res.user.username, profileColor: res.user.profile_color || '' };
      setPassword('');
      alert('Profile updated.');
    } catch (err) {
      alert(err.data?.error || 'Failed to apply changes.');
    }
  }

  return React.createElement('div', { style: styles.panel },
    React.createElement('h2', { style: { marginTop: 0, marginBottom: 8 } }, 'Profile settings'),
    React.createElement('div', { style: { display: 'grid', gap: 16 } },
      React.createElement('section', { style: { padding: 12, border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10 } },
        React.createElement('h3', { style: { marginTop: 0 } }, 'Contact settings'),
        React.createElement('div', { style: { display: 'grid', gap: 10, maxWidth: 520 } },
          React.createElement('label', { style: styles.label }, 'Name',
            React.createElement('input', {
              style: styles.input,
              type: 'text',
              value: name,
              onChange: (e) => setName(e.target.value)
            })
          ),
          React.createElement('label', { style: styles.label }, 'Username',
            React.createElement('input', {
              style: styles.input,
              type: 'text',
              value: username,
              onChange: (e) => setUsername(e.target.value)
            })
          ),
          React.createElement('label', { style: styles.label }, 'Password',
            React.createElement('input', {
              style: styles.input,
              type: 'password',
              placeholder: 'Leave blank to keep current password',
              value: password,
              onChange: (e) => setPassword(e.target.value)
            })
          )
        )
      ),
      React.createElement('section', { style: { padding: 12, border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10 } },
        React.createElement('h3', { style: { marginTop: 0 } }, 'Profile picture'),
        React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 12 } },
          React.createElement('span', {
            style: { ...avatarStyle, width: 40, height: 40, background: profileColor, fontSize: 14 },
            'aria-hidden': 'true'
          }, nameInitials(name)),
          React.createElement('div', { style: { display: 'grid', gap: 6 } },
            React.createElement('label', { style: styles.label }, 'Background colour',
              React.createElement('input', {
                type: 'color',
                className: 'gc-color-input',
                value: profileColor || '#3b82f6',
                onChange: (e) => setProfileColor(e.target.value),
                style: { width: 48, height: 32, padding: 0, border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, background: 'transparent' },
                'aria-label': 'Choose profile background colour'
              })
            )
          )
        )
      ),
      React.createElement('div', { style: { display: 'flex', justifyContent: 'flex-end' } },
        React.createElement('button', {
          onClick: handleApply,
          style: { ...styles.btn, ...styles.btnPrimary, opacity: dirty ? 1 : 0.8 },
          disabled: !dirty
        }, 'Apply changes')
      )
    )
  );
}

function App() {
  const [path, go] = usePathname();
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await api('GET', '/api/me');
        setUser(res.user || null);
      } catch {
        setUser(null);
      } finally {
        setReady(true);
      }
    })();
  }, []);

  async function handleLogout() {
    try {
      await api('POST', '/api/logout', {});
    } catch {}
    setUser(null);
    go('/');
  }

  function renderRoute() {
    if (path === '/settings') {
      if (!user) return React.createElement('div', { className: 'gcapp-panel' }, 'Please log in to edit your profile.');
      return React.createElement(ProfileSettings, { user, onSaved: (u) => setUser(u), go });
    }
    if (path === '/my-conversations') {
      return React.createElement(MyConversations, { user });
    }
    if (path === '/login') {
      if (user) return React.createElement(Home, { user });
      return React.createElement(Login, { onLoggedIn: (u) => setUser(u), go });
    }
    if (path === '/signup') {
      if (user) return React.createElement(Home, { user });
      return React.createElement(Signup, { onLoggedIn: (u) => setUser(u), go });
    }
    if (path.startsWith('/chat/')) {
      const chatId = path.substring('/chat/'.length);
      return React.createElement(Chat, { chatId, user, go });
    }
    return React.createElement(Home, { user });
  }

  return React.createElement('div', { className: 'gcapp-app' },
    React.createElement(Navbar, { user, onLogout: handleLogout, go }),
    React.createElement('main', { className: 'gcapp-container' },
      !ready ? React.createElement('div', { className: 'gcapp-panel' }, 'Loading...') : renderRoute()
    )
  );
}

// Mount the app
const rootElement = document.getElementById('root');
if (rootElement) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(React.createElement(App));
}

// Signal that the app has mounted successfully
window.__APP_MOUNTED__ = true;

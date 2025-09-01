// React and ReactDOM are loaded via CDN in index.html

// styles moved to CSS (client/build/static/css/app.css)

// Derived avatar style used for user initials
const avatarStyle = { width: 24, height: 24, borderRadius: '50%', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, color: '#fff', fontSize: 12 };

// Minimal inline styles fallback used by auth/settings forms.
// Note: Main styles are in CSS (static/css/app.css). These keep pages working
// even if classNames are missing, and prevent ReferenceError when navigating to /login.
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
  const [path, setPath] = React.useState(window.location.pathname);
  React.useEffect(() => {
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
  const [open, setOpen] = React.useState(false);
  const boxRef = React.useRef(null);
  React.useEffect(() => {
    function onDocClick(e) {
      if (!boxRef.current) return;
      if (!boxRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('click', onDocClick);
    return () => document.removeEventListener('click', onDocClick);
  }, []);
  return (
    <nav className="gcapp-navbar">
      <a className="gcapp-brand" onClick={() => go('/')}>MyApp</a>
      <div className="gcapp-navRight">
        {user ? (
          <>
            <div ref={boxRef} className="gcapp-rel">
              <button
                onClick={() => setOpen((v) => !v)}
                className="userBox"
                title={user.username}
              >
                <span
                  className="gcapp-avatar"
                  style={{ background: (user && user.profile_color) ? user.profile_color : colorFromString(user?.username || user?.name) }}
                  aria-hidden="true"
                >
                  {nameInitials(user?.name)}
                </span>
                <span>{user.name}</span>
              </button>
              {open && (
                <div className="gcapp-dropdown">
                  <button onClick={() => { setOpen(false); go('/settings'); }} className="gcapp-dropdown-item">Profile settings</button>
                  <button onClick={() => { setOpen(false); go('/my-conversations'); }} className="gcapp-dropdown-item">My Conversations</button>
                  <button onClick={() => { setOpen(false); onLogout(); }} className="gcapp-dropdown-item">Log out</button>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="userBox">
            <a
              href="#"
              className="gcapp-btn"
              onClick={(e) => { e.preventDefault(); go('/login'); }}
              role="button"
              aria-label="Log in"
              title="Log in"
            >
              Log in
            </a>
          </div>
        )}
      </div>
    </nav>
  );
}

function Home({ user }) {
  return (
    <div className="gcapp-panel">
      {user ? (
        <>
          <h1 className="mt-0">Welcome back, {user.name}!</h1>
          <p>You are now logged in.</p>
        </>
      ) : (
        <>
          <h1 className="mt-0">Welcome!</h1>
          <p>
            Please log in or sign up to continue.
          </p>
        </>
      )}
    </div>
  );
}

function Conversations({ user }) {
  const [items, setItems] = React.useState([]);
  const [error, setError] = React.useState('');
  const [loading, setLoading] = React.useState(true);
  const [showModal, setShowModal] = React.useState(false);

  React.useEffect(() => {
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

  return (
    <div className="gcapp-panel">
      <div className="flex-sb-center gap-12">
        <h2 className="m-0">My Conversations</h2>
        <button className="btn primary" onClick={() => { if (user) setShowModal(true); else navigate('/login'); }}>New Chat</button>
      </div>
      {error && <div className="gcapp-error mt-10">{error}</div>}
      {loading ? (
        <p className="mt-12">Loading…</p>
      ) : items.length === 0 ? (
        <p className="mt-12" style={{ color: 'var(--muted)' }}>No conversations yet.</p>
      ) : (
        <div className="grid-10 mt-12">
          {items.map((c) => (
            <div key={c.id} className="gcapp-row">
              <div>
                <div className="fw-700">{c.name || 'Untitled'}</div>
                <div className="muted small">ID: {c.id}{c.created_at ? ` · Created ${c.created_at}` : ''}</div>
              </div>
              <div>
                <button className="btn outline" onClick={() => navigator.clipboard?.writeText(c.id)}>Copy ID</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <ChatModal
          onClose={() => setShowModal(false)}
          onChanged={async () => {
            try { const res = await api('GET', '/api/chats'); setItems(res.chats || []); } catch {}
          }}
        />
      )}
    </div>
  );
}

function Modal({ title, onClose, children }) {
  React.useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose?.(); }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" style={{ display: 'flex' }} onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
      <div className="modal">
        <header>
          <strong>{title}</strong>
          <button className="btn outline" type="button" onClick={onClose} aria-label="Close">Close</button>
        </header>
        {children}
      </div>
    </div>
  );
}

function ChatModal({ onClose, onChanged }) {
  const [step, setStep] = React.useState('choose'); // 'choose' | 'create' | 'join'
  const [createName, setCreateName] = React.useState('');
  const [createPw, setCreatePw] = React.useState('');
  const [joinId, setJoinId] = React.useState('');
  const [joinPw, setJoinPw] = React.useState('');
  const [error, setError] = React.useState('');

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

  return (
    <Modal title="New Chat" onClose={onClose}>
      {step === 'choose' && (
        <div className="body">
          <div className="row">
            <label>What would you like to do?</label>
            <div className="muted small">Create a brand new chat or join an existing one using its ID and password.</div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button className="btn primary" onClick={() => setStep('create')}>Create new chat</button>
            <button className="btn outline" onClick={() => setStep('join')}>Join with code</button>
          </div>
        </div>
      )}

      {step === 'create' && (
        <form onSubmit={handleCreate}>
          <div className="body">
            {error && <div className="error">{error}</div>}
            <div className="row">
              <label>Chat name
                <input className="input" type="text" value={createName} onChange={(e) => setCreateName(e.target.value)} required />
              </label>
            </div>
            <div className="row">
              <label>Chat password
                <input className="input" type="password" value={createPw} onChange={(e) => setCreatePw(e.target.value)} required />
              </label>
            </div>
          </div>
          <div className="actions">
            <button type="button" className="btn outline" onClick={() => { setError(''); setStep('choose'); }}>Back</button>
            <button type="submit" className="btn primary">Create</button>
          </div>
        </form>
      )}

      {step === 'join' && (
        <form onSubmit={handleJoin}>
          <div className="body">
            {error && <div className="error">{error}</div>}
            <div className="row">
              <label>Chat ID
                <input className="input" type="text" value={joinId} onChange={(e) => setJoinId(e.target.value)} required />
              </label>
            </div>
            <div className="row">
              <label>Chat password
                <input className="input" type="password" value={joinPw} onChange={(e) => setJoinPw(e.target.value)} required />
              </label>
            </div>
          </div>
          <div className="actions">
            <button type="button" className="btn outline" onClick={() => { setError(''); setStep('choose'); }}>Back</button>
            <button type="submit" className="btn primary">Join</button>
          </div>
        </form>
      )}
    </Modal>
  );
}

function MyConversations({ user }) {
  return <Conversations user={user} />;
}

function Login({ onLoggedIn, go }) {
  const [username, setUsername] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [error, setError] = React.useState('');

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

  return (
    <div className="gcapp-panel">
      <h2 className="mt-0">Log in</h2>
      {error && <div className="gcapp-error">{error}</div>}
      <form onSubmit={handleSubmit} className="gcapp-authForm" autoComplete="on">
        <label style={styles.label}>Username
          <input style={styles.input} type="text" required value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
        </label>
        <label style={styles.label}>Password
          <input style={styles.input} type="password" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
        </label>
        <button type="submit" style={{ ...styles.btn, ...styles.btnPrimary }}>Log in</button>
      </form>
      <div style={{ marginTop: 12 }}>
        <button
          style={styles.linkBtn}
          onClick={(e) => { e.preventDefault(); go('/signup'); }}
          aria-label="Don't have an account? Sign up"
          title="Don't have an account? Sign up"
        >
          Don't have an account? Sign up
        </button>
      </div>
    </div>
  );
}

function Signup({ onLoggedIn, go }) {
  const [name, setName] = React.useState('');
  const [username, setUsername] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [error, setError] = React.useState('');

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

  return (
    <div style={styles.panel}>
      <h2 style={{ marginTop: 0 }}>Sign up</h2>
      {error && <div style={styles.error}>{error}</div>}
      <form onSubmit={handleSubmit} style={styles.authForm} autoComplete="on">
        <label style={styles.label}>Name
          <input style={styles.input} type="text" required value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
        </label>
        <label style={styles.label}>Username
          <input style={styles.input} type="text" required value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
        </label>
        <label style={styles.label}>Password
          <input style={styles.input} type="password" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
        </label>
        <button type="submit" style={{ ...styles.btn, ...styles.btnPrimary }}>Create account</button>
      </form>
    </div>
  );
}

function ProfileSettings({ user, onSaved, go }) {
  const [name, setName] = React.useState(user?.name || '');
  const [username, setUsername] = React.useState(user?.username || '');
  const [password, setPassword] = React.useState('');
  const [profileColor, setProfileColor] = React.useState(user?.profile_color || colorFromString(user?.username || user?.name));
  const initial = React.useRef({ name: user?.name || '', username: user?.username || '', profileColor: user?.profile_color || '' });

  const dirty = name !== initial.current.name || username !== initial.current.username || password.length > 0 || (profileColor || '') !== (initial.current.profileColor || '');

  React.useEffect(() => {
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

  const colorOptions = ['#3b82f6','#ef4444','#10b981','#f59e0b','#8b5cf6','#0ea5e9','#f43f5e','#22c55e','#14b8a6','#eab308'];

  return (
    <div style={styles.panel}>
      <h2 style={{ marginTop: 0, marginBottom: 8 }}>Profile settings</h2>
      <div style={{ display: 'grid', gap: 16 }}>
        <section style={{ padding: 12, border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10 }}>
          <h3 style={{ marginTop: 0 }}>Contact settings</h3>
          <div style={{ display: 'grid', gap: 10, maxWidth: 520 }}>
            <label style={styles.label}>Name
              <input style={styles.input} type="text" value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label style={styles.label}>Username
              <input style={styles.input} type="text" value={username} onChange={(e) => setUsername(e.target.value)} />
            </label>
            <label style={styles.label}>Password
              <input style={styles.input} type="password" placeholder="Leave blank to keep current password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
          </div>
        </section>
        <section style={{ padding: 12, border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10 }}>
          <h3 style={{ marginTop: 0 }}>Profile picture</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ ...avatarStyle, width: 40, height: 40, background: profileColor, fontSize: 14 }} aria-hidden="true">{nameInitials(name)}</span>
            <div style={{ display: 'grid', gap: 6 }}>
              <label style={styles.label}>Background colour
                <input
                  type="color"
                  className="gc-color-input"
                  value={profileColor || '#3b82f6'}
                  onChange={(e) => setProfileColor(e.target.value)}
                  style={{ width: 48, height: 32, padding: 0, border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, background: 'transparent' }}
                  aria-label="Choose profile background colour"
                />
              </label>
            </div>
          </div>
        </section>
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button
            onClick={handleApply}
            style={{ ...styles.btn, ...styles.btnPrimary, opacity: dirty ? 1 : 0.8 }}
            disabled={!dirty}
          >
            Apply changes
          </button>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [path, go] = usePathname();
  const [user, setUser] = React.useState(null);
  const [ready, setReady] = React.useState(false);

  React.useEffect(() => {
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
      if (!user) return <div className="gcapp-panel">Please log in to edit your profile.</div>;
      return <ProfileSettings user={user} onSaved={(u) => setUser(u)} go={go} />;
    }
    if (path === '/my-conversations') {
      return <MyConversations user={user} />;
    }
    if (path === '/login') {
      if (user) return <Home user={user} />;
      return <Login onLoggedIn={(u) => setUser(u)} go={go} />;
    }
    if (path === '/signup') {
      if (user) return <Home user={user} />;
      return <Signup onLoggedIn={(u) => setUser(u)} go={go} />;
    }
    return <Home user={user} />;
  }

  return (
    <div className="gcapp-app">
      <Navbar user={user} onLogout={handleLogout} go={go} />
      <main className="gcapp-container">
        {!ready ? (
          <div className="gcapp-panel">Loading...</div>
        ) : (
          renderRoute()
        )}
      </main>
    </div>
  );
}

const rootElement = document.getElementById('root');
if (rootElement) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(<App />);
}

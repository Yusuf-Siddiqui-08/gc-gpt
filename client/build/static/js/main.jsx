const containerStyle = {
  fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif',
  margin: '2rem auto',
  maxWidth: '720px'
};

const preStyle = {
  padding: '1rem',
  background: '#f6f8fa',
  border: '1px solid #e1e4e8',
  borderRadius: '6px',
  overflowX: 'auto'
};

function App() {
  const [data, setData] = React.useState(null);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <div style={containerStyle}>
      <h1>Flask + React using JSX</h1>
      <p>This page is rendered with React JSX transpiled in the browser via Babel Standalone.</p>
      <pre style={preStyle}>
        {error ? (
          <>Failed to fetch /api/health: {error}</>
        ) : data ? (
          JSON.stringify(data, null, 2)
        ) : (
          'Checking backend health...'
        )}
      </pre>
      <p style={{ color: '#666' }}>
        For production, replace this with a real build pipeline (Vite/CRA) and serve the compiled assets.
      </p>
    </div>
  );
}

const rootElement = document.getElementById('root');
if (rootElement) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(<App />);
}

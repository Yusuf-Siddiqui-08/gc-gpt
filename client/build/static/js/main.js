(function(){
  const root = document.getElementById('root');
  const container = document.createElement('div');
  container.style.fontFamily = 'system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif';
  container.style.margin = '2rem auto';
  container.style.maxWidth = '720px';

  const title = document.createElement('h1');
  title.textContent = 'Flask serving a React-like frontend';

  const p = document.createElement('p');
  p.textContent = 'This is a minimal static bundle that simulates a React build.';

  const status = document.createElement('pre');
  status.textContent = 'Checking backend health...';
  status.style.padding = '1rem';
  status.style.background = '#f6f8fa';
  status.style.border = '1px solid #e1e4e8';
  status.style.borderRadius = '6px';
  status.style.overflowX = 'auto';

  container.appendChild(title);
  container.appendChild(p);
  container.appendChild(status);
  root.innerHTML = '';
  root.appendChild(container);

  fetch('/api/health').then(r => r.json()).then(data => {
    status.textContent = JSON.stringify(data, null, 2);
  }).catch(err => {
    status.textContent = 'Failed to fetch /api/health: ' + err;
  });
})();

# Group Chat GPT — Flask backend serving a static frontend

This repository contains a minimal Flask backend that serves a prebuilt static frontend (placed under `client/build`). It currently ships a simple homepage for the product “Group Chat GPT.”

Note: You can replace the provided static homepage with a real React app's production build at any time (see instructions below).

## Prerequisites
- Python 3.9+
- pip

## Setup

1. Create and activate a virtual environment (optional but recommended):

   Windows PowerShell:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

## Run the server

```powershell
python app.py
```

The server will start on http://127.0.0.1:5000

- Health check: http://127.0.0.1:5000/api/health
- Frontend: http://127.0.0.1:5000/

## Replacing the static bundle with a real React app

If you have a React project (e.g., created via Create React App, Vite, or Next.js static export), build it and copy the production output into `client/build`.

For Create React App:

```powershell
# inside your React app directory
npm install
npm run build

# copy build to this repo
# Replace <path-to-this-repo> with the actual path
Copy-Item -Recurse -Force .\build\* <path-to-this-repo>\client\build\
```

Flask is already configured to serve:
- `/static/*` assets from `client/build/static`
- Any other files in `client/build` directly (e.g., `favicon.ico`, `manifest.json`)
- Fallback to `client/build/index.html` for any unknown path to support client-side routing

## Notes
- Environment variables:
  - `FLASK_RUN_HOST` (default `127.0.0.1`)
  - `FLASK_RUN_PORT` (default `5000`)
  - `FLASK_DEBUG` (default `1`)
- CORS is enabled via `flask-cors` for convenience during development.

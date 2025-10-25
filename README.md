# Group Chat GPT — Flask backend serving a static frontend

This repository contains a minimal Flask backend that serves a prebuilt React frontend (placed under `client/build`).

New endpoints provide per-chat messaging with timestamps, avatars, and reply support. If you don't have a React build, the backend exposes APIs only; no non-React HTML UI is shipped anymore.

Note: Bring your own React app build (see instructions below).

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

## Frontend layout and build

The repository serves a prebuilt frontend only and does not keep a `client/src` directory.
- Build output (if you provide one): `client/build/`

A minimal toolchain is provided via `client/package.json` only if you want to copy or prepare static files under `client/build` yourself; by default, there's no source tree to build:

```powershell
cd client
npm install --silent  # optional
# If you have your own app, produce files into client/build yourself.
```

Flask is already configured to serve:
- `/static/*` assets from `client/build/static`
- Any other files in `client/build` directly (e.g., `favicon.ico`, `manifest.json`)
- Fallback to `client/build/index.html` for any unknown path to support client-side routing

You can replace the placeholder with any real React/Vite/CRA app. Just have your toolchain output to `client/build/`.

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

### /api/chats response enrichment
Each chat item now includes:
- members: array of { username, name, profile_color, initials } ordered by most-recent joined.
- avatar_layout: object with:
  - type: one of single, double, triple
  - users: usernames used in the layout (for triple, last three active)
  - positions: same length as users; each has normalized x, y (0..1 in a square), r (radius 0..1), overlap (suggested overlap ratio), zIndex.

This is designed so a frontend can render composite chat logos:
- 1 member: full-circle single avatar
- 2 members: side-by-side with slight overlap
- 3+ members: use last three active and arrange in a tri-venn layout
- Environment variables:
  - `FLASK_RUN_HOST` (default `127.0.0.1`)
  - `FLASK_RUN_PORT` (default `5000`)
  - `FLASK_DEBUG` (default `1`)
- CORS is enabled via `flask-cors` for convenience during development.

## SQL management
- Queries are centralized in `sql/main.sql` (SQLite) or `sql/postgres.sql` (PostgreSQL) using sections marked by lines like `-- name: query_key`.
- The app automatically loads the appropriate SQL file based on the database type.
- To add or modify a query:
  1. Edit both `sql/main.sql` and `sql/postgres.sql` and add a new section:

     -- name: my_new_query
     SELECT ...;
  2. Update code to call `load_sql('my_new_query')`.
  3. Note: PostgreSQL uses `%s` placeholders, SQLite uses `?` placeholders.

## Database Configuration

The application supports both SQLite (for local development) and PostgreSQL (for production deployment on Railway).

### Local Development (SQLite)
By default, the app uses SQLite with a database file at `app.db`. No configuration needed.

### Production Deployment (PostgreSQL on Railway)

The app automatically detects and uses PostgreSQL when the following environment variables are present:

#### Option 1: Using DATABASE_URL (Recommended for Railway)
Railway automatically provides this variable when you provision a PostgreSQL database:
```
DATABASE_URL=postgresql://user:password@host:port/database
```

#### Option 2: Using individual PostgreSQL variables
```
PGHOST=your-postgres-host
PGPORT=5432
PGDATABASE=your-database-name
PGUSER=your-username
PGPASSWORD=your-password
PGSSLMODE=prefer
```

### Deploying to Railway

1. **Create a new project on Railway**
   - Go to [Railway.app](https://railway.app)
   - Click "New Project"
   - Connect your GitHub repository

2. **Add a PostgreSQL database**
   - Click "New" → "Database" → "Add PostgreSQL"
   - Railway will automatically provision a database and set the `DATABASE_URL` environment variable

3. **Set environment variables** (in Railway dashboard under Variables):
   ```
   SECRET_KEY=your-secret-key-here
   SESSION_COOKIE_SECURE=True
   PORT=8080
   ```

4. **Deploy**
   - Railway will automatically detect the `requirements.txt` and `app.py`
   - Your app will be deployed and accessible via a Railway domain

5. **Database migrations**
   - The app automatically creates tables on first run
   - No manual migration needed

### Environment Variables Reference

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection string | None | No (uses SQLite if not set) |
| `SECRET_KEY` | Flask secret key for sessions | `dev-secret-change-me` | Yes (for production) |
| `SESSION_COOKIE_SECURE` | Use secure cookies (HTTPS only) | `True` | No |
| `PORT` | Server port | `8080` | No |
| `CLEAR_DB_ON_START` | Clear database on startup (1=yes) | `0` | No |
| `ADMIN_TOKEN` | Token for admin endpoints | None | No |

---

## Name usage disclaimer
- This project uses the term "GPT" in the product name purely in a descriptive sense to indicate a class of generative AI chat capabilities familiar to users.
- The project is not affiliated with, endorsed by, or sponsored by OpenAI, Inc. or any of its products or services.
- "OpenAI" and "GPT" may be trademarks or service marks of their respective owners. Any references are for identification purposes only.

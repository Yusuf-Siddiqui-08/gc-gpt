# Group Chat GPT

A collaborative messaging platform that brings powerful, context-aware AI models directly into your group conversations.

Group Chat GPT is a collaborative messaging application featuring a Flask backend that serves a prebuilt React frontend. It allows users to create private group conversations and interact with various integrated AI models using a simple `/AI` command.

## Key Features

* **Collaborative Group Messaging**: Create or join password-protected chat rooms using unique 8-character hex IDs.
* **Integrated AI Models**: Switch between various LLMs, including DeepSeek V3.1, GPT-OSS, Kimi-K2, and Qwen3, managed via an Ollama integration.
* **Context-Aware AI**: The platform uses a relevance filtering mechanism to provide the AI with the most pertinent conversation history, ensuring more accurate and focused responses.
* **Modern React UI**: A responsive interface featuring dynamic avatar layouts for groups, dark mode support, and real-time message updates.
* **Rich Content Support**: Includes Markdown rendering and mathematical typesetting via MathJax for technical discussions.
* **Flexible Database Support**: Uses SQLite for local development and is pre-configured for PostgreSQL in production environments like Railway.

## Tech Stack

* **Backend**: Flask
* **Frontend**: React (Prebuilt and served via Flask)
* **AI Orchestration**: Ollama
* **Database**: SQLite or PostgreSQL (via `psycopg2`)
* **Deployment**: Ready for Railway with automatic database migrations

## Setup and Installation

### Prerequisites

* Python 3.9+
* An active Ollama instance with an API key

### Local Development

1.  **Clone the repository and enter the directory.**
2.  **Create and activate a virtual environment**:
    ```powershell
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    ```
3.  **Install dependencies**:
    ```powershell
    pip install -r requirements.txt
    ```
4.  **Configure environment variables**:
    * `OLLAMA_API_KEY`: Your Ollama authorization token.
    * `SECRET_KEY`: A secure key for Flask sessions.
5.  **Run the application**:
    ```powershell
    python app.py
    ```
    The server will start at `http://127.0.0.1:8080` by default.

## Usage

* **Group Management**: Use the "New Chat" button to create a room with a password or join an existing one using an ID provided by a peer.
* **AI Interaction**: Type `/AI` followed by your prompt to receive a response from the currently active model.
* **Model Selection**: Long-press or hover over the AI robot icon in the chat composer to switch between available models.

## Database Management

SQL queries are managed centrally in `sql/main.sql` (SQLite) and `sql/postgres.sql` (PostgreSQL). The application automatically detects the database type and applies necessary table schemas and migrations on startup.

## Deployment

This app is optimized for Railway. By adding a PostgreSQL database to your Railway project, the app will automatically detect the `DATABASE_URL` environment variable and switch to production mode.

### Railway Environment Variables

Set these in your Railway dashboard:

| Variable | Description | Value / Default |
| :--- | :--- | :--- |
| `DATABASE_URL` | Connection string for PostgreSQL | *Automatically provided by Railway* |
| `SECRET_KEY` | Flask session key | *Your custom secret string* |
| `SESSION_COOKIE_SECURE` | Enforce HTTPS cookies | `True` |
| `PORT` | Application port | `8080` |

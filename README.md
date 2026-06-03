# GitLab AI Review

**English** | [简体中文](./README_zh-CN.md)

> AI-powered code review for GitLab Merge Requests

GitLab AI Review analyzes MR code changes using AI (OpenAI / Ollama) and generates intelligent review comments. It ships as a web app (FastAPI + React) or a desktop app (PyQt6).

## Features

- Browse GitLab projects and MR lists
- Diff viewer with syntax highlighting
- AI-driven code review with customizable rules
- Post comments, approve/unapprove MRs directly
- SQLite cache for faster access
- Multi-user support with JWT authentication
- Docker deployment ready

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+ / FastAPI / Uvicorn |
| Frontend | React 19 / TypeScript / Ant Design / Vite |
| Desktop | PyQt6 |
| Database | SQLite |
| AI | OpenAI API / Ollama (local models) |

## Quick Start

### 1. Clone

```bash
git clone https://github.com/tonymaa/ai-review-gitlab-mr.git
cd ai-review-gitlab-mr
```

### 2. Backend

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Frontend

```bash
cd web
npm install
```

### 4. Configure

Copy `.env.example` to `.env` and fill in your credentials:

```env
GITLAB_URL=https://gitlab.example.com
GITLAB_TOKEN=glpat-your_token_here

# Pick one AI provider
OPENAI_API_KEY=sk-your_key_here
# OLLAMA_BASE_URL=http://localhost:11434
```

Or use `config.example.yaml` for more detailed settings (AI rules, auto-refresh, UI layout).

### 5. GitLab Token

Create a token at **Settings → Access Tokens** with scopes: `api`, `read_api`, `read_repository`.

## Running

### Web App (recommended)

```bash
# Development (auto-reload)
python server.py --reload

# Production
python server.py --host 0.0.0.0 --port 19000
```

Backend serves at `http://127.0.0.1:19000`. For development, run the frontend separately:

```bash
cd web && npm run dev    # http://localhost:5173 (proxies API)
```

For production, build the frontend and let FastAPI serve the static files:

```bash
cd web && npm run build
cd .. && python server.py --host 0.0.0.0 --port 19000
```

### Desktop App

```bash
python main.py
```

### Docker

```bash
cp .env.example .env   # edit with your credentials
docker-compose up -d
```

Access at `http://localhost:19000`. Data is persisted under `./data`, `./cache`, and `./logs`.

## API Reference

Interactive docs available at `http://127.0.0.1:19000/docs` when the server is running.

| Group | Endpoints |
|-------|-----------|
| Auth `/api/auth` | `POST /register`, `POST /login`, `POST /logout`, `GET /me` |
| GitLab `/api/gitlab` | `POST /connect`, `GET /projects`, `GET /projects/{id}/merge-requests`, `GET /merge-requests/{iid}/diff`, `GET/POST/DELETE .../notes`, `POST .../approve`, `POST .../unapprove` |
| AI Review `/api/ai` | `POST /review`, `GET /review/{task_id}`, `POST /review/file` |
| Config `/api/config` | `GET /config`, `POST /config` |
| Health | `GET /api/health` |

## Project Structure

```
ai-review-gitlab-mr/
├── server.py              # Web server entry point
├── main.py                # Desktop app entry point
├── config.example.yaml    # Config template
├── .env.example           # Environment variable template
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
│
├── server/                # FastAPI backend
│   ├── main.py           # App factory & startup
│   ├── api/              # Route handlers (auth, config, gitlab, ai, health)
│   └── models/           # Data models (session)
│
├── src/                   # Core logic
│   ├── core/             # Config, database, auth, exceptions
│   ├── gitlab/           # GitLab API client & models
│   ├── ai/               # Reviewer & prompt templates
│   └── ui/               # PyQt6 desktop UI
│
├── web/                   # React frontend
│   ├── src/
│   │   ├── api/          # API client
│   │   ├── components/   # Layout, DiffViewer, MRList, CommentPanel
│   │   ├── contexts/     # App context
│   │   └── types/        # TypeScript types
│   └── vite.config.ts
│
├── data/                  # SQLite database
├── cache/                 # Response cache
└── logs/                  # Application logs
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GITLAB_URL` | GitLab server URL | `https://gitlab.example.com` |
| `GITLAB_TOKEN` | Personal Access Token | `glpat-xxxxxxxxxxxx` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-xxxxxxxxxxxx` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama model name | `codellama` |
| `ALLOW_REGISTRATION` | Enable user registration | `true` |

## Architecture

```
Browser → React (Vite :5173) → FastAPI (:19000) → GitLab API
                                              → OpenAI / Ollama
                                              → SQLite
```

## Development

```bash
# Backend
python server.py --reload    # auto-reload
pytest                       # tests
black src/ server/           # format
isort src/ server/           # sort imports

# Frontend
cd web
npm run dev                  # dev server
npm run build                # production build
npm run lint                 # lint
```

## License

MIT

# JaliMind Backend

Django 6 + Django REST Framework + Channels API for JaliMind, the guidance and counselling platform for African university students. See the [root README](../README.md) for the product overview.

## Contents

- [Stack](#stack) · [Structure](#structure) · [Setup](#setup) · [Environment](#environment)
- [API](#api) · [Real-time](#real-time) · [Anonymous chat](#anonymous-chat) · [JaliBot](#jalibot)
- [Tests](#tests) · [Roles](#roles)

## Stack

| Layer | Technology |
|---|---|
| Framework | Django 6, Django REST Framework |
| Auth | JWT (`djangorestframework-simplejwt`) + Google sign-in (ID token) |
| Real-time | Django Channels + Daphne (ASGI); Redis layer in production |
| AI | Gemini (`google-genai`), OpenAI, Anthropic Claude (see [JaliBot](#jalibot)) |
| Database | PostgreSQL in production, SQLite in development and tests |
| Config | `python-decouple` |

## Structure

```
backend/
├── core/                 settings (base/development/production/testing), urls, asgi, routing
├── apps/
│   ├── users/            custom user, JWT, Google login
│   ├── counselors/       profiles, availability, bookable times, counsellor dashboard, seed_demo
│   ├── sessions/         appointments (label: booking_sessions), reviews, call consumer
│   ├── shadow_chat/      anonymous chat, counsellor queue, AI cover (no FK to users)
│   ├── jalibot/          conversations, memories
│   ├── assessments/      check-in instruments and results
│   ├── library/          resources      ├── circle/  peer forum   └── referrals/  campus help
├── api/
│   ├── permissions.py    role classes
│   ├── admin_*.py        admin endpoints
│   └── services/         jalibot_service.py (provider chain), claude_provider.py
└── tests/                51 tests: auth, shadow, jalibot, new features
```

## Setup

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate     # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate --settings=core.settings.development
python manage.py seed_demo --settings=core.settings.development   # optional demo counsellors
python manage.py runserver --settings=core.settings.development
```

Served at `http://localhost:8000` (admin at `/admin/`). Restart after code changes; if the autoreloader crashes, use `runserver --noreload`. With no database settings, development uses SQLite (`db.sqlite3`).

## Environment

Copy `.env.example`. The important variables:

| Variable | Purpose |
|---|---|
| `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` | Django |
| `GEMINI_API_KEY`, `GEMINI_MODEL` (default `gemini-2.5-flash`) | First AI provider |
| `OPENAI_API_KEY`, `OPENAI_MODEL` (default `gpt-4o-mini`) | Second provider |
| `ANTHROPIC_API_KEY` or `CLAUDE_API_KEY`, `CLAUDE_MODEL` (default `claude-sonnet-5-5`) | Third provider |
| `JALIBOT_RATE_LIMIT` (30), `JALIBOT_MAX_OUTPUT_TOKENS` (160) | JaliBot limits |
| `SHADOW_SESSION_TTL_HOURS` (24), `SHADOW_AI_FALLBACK_SECONDS` (45) | Anonymous chat |
| `GOOGLE_CLIENT_ID` | Google sign-in (public web client ID only) |
| `CORS_ALLOWED_ORIGINS`, `FRONTEND_URL`, `WHATSAPP_NUMBER` | Frontend integration |
| `REDIS_URL`, `CALL_TURN_URL/USERNAME/CREDENTIAL` | Production live chat and calls behind strict networks |
| `DB_*`, `EMAIL_*` | Production database and email |

At least one AI key is needed for JaliBot. Never commit `.env`.

## API

All routes are under `/api/`.

| Area | Routes |
|---|---|
| Auth `/auth/` | `register/`, `login/`, `refresh/`, `logout/`, `google/`, `me/` |
| JaliBot `/jalibot/` | `POST chat/`, `GET history/`, `GET/DELETE history/{id}/`, `memories/`, `memories/{id}/` |
| Anonymous chat `/shadow/` | `POST start/`, `GET/DELETE session/{id}/`, `POST session/{id}/message/`, counsellor: `GET queue/`, `POST queue/{id}/claim/`, `counselor/{id}/` |
| Counsellors `/counselors/` | directory and detail, `{id}/times/`, `me/`, `me/availability/`, `dashboard/`, `students/` |
| Appointments `/appointments/` | list, detail, status updates (role-scoped) |
| Check-ins `/assessments/` | instruments, `{key}/submit/`, `results/`, `results/{id}/share/`, `shared/` |
| Library, Circle, Referrals | `/library/`, `/circle/{categories,threads}/`, `/referrals/`, `/referrals/resources/`, `/referrals/whatsapp/` |
| Admin `/admin/` | reports, users, audit logs |

`POST /api/jalibot/chat/` takes `{message, conversation_id?}` and returns `{reply, crisis_detected, conversation_id}`. Replies may contain Markdown.

## Real-time

WebSockets (`core/routing.py`):

- `ws/shadow/<session_id>/`: anonymous chat events (messages, crisis, closed)
- `ws/call/<appointment_id>/`: WebRTC signalling for 1:1 calls

Production needs Redis (`REDIS_URL`) so chat and calls work across processes, and a TURN server for calls from restrictive networks.

## Anonymous chat

- `AnonymousSession` has **no foreign key to any user**. A random token is returned once; only its SHA-256 hash is stored and compared in constant time.
- Students get a random nickname, topics, and a "need help now" priority lane. Sessions expire (24h by default) and can be wiped by the student.
- Counsellors see a queue and claim a chat. The chat then belongs to them.
- **AI cover:** if a chat is flagged critical (or topic is urgent), nobody has claimed it, and either no counsellor is available or 45s have passed, JaliBot replies as "JaliBot (AI)", points to the helplines at the top of the chat, and stops the moment a counsellor claims it. It is stateless: it reads the transcript only. If every provider fails, a static safe message is sent.
- Crisis keywords (several languages and phrasings) flag the chat for counsellors.

## JaliBot

`api/services/jalibot_service.py` calls providers through one `_complete()` chain: **Gemini → OpenAI → Claude**, moving on after any error (quota, outage, missing key). Any single key is enough.

- Short, practical replies; light Markdown (bold, short numbered lists); says it is an AI once, in the first reply.
- Multilingual (English, Swahili, French, Hausa, Igbo, Twi).
- Crisis handling: keyword list plus a model-side flag (`[[CRISIS]]` marker, stripped before display). The reply refers to the helplines the app pins; the model never types phone numbers. Crisis replies get extra token room so nothing is cut off.
- Persistent conversations (`history/`), deletable by their owner, plus long-term "memories" with extraction.
- Per-user rate limit (`JALIBOT_RATE_LIMIT`).

The pinned helpline list lives in `apps/shadow_chat/services.py`. Verify the numbers before launch.

## Tests

```bash
pytest -q        # 51 tests, SQLite in memory, AI calls faked
```

## Roles

| Role | Access |
|---|---|
| `student` | JaliBot, anonymous chat, booking, check-ins, library, Circle |
| `counselor` | Dashboard, queue and claim, schedule and availability, students, sessions, library write |
| `admin` / `superadmin` | Everything above plus users, audit logs, reports |

Permission classes are in `api/permissions.py`.

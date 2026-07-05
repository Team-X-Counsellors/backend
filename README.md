# JaliMind Backend

Django 6 + Django REST Framework API powering the JaliMind guidance and counselling platform for African university students.

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Environment Variables](#environment-variables)
- [Database Setup](#database-setup)
- [Running the Server](#running-the-server)
- [API Reference](#api-reference)
- [Authentication](#authentication)
- [Shadow Chat — Privacy Architecture](#shadow-chat--privacy-architecture)
- [JaliBot — Gemini Integration](#jalibot--gemini-integration)
- [Running Tests](#running-tests)
- [Role-Based Access Control](#role-based-access-control)

---

## Overview

JaliMind is an AI-powered mental health and guidance platform built specifically for university students across Africa. The backend provides:

- JWT-authenticated REST API with role-based access control
- JaliBot: Gemini-powered AI counselling companion (multilingual, crisis detection)
- Shadow Chat: cryptographically anonymous sessions — unlinkable to any user identity
- Appointment booking system with counsellor profiles
- Jali Library: curated mental health resources
- JaliMind Circle: peer support forum
- Audit logging and admin reporting

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 6.0.6 + Django REST Framework |
| Auth | JWT via `djangorestframework-simplejwt` |
| Database | PostgreSQL (Neon cloud) via `psycopg` (psycopg3) |
| AI | Google Gemini via `google-genai` SDK |
| Async | Celery + Redis (background tasks) |
| WebSocket | Django Channels + Daphne (ASGI) |
| CORS | `django-cors-headers` |
| Config | `python-decouple` |

---

## Project Structure

```
backend/
├── core/
│   ├── settings/
│   │   ├── base.py          # Shared settings
│   │   ├── development.py   # Dev: Neon PostgreSQL or SQLite fallback
│   │   ├── production.py    # Prod: PostgreSQL + HTTPS security headers
│   │   └── testing.py       # Tests: SQLite in-memory (fast, isolated)
│   ├── urls.py              # Root URL routing
│   ├── asgi.py              # ASGI entry point (Channels)
│   ├── wsgi.py              # WSGI entry point
│   └── celery.py            # Celery app
│
├── apps/
│   ├── users/               # CustomUser model, JWT auth, registration
│   ├── counselors/          # CounselorProfile, availability slots
│   ├── sessions/            # Appointment booking + reviews (label: booking_sessions)
│   ├── shadow_chat/         # Anonymous sessions — NO FK to users table
│   ├── jalibot/             # JalibotConversation, Gemini chat history
│   ├── library/             # Resource model (articles, videos, workbooks)
│   └── circle/              # ForumCategory, ForumThread, ForumReply, AuditLog
│
├── api/
│   ├── permissions.py       # RBAC permission classes
│   ├── admin_urls.py        # Admin-only endpoints
│   └── services/
│       └── jalibot_service.py  # Gemini API integration + crisis detection
│
├── tests/
│   ├── conftest.py          # Shared fixtures (student, counselor, admin users)
│   ├── test_auth/           # Registration, login, role enforcement
│   ├── test_shadow/         # Privacy guarantee tests (no FK to users)
│   └── test_jalibot/        # Gemini mock tests, crisis detection, rate limits
│
├── manage.py
├── requirements.txt
├── pytest.ini
└── .env                     # Never commit this file
```

---

## Prerequisites

- Python 3.11+
- Git
- A Gemini API key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- PostgreSQL database (the project uses [Neon](https://neon.tech) — free serverless Postgres)
- Redis (optional in development — only needed for Celery background tasks)

---

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd jalimind/backend
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create your environment file

```bash
cp .env.example .env
```

Then fill in the values — see [Environment Variables](#environment-variables) below.

### 5. Apply database migrations

```bash
python manage.py migrate --settings=core.settings.development
```

### 6. Create a superuser (optional)

```bash
python manage.py createsuperuser --settings=core.settings.development
```

---

## Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# Django
SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# Gemini AI
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash

# Database — Neon PostgreSQL connection string
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require

# Redis (Celery + Django Channels)
REDIS_URL=redis://localhost:6379/0

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000

# Shadow Chat session lifetime
SHADOW_SESSION_TTL_HOURS=24

# JaliBot messages per user per hour
JALIBOT_RATE_LIMIT=30
```

**If `DATABASE_URL` is not set**, the development settings fall back to a local SQLite database (`db.sqlite3`).

---

## Database Setup

The project targets **PostgreSQL** (Neon) in all environments except tests.

### Neon (recommended)

1. Create a free project at [neon.tech](https://neon.tech)
2. Copy the connection string from the Neon dashboard
3. Paste it as `DATABASE_URL` in your `.env`

### SQLite fallback (quick local dev)

Remove or leave `DATABASE_URL` blank — the server will use `db.sqlite3` automatically.

### Migrations

```bash
# Run all migrations
python manage.py migrate --settings=core.settings.development

# Generate migrations after model changes
python manage.py makemigrations --settings=core.settings.development

# Note: the sessions app uses label 'booking_sessions' (avoids conflict with Django's built-in sessions)
python manage.py makemigrations booking_sessions --settings=core.settings.development
```

---

## Running the Server

```bash
python manage.py runserver --settings=core.settings.development
```

The API will be available at `http://localhost:8000`.

Django Admin: `http://localhost:8000/admin/`

---

## API Reference

All endpoints are prefixed with `/api/`.

### Authentication — `/api/auth/`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register/` | None | Register new user (returns JWT) |
| POST | `/api/auth/login/` | None | Login (returns access + refresh tokens) |
| POST | `/api/auth/refresh/` | None | Refresh access token |
| POST | `/api/auth/logout/` | JWT | Blacklist refresh token |
| GET | `/api/auth/me/` | JWT | Current user profile |
| PATCH | `/api/auth/me/` | JWT | Update profile |

### JaliBot — `/api/jalibot/`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/jalibot/chat/` | JWT or Anonymous | Send message, receive AI reply |
| GET | `/api/jalibot/history/` | JWT | Retrieve conversation history |

**Request body:**
```json
{
  "message": "I'm feeling overwhelmed with exams",
  "language": "en"
}
```

**Response:**
```json
{
  "reply": "I hear you...",
  "crisis_detected": false,
  "referred_to_counselor": false,
  "conversation_id": "uuid"
}
```

### Shadow Chat — `/api/shadow/`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/shadow/start/` | None | Start anonymous session |
| GET | `/api/shadow/session/{id}/` | X-Shadow-Token header | Get session details |
| DELETE | `/api/shadow/session/{id}/` | X-Shadow-Token header | End session |
| POST | `/api/shadow/session/{id}/message/` | X-Shadow-Token header | Send message |

**Start session response:**
```json
{
  "session_id": "uuid",
  "pseudonym": "BoldHarambee_7392",
  "token": "one-time-raw-token",
  "expires_at": "2026-07-06T12:00:00Z"
}
```

The raw token is returned **once only** and never stored. Include it in subsequent requests as `X-Shadow-Token: <token>`.

### Counselors — `/api/counselors/`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/counselors/` | JWT | List all counselors (filterable) |
| GET | `/api/counselors/{id}/` | JWT | Counselor detail |
| POST | `/api/counselors/{id}/book/` | JWT (Student) | Book appointment |

### Appointments — `/api/appointments/`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/appointments/` | JWT | List (role-scoped) |
| GET | `/api/appointments/{id}/` | JWT | Detail |
| PATCH | `/api/appointments/{id}/` | JWT | Update status |

### Library — `/api/library/`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/library/` | JWT | List resources (searchable, filterable) |
| POST | `/api/library/` | JWT (Counselor/Admin) | Upload resource |

### Circle Forum — `/api/circle/`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/circle/threads/` | JWT | List threads |
| POST | `/api/circle/threads/` | JWT | Create thread |
| GET | `/api/circle/threads/{id}/replies/` | JWT | List replies |
| POST | `/api/circle/threads/{id}/replies/` | JWT | Post reply |
| GET | `/api/circle/categories/` | JWT | List categories |

### Admin — `/api/admin/`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/admin/reports/utilization/` | Admin | Platform utilization report |
| GET | `/api/admin/users/` | Admin | All users |
| POST | `/api/admin/users/{id}/deactivate/` | Admin | Deactivate user |
| GET | `/api/admin/audit-logs/` | Admin | Audit log |

---

## Authentication

The API uses **JWT Bearer tokens**.

```http
Authorization: Bearer <access_token>
```

Tokens contain custom claims:
```json
{
  "user_id": 1,
  "role": "student",
  "university": "University of Nairobi",
  "full_name": "Amara Osei"
}
```

Access tokens expire after **1 hour**. Use the refresh endpoint to get a new one. Refresh tokens expire after **7 days** and are rotated + blacklisted on use.

---

## Shadow Chat — Privacy Architecture

Shadow Chat is the fully anonymous support channel. The privacy guarantee is enforced at the database level:

- `AnonymousSession` has **no ForeignKey to any user table** — this is a hard architectural constraint
- A one-time random token (`secrets.token_urlsafe(32)`) is generated at session start
- Only the **SHA-256 hash** of the token is stored — the raw token is returned to the client once and discarded
- Token verification uses `secrets.compare_digest()` to prevent timing attacks
- Sessions expire after 24 hours (configurable via `SHADOW_SESSION_TTL_HOURS`)
- Expired sessions are hard-deleted every 15 minutes via Celery Beat
- The `referred_counselor_id` field is a plain UUID with no FK constraint — preserving anonymity even when counsellor referrals occur

Pseudonyms are generated from African word lists (e.g. `BoldHarambee_7392`, `CalmBaobab_4851`).

---

## JaliBot — Gemini Integration

JaliBot uses the `google-genai` SDK (not the deprecated `google-generativeai`).

**Model:** `gemini-2.5-flash` (configurable via `GEMINI_MODEL`)

**Features:**
- Full conversation history sent with each request
- Multilingual: English, Swahili, French, Hausa, Igbo, Twi
- Crisis keyword detection in all supported languages — triggers counsellor referral
- Per-user rate limiting: 30 messages/hour (configurable via `JALIBOT_RATE_LIMIT`)
- Graceful 429 handling — returns a user-friendly message instead of a 500 error

**Crisis hotlines embedded in system prompt:**
- Kenya: Befrienders Kenya — +254 722 178 177
- Nigeria: SURPIN — +234 806 210 6493
- Ghana: Mental Health Authority — 0800 111 222
- South Africa: SADAG — 0800 456 789

---

## Running Tests

Tests use SQLite in-memory (not Neon) for speed and isolation.

```bash
# Run all tests
pytest tests/

# Run specific test categories
pytest tests/test_auth/        # RBAC and authentication
pytest tests/test_shadow/      # Privacy guarantee (no FK to users)
pytest tests/test_jalibot/     # Gemini mock tests

# Verbose output
pytest tests/ -v
```

Expected output: **28 tests passing in ~4 seconds**.

---

## Role-Based Access Control

| Role | Access |
|---|---|
| `student` | JaliBot, Shadow Chat, Library (read), Circle, book appointments |
| `counselor` | Library (write), view assigned appointments, respond in Shadow Chat |
| `admin` | All of the above + user management, audit logs, reports |
| `superadmin` | Full platform access |

Permission classes are in [`api/permissions.py`](api/permissions.py):
- `IsStudent`, `IsCounselor`, `IsAdmin`, `IsSuperAdmin`
- `IsCounselorOrAdmin` — combined check
- `IsAdminOrAuthor` — object-level: admin or the resource author
- `IsAnonymousSessionOwner` — validates `X-Shadow-Token` header

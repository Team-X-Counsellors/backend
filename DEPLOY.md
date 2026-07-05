# JaliMind Backend — Render Deployment Guide

Deploy the JaliMind Django API to [Render](https://render.com) using the free tier with a PostgreSQL database (Neon) and GitHub as the source.

---

## Prerequisites

- GitHub account with the backend repo pushed (you are reading this, so ✓)
- [Render account](https://render.com) — free tier is sufficient for MVP
- Neon PostgreSQL database (already configured in your `.env`)
- A new Gemini API key (production key, not the dev one)

---

## Step 1 — Prepare the Repository

These files must exist in your repo before deploying. They are already committed:

| File | Purpose |
|---|---|
| `requirements.txt` | Python dependencies |
| `core/settings/production.py` | Production Django settings |
| `manage.py` | Django entry point |

### Add a `build.sh` script

Create `backend/build.sh` — Render runs this on every deploy:

```bash
#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input --settings=core.settings.production
python manage.py migrate --settings=core.settings.production
```

Make it executable and commit:

```bash
chmod +x build.sh
git add build.sh
git commit -m "chore: add Render build script"
git push origin main
```

---

## Step 2 — Create a Web Service on Render

1. Go to [dashboard.render.com](https://dashboard.render.com) and click **New → Web Service**
2. Connect your GitHub account if not already connected
3. Select the repository: `Paulmwas/backend`
4. Configure the service:

| Setting | Value |
|---|---|
| **Name** | `jalimind-api` |
| **Region** | Oregon (US West) or Frankfurt (EU) — pick closest to your users |
| **Branch** | `main` |
| **Root Directory** | *(leave blank — repo root is the backend)* |
| **Runtime** | `Python 3` |
| **Build Command** | `./build.sh` |
| **Start Command** | `daphne -b 0.0.0.0 -p $PORT core.asgi:application` |
| **Plan** | Free (for MVP) |

5. Click **Create Web Service** — do not add environment variables yet, do that in Step 3.

---

## Step 3 — Set Environment Variables

In your Render service dashboard, go to **Environment** and add each variable:

| Key | Value | Notes |
|---|---|---|
| `SECRET_KEY` | Generate a strong random key | See tip below |
| `DEBUG` | `False` | Must be False in production |
| `ALLOWED_HOSTS` | `jalimind-api.onrender.com` | Your Render URL |
| `DJANGO_SETTINGS_MODULE` | `core.settings.production` | |
| `DATABASE_URL` | Your Neon connection string | From Neon dashboard |
| `GEMINI_API_KEY` | Your production Gemini key | From Google AI Studio |
| `GEMINI_MODEL` | `gemini-2.5-flash` | |
| `CORS_ALLOWED_ORIGINS` | `https://your-frontend.netlify.app` | Your Netlify URL |
| `SHADOW_SESSION_TTL_HOURS` | `24` | |
| `JALIBOT_RATE_LIMIT` | `30` | |
| `REDIS_URL` | *(optional — only if using Celery)* | Render has a Redis add-on |

**Generate a SECRET_KEY** — run this in your local terminal:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Copy the output and paste it as the `SECRET_KEY` value.

---

## Step 4 — Verify Production Settings

Check `core/settings/production.py` contains these settings:

```python
from .base import *
import dj_database_url

DEBUG = False
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())

DATABASES = {
    'default': dj_database_url.parse(
        config('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

If anything is missing, add it, commit, and push.

---

## Step 5 — Trigger Your First Deploy

Render auto-deploys when you push to `main`. Either:

```bash
# Make a small change and push
git commit --allow-empty -m "chore: trigger Render deploy"
git push origin main
```

Or in the Render dashboard click **Manual Deploy → Deploy latest commit**.

Watch the build logs in real time on the Render dashboard under **Logs**.

A successful build ends with:
```
==> Your service is live 🎉
```

---

## Step 6 — Verify the Deployment

Your API base URL will be:
```
https://jalimind-api.onrender.com
```

Test each endpoint:

```bash
# Health check — Django admin should redirect (302)
curl -I https://jalimind-api.onrender.com/admin/

# Register a user
curl -X POST https://jalimind-api.onrender.com/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "first_name": "Test",
    "last_name": "User",
    "password": "SecurePass123",
    "password_confirm": "SecurePass123",
    "consent_given": true
  }'

# Start an anonymous shadow session
curl -X POST https://jalimind-api.onrender.com/api/shadow/start/
```

---

## Step 7 — Update the Frontend

Once your API is live, update the frontend environment variable:

**On Netlify:** Site settings → Environment variables:
```
NEXT_PUBLIC_API_URL = https://jalimind-api.onrender.com
```

Trigger a Netlify redeploy after saving.

Also update `CORS_ALLOWED_ORIGINS` on Render to include your Netlify domain:
```
CORS_ALLOWED_ORIGINS=https://your-site.netlify.app
```

---

## Auto-Deploy on Push

By default Render watches the `main` branch and redeploys on every push. Your workflow becomes:

```bash
# Make changes locally, test, then:
git add .
git commit -m "feat: your change"
git push origin main
# → Render auto-deploys within 1-2 minutes
```

---

## Free Tier Limitations

Render's free web service **spins down after 15 minutes of inactivity**. The first request after inactivity takes ~30–60 seconds (cold start).

**To avoid cold starts**, either:
- Upgrade to a paid Render plan (Starter at $7/month keeps the service always-on)
- Use an external uptime monitor (e.g. [UptimeRobot](https://uptimerobot.com) — free) to ping `https://jalimind-api.onrender.com/admin/` every 10 minutes

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Build fails: `ModuleNotFoundError` | Check `requirements.txt` has all packages |
| `DISALLOWED_HOST` error | Add your Render URL to `ALLOWED_HOSTS` env var |
| Database connection error | Verify `DATABASE_URL` is correct in Render env vars |
| Static files 404 | Ensure `collectstatic` runs in `build.sh` and `whitenoise` is in `MIDDLEWARE` |
| CORS blocked from frontend | Add your Netlify URL to `CORS_ALLOWED_ORIGINS` |
| `daphne: command not found` | Ensure `daphne` is in `requirements.txt` |
| 500 on first request | Check Render logs — usually a missing env var |
| Gemini 429 errors | Your API key hit free-tier limits — check quota at [ai.dev/rate-limit](https://ai.dev/rate-limit) |

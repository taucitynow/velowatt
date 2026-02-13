# VeloWatt — Railway Deployment Guide

## Quick Start (15 minutes)

### 1. Create GitHub Repository

Push your code to GitHub with this structure:

```
velowatt/
├── backend/
│   ├── main.py          ← Web backend (new file)
│   ├── models.py         ← Updated with User model
│   ├── database.py       ← Updated for PostgreSQL
│   ├── auth.py           ← NEW: JWT authentication
│   ├── metrics.py        ← Same as desktop version
│   ├── fit_parser.py     ← Same as desktop version
├── requirements.txt      ← Updated with auth deps
├── Dockerfile            ← Docker build config
└── README.md
```

### 2. Create Railway Account

1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub
3. Click "New Project"

### 3. Add PostgreSQL Database

1. In your Railway project, click "Add Service"
2. Select **PostgreSQL**
3. Railway auto-creates the database — note the `DATABASE_URL` in variables

### 4. Deploy Backend

1. Click "Add Service" → "GitHub Repo"
2. Select your `velowatt` repository
3. Railway auto-detects the Dockerfile and builds

### 5. Set Environment Variables

In the backend service settings, add:

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (Railway reference) |
| `SECRET_KEY` | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ANTHROPIC_API_KEY` | `sk-ant-api03-...` (your key) |
| `STRAVA_CLIENT_ID` | Your Strava app client ID |
| `STRAVA_CLIENT_SECRET` | Your Strava app client secret |
| `ALLOWED_ORIGINS` | `https://velowatt.app,https://your-railway-url.up.railway.app` |
| `BASE_URL` | `https://your-railway-url.up.railway.app` |

### 6. Connect Custom Domain

1. In Railway service settings → "Settings" → "Networking"
2. Click "Generate Domain" (gives you a `.up.railway.app` URL)
3. Click "Custom Domain" → enter `velowatt.app`
4. Add the CNAME record at your domain registrar:
   - **Type:** CNAME
   - **Name:** @ (or velowatt.app)
   - **Value:** your-project.up.railway.app

Railway handles SSL automatically!

### 7. Update Strava OAuth

Go to [strava.com/settings/api](https://www.strava.com/settings/api):
- **Authorization Callback Domain:** `velowatt.app` (or your Railway URL)

---

## Architecture

```
User Browser (React SPA)
    ↓ HTTPS
velowatt.app (Railway)
    ↓
FastAPI Backend (Docker)
    ↓
PostgreSQL (Railway addon)
    ↓
Claude API (AI Coach + Analysis)
Strava API (Activity sync)
```

## Frontend Options

### Option A: Use the React JSX Artifact (Quickest)
The `VeloWatt_Web.jsx` file works as a Claude artifact preview.
Copy it to a React project to self-host, or use it inside claude.ai.

### Option B: Serve from FastAPI (Recommended for MVP)
Add a static HTML file that loads React from CDN:

1. Create `backend/static/index.html` with the React app
2. Add to `main.py`:
```python
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

### Option C: Separate Frontend (Best for Scale)
Deploy a Vite/React app separately on Vercel/Netlify, pointing API calls to the Railway backend.

---

## Cost Breakdown (Railway)

| Service | Free Tier | Pro ($5/mo) |
|---------|-----------|-------------|
| Backend | 500 hours/mo | Unlimited |
| PostgreSQL | 1GB storage | 5GB |
| Bandwidth | 100GB/mo | Unlimited |
| Custom domain | ✅ | ✅ |

**AI Coach costs:** ~$0.01 per message (Claude Sonnet)
**AI Analysis:** ~$0.002 per ride analysis

For beta testing with 10-50 users, **free tier is enough**.

---

## Migration from Desktop

Your existing desktop app continues to work locally.
The web version is a separate deployment with user accounts.

To import your existing 265 rides:
1. Register on the web app
2. Connect Strava → Sync (re-downloads from Strava)
3. Or: write a migration script to POST rides to `/api/rides`

---

## Environment Setup Checklist

- [ ] GitHub repo created with all files
- [ ] Railway account created
- [ ] PostgreSQL added to Railway project
- [ ] Backend service deployed from GitHub
- [ ] Environment variables set
- [ ] Domain pointed to Railway
- [ ] Strava callback domain updated
- [ ] First user registered
- [ ] Strava sync tested
- [ ] AI Coach tested

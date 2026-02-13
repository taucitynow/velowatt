# velowatt
velowatt app
####

<p align="center">
  <img src="https://img.shields.io/badge/⚡-VeloWatt-F59E0B?style=for-the-badge&labelColor=0f1117" alt="VeloWatt" />
</p>

<h1 align="center">VeloWatt</h1>
<p align="center"><strong>Power up your cycling.</strong></p>
<p align="center">AI-powered cycling performance analytics platform built for data-driven athletes.</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/Claude_AI-Sonnet-7C3AED?logo=anthropic&logoColor=white" />
</p>

---

## What is VeloWatt?

VeloWatt is a web-based training analytics platform for cyclists who train with power meters. Import your rides from Strava, get instant AI-powered coaching insights, and track your fitness progression with science-backed metrics.

**Think of it as:** TrainingPeaks + AI Coach — in one free platform.

### Key Features

🔋 **Power Metrics** — TSS, NP, IF, VI, EF calculated from second-by-second power data

📈 **Performance Management Chart** — CTL/ATL/TSB tracking with 30-day forecast

🤖 **AI Coach** — Claude-powered cycling coach that knows your fitness, recent rides, and power zones

✨ **Auto Ride Analysis** — Every imported ride gets a 2-3 sentence AI coaching insight

🔄 **Strava Sync** — One-click OAuth2 sync with power stream data for accurate NP

📊 **Power Zones** — 7-zone model auto-calculated from your FTP

🏋️ **FTP Management** — Set FTP, get estimates from ride data, recalculate all rides on change

👥 **Multi-User** — JWT authentication, each user gets their own data and Strava connection

---

## Screenshots

| Dashboard | AI Coach | Strava Sync |
|-----------|----------|-------------|
| PMC chart, fitness cards, AI analysis, recent rides | Chat with context-aware cycling coach | OAuth2 connect, bulk import with auto-analysis |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python, FastAPI, SQLModel |
| **Database** | PostgreSQL (prod) / SQLite (dev) |
| **Auth** | JWT + bcrypt |
| **Frontend** | React |
| **AI** | Claude API (Sonnet) |
| **Integrations** | Strava API, .FIT file parser |
| **Deploy** | Docker, Railway |

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (or use SQLite for local dev)
- [Anthropic API key](https://console.anthropic.com) (for AI features)
- [Strava API app](https://www.strava.com/settings/api) (for Strava sync)

### Local Development

```bash
# Clone
git clone https://github.com/yourusername/velowatt.git
cd velowatt

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your API keys

# Run
cd backend
uvicorn main:app --reload --port 8000
```

### Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# Database (optional — defaults to SQLite for local dev)
DATABASE_URL=sqlite:///velowatt.db

# Auth
SECRET_KEY=your-random-secret-key-here

# AI Coach (required for AI features)
ANTHROPIC_API_KEY=sk-ant-api03-...

# Strava (required for Strava sync)
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret

# Production
ALLOWED_ORIGINS=https://velowatt.app
BASE_URL=https://velowatt.app
```

### Deploy to Railway

1. Push this repo to GitHub
2. Create a [Railway](https://railway.app) project
3. Add a **PostgreSQL** service
4. Add a **GitHub Repo** service (this repo)
5. Set environment variables (see above)
6. Point your domain → Railway

Railway handles SSL, builds, and deploys automatically.

See [DEPLOY_GUIDE.md](DEPLOY_GUIDE.md) for detailed instructions.

---

## API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Get JWT token |
| GET | `/auth/me` | Current user info |

### Rides
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/rides` | Add a ride manually |
| GET | `/api/rides` | List rides (paginated) |
| GET | `/api/rides/{id}` | Get single ride |
| DELETE | `/api/rides/{id}` | Delete ride |
| POST | `/api/rides/{id}/analyze` | Generate AI analysis |
| POST | `/api/rides/analyze-latest` | Analyze most recent ride |

### Fitness & Zones
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/fitness` | CTL/ATL/TSB + PMC history |
| GET | `/api/zones` | Power zones based on FTP |
| GET | `/api/ftp-estimate` | Estimated FTP from ride data |

### Settings
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings` | Get user settings |
| PUT | `/api/settings` | Update FTP, weight, name |
| POST | `/api/recalculate` | Recalculate all rides with current FTP |

### Import & Sync
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/import/fit` | Upload .FIT file |
| GET | `/api/strava/status` | Check Strava connection |
| GET | `/api/strava/auth-url` | Get OAuth2 authorization URL |
| POST | `/api/strava/sync` | Sync rides from Strava |

### AI Coach
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/coach/chat` | Chat with AI cycling coach |

---

## How Metrics Work

### Normalized Power (NP)
30-second rolling average → raise to 4th power → average → 4th root. Accounts for power variability — a ride with big surges has higher NP than steady power at the same average.

### Training Stress Score (TSS)
`TSS = (duration × NP × IF) / (FTP × 3600) × 100`

Quantifies training load. 100 TSS ≈ riding at FTP for 1 hour.

### Intensity Factor (IF)
`IF = NP / FTP`

| IF | Zone |
|----|------|
| < 0.75 | Recovery / Endurance |
| 0.75–0.90 | Tempo |
| 0.90–1.05 | Threshold |
| 1.05–1.20 | VO2max |
| > 1.20 | Anaerobic |

### CTL / ATL / TSB
- **CTL (Fitness):** 42-day exponential moving average of daily TSS
- **ATL (Fatigue):** 7-day exponential moving average of daily TSS
- **TSB (Form):** CTL − ATL. Positive = fresh. Negative = fatigued.

---

## Project Structure

```
velowatt/
├── backend/
│   ├── main.py           # FastAPI app + all endpoints
│   ├── models.py          # SQLModel database models
│   ├── database.py        # PostgreSQL/SQLite connection
│   ├── auth.py            # JWT authentication
│   ├── metrics.py         # TSS/NP/IF/CTL calculations
│   └── fit_parser.py      # Garmin .FIT file parser
├── requirements.txt
├── Dockerfile
├── DEPLOY_GUIDE.md
└── README.md
```

---

## Roadmap

- [x] Core metrics engine (TSS, NP, IF, CTL/ATL/TSB)
- [x] .FIT file import with power stream parsing
- [x] Strava OAuth2 sync
- [x] AI ride analysis (auto after import)
- [x] AI Coach chat with training context
- [x] PMC chart with forecast
- [x] Multi-user auth (JWT)
- [x] PostgreSQL + Docker deployment
- [ ] Garmin Connect sync (web version)
- [ ] Ride detail view with power graph
- [ ] Power curve (peak efforts)
- [ ] Training plan generator
- [ ] Race peaking planner
- [ ] Mobile-responsive PWA
- [ ] Stripe payments (Free / Pro tiers)

---

## Part of the VeloCX Ecosystem

**VeloWatt** is the training platform of the VeloCX brand family:

- 🏁 **VeloCX** — cyclocross race series
- ⚡ **VeloWatt** — training analytics platform

*Power up with VeloWatt to race VeloCX.*

---

## License

MIT

---

<p align="center">
  <strong>⚡ VeloWatt</strong> — Built by cyclists, for cyclists.
</p>

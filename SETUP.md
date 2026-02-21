# Quick Setup Guide

Get Legislative AI Assist running locally in 5 minutes.

## Prerequisites

- Python 3.11+
- Node.js 18+
- Git

## Step 1: Clone & Setup

```bash
git clone https://github.com/your-org/legislative-ai-assist.git
cd legislative-ai-assist
```

## Step 2: Environment Variables

```bash
# Copy environment template
cp env.example .env

# Edit .env and add your API keys
nano .env
```

Required keys:
- `OPENAI_API_KEY` - Get from https://platform.openai.com/api-keys
- `ANTHROPIC_API_KEY` - Get from https://console.anthropic.com/settings/keys
- `GOOGLE_API_KEY` - Get from https://makersuite.google.com/app/apikey
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_KEY` - Your Supabase anon/public key

## Step 3: Backend Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run backend
uvicorn main:app --reload --port 8000
```

Backend available at: http://localhost:8000

API Docs: http://localhost:8000/docs

## Step 4: Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Run frontend
npm run dev
```

Frontend available at: http://localhost:3000

## Step 5: Verify

Open http://localhost:3000 in your browser and try asking a question!

Example questions:
- **SK**: "Aké su hlavné zásady ochrany hospodárskej súťaže?"
- **HU**: "Mi a kartelltilalom lényege az EU versenyjogban?"
- **EN**: "What is the difference between TFEU Article 101 and 102?"

## Troubleshooting

**Backend fails to start:**
- Check if all environment variables are set in `.env`
- Verify Python version: `python --version` (should be 3.11+)
- Check if port 8000 is available

**Frontend can't connect to backend:**
- Ensure backend is running on port 8000
- Check browser console for CORS errors
- Verify `API_BASE_URL` in `frontend/app.js`

**Database errors:**
- Verify Supabase credentials in `.env`
- Check if Supabase project is active
- Run database schema: see `scripts/supabase_schema.sql`

## Next Steps

- **Full Deployment**: See [DEPLOYMENT.md](DEPLOYMENT.md)
- **Development Guide**: See [README.md](README.md)
- **Contributing**: See [CONTRIBUTING.md](CONTRIBUTING.md)

## Need Help?

Create an issue on GitHub or check the documentation.





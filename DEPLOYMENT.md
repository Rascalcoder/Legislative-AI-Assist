# Deployment Guide - Legislative AI Assist

Comprehensive deployment guide for Legislative AI Assist (Competition Law AI Assistant).

## Table of Contents
- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Local Development](#local-development)
- [Production Deployment](#production-deployment)
- [Post-Deployment](#post-deployment)

---

## Prerequisites

### Required Accounts & API Keys

1. **LLM Providers**
   - [OpenAI API Key](https://platform.openai.com/api-keys) - GPT-4o mini
   - [Anthropic API Key](https://console.anthropic.com/settings/keys) - Claude Sonnet 4.5
   - [Google AI API Key](https://makersuite.google.com/app/apikey) - Gemini Flash-Lite

2. **Database**
   - [Supabase Account](https://supabase.com) - PostgreSQL with pgvector + FTS

3. **Hosting**
   - **Backend**: [Google Cloud Run](https://cloud.google.com/run) or similar
   - **Frontend**: [Vercel](https://vercel.com) or [Netlify](https://netlify.com)

4. **Version Control**
   - GitHub account for CI/CD

---

## Environment Setup

### 1. Clone & Setup

```bash
# Clone repository
git clone https://github.com/your-org/legislative-ai-assist.git
cd legislative-ai-assist

# Copy environment template
cp env.example .env

# Edit .env with your actual keys
nano .env  # or use your preferred editor
```

### 2. Supabase Database Setup

#### Create Supabase Project
1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Create new project
3. Wait for database provisioning
4. Copy `Project URL` and `anon/public` key to `.env`

#### Run Database Schema

```bash
# Connect to Supabase SQL Editor and run:
cat scripts/supabase_schema.sql
```

Or via CLI:
```bash
# Install Supabase CLI
npm install -g supabase

# Login
supabase login

# Link project
supabase link --project-ref your-project-ref

# Run migrations
supabase db push
```

The schema creates:
- `documents` table
- `chunks` table with vector embeddings
- Full-text search indexes
- RRF (Reciprocal Rank Fusion) functions

---

## Local Development

### Backend (FastAPI)

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run development server
uvicorn main:app --reload --port 8000

# Test API
curl http://localhost:8000/api/v1/health
```

**API Documentation**: http://localhost:8000/docs

### Frontend (Vite + Tailwind)

```bash
cd frontend

# Install Node dependencies
npm install

# Run development server
npm run dev

# Frontend will be available at http://localhost:3000
```

**Environment**: Frontend automatically proxies `/api` to `http://localhost:8000`

---

## Production Deployment

### Backend - Google Cloud Run

#### 1. Setup Google Cloud

```bash
# Install Google Cloud SDK
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Login
gcloud auth login

# Set project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

#### 2. Build & Deploy

```bash
# Build Docker image
docker build -t gcr.io/YOUR_PROJECT_ID/legislative-ai-assist:latest .

# Push to Google Container Registry
docker push gcr.io/YOUR_PROJECT_ID/legislative-ai-assist:latest

# Deploy to Cloud Run
gcloud run deploy legislative-ai-assist \
  --image gcr.io/YOUR_PROJECT_ID/legislative-ai-assist:latest \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --set-env-vars "OPENAI_API_KEY=$OPENAI_API_KEY,ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY,GOOGLE_API_KEY=$GOOGLE_API_KEY,SUPABASE_URL=$SUPABASE_URL,SUPABASE_KEY=$SUPABASE_KEY,ALLOWED_ORIGINS=https://yourdomain.com" \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --concurrency 80 \
  --max-instances 10
```

#### 3. Get Service URL

```bash
gcloud run services describe legislative-ai-assist \
  --region europe-west1 \
  --format 'value(status.url)'
```

Save this URL - you'll need it for frontend configuration!

---

### Frontend - Vercel Deployment

#### 1. Install Vercel CLI

```bash
npm install -g vercel
```

#### 2. Deploy

```bash
cd frontend

# Login to Vercel
vercel login

# Deploy (follow prompts)
vercel

# For production
vercel --prod
```

#### 3. Configure Environment Variables

In Vercel Dashboard:
1. Go to Project Settings → Environment Variables
2. Add:
   ```
   API_BASE_URL=https://your-cloudrun-url.run.app/api/v1
   ```

#### 4. Update CORS

Update your backend's `ALLOWED_ORIGINS` environment variable in Cloud Run:

```bash
gcloud run services update legislative-ai-assist \
  --update-env-vars "ALLOWED_ORIGINS=https://your-vercel-domain.vercel.app"
```

---

### Frontend - Netlify Deployment (Alternative)

#### 1. Install Netlify CLI

```bash
npm install -g netlify-cli
```

#### 2. Deploy

```bash
cd frontend

# Login
netlify login

# Initialize
netlify init

# Deploy
netlify deploy --prod
```

#### 3. Configure Environment

In Netlify Dashboard:
1. Site Settings → Build & Deploy → Environment Variables
2. Add `API_BASE_URL` with your Cloud Run URL

---

## GitHub Actions CI/CD

### 1. Setup GitHub Secrets

Go to your GitHub repository → Settings → Secrets and Variables → Actions

Add these secrets:

**For Backend (Cloud Run):**
```
GCP_PROJECT_ID=your-gcp-project-id
GCP_SA_KEY=<service-account-json-key>
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
SUPABASE_URL=https://...
SUPABASE_KEY=eyJ...
ALLOWED_ORIGINS=https://yourdomain.com
```

**For Frontend (Vercel):**
```
VERCEL_TOKEN=<your-vercel-token>
VERCEL_ORG_ID=<your-org-id>
VERCEL_PROJECT_ID=<your-project-id>
```

### 2. Workflows

Three workflows are configured:

1. **CI** (`.github/workflows/ci.yml`) - Runs on every push/PR
   - Backend: Tests, linting, type checking
   - Frontend: Build validation
   - Security: Trivy vulnerability scan

2. **Deploy Backend** (`.github/workflows/deploy-backend.yml`)
   - Triggers on push to `main` or manual dispatch
   - Builds Docker image
   - Deploys to Cloud Run

3. **Deploy Frontend** (`.github/workflows/deploy-frontend.yml`)
   - Triggers on frontend changes to `main`
   - Builds and deploys to Vercel

---

## Post-Deployment

### 1. Update SEO Files

Edit these files in `frontend/`:
- `robots.txt` - Update sitemap URL
- `sitemap.xml` - Update domain
- `index.html` - Update Open Graph URLs and images

### 2. Custom Domain Setup

#### Vercel Custom Domain
1. Vercel Dashboard → Your Project → Settings → Domains
2. Add your domain
3. Configure DNS (follow Vercel instructions)

#### Cloud Run Custom Domain
```bash
gcloud run domain-mappings create \
  --service legislative-ai-assist \
  --domain api.yourdomain.com \
  --region europe-west1
```

### 3. SSL Certificates

Both Vercel and Cloud Run provide automatic SSL certificates.

### 4. Monitoring

#### Backend Logs (Cloud Run)
```bash
gcloud run services logs read legislative-ai-assist \
  --region europe-west1 \
  --limit 50
```

#### Vercel Logs
Check Vercel Dashboard → Deployments → View Function Logs

### 5. Analytics Setup

Add to `frontend/index.html`:

```html
<!-- Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

---

## Troubleshooting

### Backend Issues

**500 Internal Server Error**
- Check Cloud Run logs
- Verify environment variables are set
- Check Supabase connection

**CORS Errors**
- Ensure `ALLOWED_ORIGINS` includes your frontend domain
- Check browser console for exact origin

**Slow Response**
- Increase Cloud Run memory/CPU
- Check LLM API rate limits
- Monitor Supabase query performance

### Frontend Issues

**API Connection Failed**
- Verify `API_BASE_URL` environment variable
- Check Cloud Run service is running
- Verify CORS settings

**Build Fails**
- Clear node_modules: `rm -rf node_modules && npm install`
- Check Node version (needs 18+)
- Verify all dependencies in package.json

---

## Cost Optimization

### Free Tier Limits

**Supabase Free Tier:**
- 500 MB database
- 1 GB file storage
- 2 GB bandwidth/month

**Cloud Run Free Tier:**
- 2M requests/month
- 360,000 GB-seconds/month
- 180,000 vCPU-seconds/month

**Vercel Free Tier:**
- Unlimited deployments
- 100 GB bandwidth/month

### Expected Costs (after free tier)

| Traffic | LLM Costs | Infrastructure | Total |
|---------|-----------|----------------|-------|
| 100 queries/month | $0.41 | $0 | **$0.41** |
| 1,000 queries/month | $4.19 | $0 | **$4.19** |
| 10,000 queries/month | $41.90 | ~$5 | **~$47** |

---

## Support & Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com
- **Supabase Docs**: https://supabase.com/docs
- **Cloud Run Docs**: https://cloud.google.com/run/docs
- **Vercel Docs**: https://vercel.com/docs

---

## Security Checklist

- [ ] All API keys stored in environment variables (not in code)
- [ ] `.env` added to `.gitignore`
- [ ] CORS restricted to specific domains in production
- [ ] HTTPS enabled on all domains
- [ ] Supabase Row Level Security (RLS) configured
- [ ] Rate limiting enabled (if high traffic expected)
- [ ] Regular dependency updates via Dependabot
- [ ] Security headers configured (already in vercel.json/netlify.toml)

---

**Last Updated**: February 15, 2026





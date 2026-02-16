# Legislative AI Assist

**Versenyjogi AI asszisztens - Szlovak (SK) es EU jogforrasokkal**

Serverless jogi asszisztens hibrid keresessel (vektor + BM25), tobb szintu LLM pipeline-nal es automatikus jurisdikcio cimkezessel [SK] / [EU].

## Architektura

```
Frontend (Vercel/Netlify)
  Tailwind CSS + vanilla JS
        |
        v
Google Cloud Run (FastAPI)
        |
   +---------+---------+
   |         |         |
   v         v         v
  F1        F2        F3
 Router   Retrieval  Generate
 (o4-mini)  (Supabase) + Verify
        |
   +----+----+
   |         |
   v         v
 Supabase   LLM APIs
 (pgvector  (OpenAI,
  + FTS)    Anthropic,
            Google)
```

## LLM Stack

| Szerep | Modell | Mikor |
|--------|--------|-------|
| **Light** | GPT-4o mini | Query-time, 90% |
| **Deep** | Claude Sonnet 4.5 | Komplex jogi elemzes, 10% |
| **Async** | Gemini Flash-Lite | Hatter dokumentum feldolgozas |

Kozvetlen API (nem OpenRouter) - 3 provider, 1 kozos `get_client(role)`.

## Pipeline (3 serverless function)

- **F1 (Router)**: Szabaly-alapu eloszures + LLM intent felismeres + query rewrite
- **F2 (Retrieval)**: Hybrid search - pgvector (szemantikus) + FTS (lexikalis) + RRF fusion
- **F3 (Generate+Verify)**: Valasz generalas + citation check + hallucinacio-fek

## Kereses

Hybrid search Supabase-ben:
- **Vektor**: pgvector (szemantikus hasonlosag)
- **Lexikalis**: PostgreSQL full-text search (pontos paragrafus talalat)
- **RRF**: Reciprocal Rank Fusion (eredmenyek osszevonasa)

## Konfiguracnio

Minden JSON-bol jon, semmi nem beegetve:
- `config/models.json` - LLM modellek, providerek
- `config/search.json` - keresesi parameterek
- `config/sources.json` - jogforrasok, URL-ek
- `config/prompts.json` - system promptok, szabalyok
- `.env` - csak API kulcsok

## Projekt Struktura

```
Legislative AI assist/
├── main.py                    # FastAPI alkalmazas
├── requirements.txt           # Python fuggosegek
├── Dockerfile                 # Docker image
├── env.example                # Kornyezeti valtozok pelda
├── README.md                  # Projekt leiras
├── SETUP.md                   # Gyors telepitesi utmutato
├── DEPLOYMENT.md              # Reszletes deployment guide
├── CONTRIBUTING.md            # Hozzajarulasi iranyelvek
│
├── config/
│   ├── __init__.py            # Config loader
│   ├── models.json            # LLM konfig
│   ├── search.json            # Keresesi parameterek
│   ├── sources.json           # Jogforrasok
│   └── prompts.json           # Promptok, szabalyok
│
├── api/
│   ├── models.py              # Pydantic request/response
│   └── routes/
│       ├── chat.py            # Chat endpoint
│       ├── documents.py       # Dokumentum kezeles
│       ├── search.py          # Hybrid search
│       └── health.py          # Health check
│
├── services/
│   ├── llm_client.py          # Multi-provider LLM (get_client)
│   ├── supabase_service.py    # Supabase muveletek
│   ├── language_service.py    # Nyelvfelismeres
│   ├── document_service.py    # Dokumentum feldolgozas
│   ├── search_service.py      # Kereses wrapper
│   └── chat_service.py        # Pipeline orchestrator
│
├── pipeline/
│   ├── router.py              # F1: Router (L0+L1)
│   ├── retrieval.py           # F2: Hybrid search (L2)
│   └── generate.py            # F3: Generate + Verify (L3-L5)
│
├── frontend/
│   ├── index.html             # Main HTML (SEO optimized)
│   ├── app.js                 # Frontend logika
│   ├── styles.css             # Tailwind + animaciok
│   ├── package.json           # Node dependencies
│   ├── vite.config.js         # Vite build konfig
│   ├── tailwind.config.js     # Tailwind testreszabas
│   ├── postcss.config.js      # PostCSS konfig
│   ├── robots.txt             # SEO robots
│   ├── sitemap.xml            # SEO sitemap
│   ├── favicon.svg            # Favicon
│   ├── site.webmanifest       # PWA manifest
│   └── README.md              # Frontend dokumentacio
│
├── scripts/
│   ├── supabase_schema.sql    # DB sema
│   └── seed_data.py           # Adat feltoltes (TODO)
│
├── .github/
│   └── workflows/
│       ├── ci.yml             # CI pipeline (test, lint)
│       ├── deploy-backend.yml # Backend deploy (Cloud Run)
│       └── deploy-frontend.yml # Frontend deploy (Vercel)
│
├── tests/                     # Unit es integration tesztek
│
├── vercel.json                # Vercel deployment konfig
└── netlify.toml               # Netlify deployment konfig
```

## Koltseg

| Forgalom | Infra | LLM | Osszesen |
|----------|-------|-----|----------|
| 100 kerdes/ho | $0 | $0.41 | **$0.41** |
| 1000 kerdes/ho | $0 | $4.19 | **$4.19** |
| 10000 kerdes/ho | $0 | $41.90 | **$41.90** |

Infra: Supabase free tier + Cloud Run free tier + Vercel free tier (orok, nem trial).

## Nyelvek

- Szlovak (sk), Magyar (hu), Angol (en)
- Automatikus nyelvfelismeres
- Valasz a kerdes nyelven

## Domain

Versenyjog (competition law) - SK tagallami + EU szint:
- Slov-Lex, PMU hatarozatok
- EUR-Lex, EU Commission donatesek
- Valaszban kotelezo [EU] / [SK] jeloles

## Gyors Start

```bash
# 1. Kornyezet setup
cp env.example .env
# Szerkeszd az .env fajlt API kulcsokkal

# 2. Backend inditasa
pip install -r requirements.txt
uvicorn main:app --reload

# 3. Frontend inditasa (uj terminal)
cd frontend
npm install
npm run dev
```

Reszletes telepites: [SETUP.md](SETUP.md)

Deployment utmutato: [DEPLOYMENT.md](DEPLOYMENT.md)

## SEO & Optimalizalas

✅ **SEO Ready:**
- Meta tag-ek (title, description, keywords)
- Open Graph (Facebook, LinkedIn)
- Twitter Cards
- Sitemap.xml + Robots.txt
- Canonical URLs
- Semantic HTML

✅ **Performance:**
- Vite build optimization
- Tailwind CSS purging
- Asset minification
- CDN ready
- Lazy loading

✅ **Security:**
- CORS konfiguralva
- Security headers
- HTTPS only (production)
- Environment variable isolation

## CI/CD Pipeline

GitHub Actions automatikusan:
- ✅ Tesztek futtatasa
- ✅ Linting es type checking
- ✅ Security scan (Trivy)
- ✅ Backend deploy (Cloud Run)
- ✅ Frontend deploy (Vercel)

Workflow fajlok: `.github/workflows/`

## Hozzajarulas

Erdekels a projekt? Nezd meg a [CONTRIBUTING.md](CONTRIBUTING.md) fajlt!

Jovunk minden hozzajarulas:
- 🐛 Bug fix-ek
- ✨ Uj funkciok
- 📚 Dokumentacio
- 🧪 Tesztek
- 🌍 Forditasok


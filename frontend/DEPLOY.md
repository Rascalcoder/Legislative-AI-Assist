# Vercel Deployment Guide

## Quick Start - 3 Steps

### Step 1: Get Vercel Token (2 minutes)

1. Open: https://vercel.com/signup
   - Try email/password signup (NOT GitHub OAuth)
   - Or use incognito mode if GitHub OAuth hangs
   
2. Once logged in, go to: https://vercel.com/account/tokens

3. Create Token:
   - Name: `Legislative AI CLI`
   - Scope: `Full Account`  
   - Expiration: `No Expiration`
   - Click **Create**
   
4. **Copy the token** (save it temporarily in notepad)

### Step 2: Deploy with CLI (5 minutes)

Open PowerShell and run:

```powershell
# 1. Install Vercel CLI (if not installed)
npm install -g vercel

# 2. Navigate to frontend folder
cd "C:\Users\User\Projekteim\Legislative AI assist\frontend"

# 3. Deploy (replace YOUR_TOKEN with actual token)
vercel --token YOUR_TOKEN

# Answer the prompts:
# ? Set up and deploy? Y
# ? Which scope? [Select your account]
# ? Link to existing project? N
# ? What's your project's name? legislative-ai-assist
# ? In which directory is your code located? ./ [press Enter]
# ? Want to override settings? N

# 4. Add environment variable
vercel env add VITE_API_BASE_URL production --token YOUR_TOKEN

# When prompted, paste this URL:
# https://legislative-ai-assist-787977781915.europe-central2.run.app/api/v1

# 5. Deploy to production
vercel --prod --token YOUR_TOKEN
```

**Done!** Vercel will give you a URL like: `https://legislative-ai-assist-xxx.vercel.app`

### Step 3: Update Backend CORS (1 minute)

Once you have the Vercel URL, update the backend:

**Option A - gcloud CLI:**
```bash
gcloud run services update legislative-ai-assist \
  --region europe-central2 \
  --update-env-vars "ALLOWED_ORIGINS=https://your-vercel-url.vercel.app"
```

**Option B - Cloud Console:**
1. Go to: https://console.cloud.google.com/run
2. Click: `legislative-ai-assist` service
3. Click: **Edit & Deploy New Revision**
4. Go to: **Variables & Secrets** tab
5. Add variable:
   - Name: `ALLOWED_ORIGINS`
   - Value: `https://your-vercel-url.vercel.app`
6. Click: **Deploy**

---

## Troubleshooting

### Token not working?
- Make sure you copied the full token
- Check token scope is "Full Account"
- Token starts with something like `vercel_xxx` or similar

### Build fails?
```powershell
# Try installing dependencies first
cd "C:\Users\User\Projekteim\Legislative AI assist\frontend"
npm install
npm run build

# If successful, try deploy again
vercel --prod --token YOUR_TOKEN
```

### CORS errors in browser?
- Open browser console (F12)
- If you see CORS error, backend ALLOWED_ORIGINS needs your Vercel URL
- Update as shown in Step 3 above

### Alternative: Email Login
If you can create a Vercel account with email/password successfully:
```powershell
vercel login --email your.email@example.com
# Check your email for verification link
# Then deploy without --token flag
vercel
```

---

## Backend URL

Already configured and running:
```
https://legislative-ai-assist-787977781915.europe-central2.run.app
```

Health check: https://legislative-ai-assist-787977781915.europe-central2.run.app/api/v1/health

---

## What Gets Deployed?

- ✅ Frontend UI (Tailwind CSS + Vanilla JS)
- ✅ Chat interface (3 views: Chat, Search, Documents)
- ✅ Multi-language support (SK, HU, EN)
- ✅ Optimized build (Vite minification)
- ✅ Security headers (CORS, XSS protection)
- ✅ SEO meta tags (Open Graph, Twitter Cards)

---

## After Successful Deploy

Test the frontend:
1. Open your Vercel URL
2. Try asking a question in Slovak, Hungarian, or English
3. Check if backend connection works
4. If CORS error → Update backend ALLOWED_ORIGINS

---

Last Updated: 2026-02-16


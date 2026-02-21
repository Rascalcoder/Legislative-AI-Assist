# Vercel Deploy Helper Script
# Usage: .\deploy.ps1 -Token "your_vercel_token_here"

param(
    [Parameter(Mandatory=$true)]
    [string]$Token
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Vercel Deploy - Legislative AI Assist" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if we're in the frontend directory
$currentDir = Get-Location
if (-not (Test-Path ".\package.json")) {
    Write-Host "Error: package.json not found!" -ForegroundColor Red
    Write-Host "Make sure you're in the frontend directory" -ForegroundColor Red
    Write-Host ""
    Write-Host "Run: cd 'C:\Users\User\Projekteim\Legislative AI assist\frontend'" -ForegroundColor Yellow
    exit 1
}

# Check if Vercel CLI is installed
Write-Host "[1/5] Checking Vercel CLI..." -ForegroundColor Yellow
$vercelInstalled = Get-Command vercel -ErrorAction SilentlyContinue
if (-not $vercelInstalled) {
    Write-Host "Vercel CLI not found. Installing..." -ForegroundColor Yellow
    npm install -g vercel
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Failed to install Vercel CLI" -ForegroundColor Red
        exit 1
    }
    Write-Host "✓ Vercel CLI installed" -ForegroundColor Green
} else {
    Write-Host "✓ Vercel CLI found" -ForegroundColor Green
}

# Test token
Write-Host ""
Write-Host "[2/5] Testing token..." -ForegroundColor Yellow
$env:VERCEL_TOKEN = $Token
$testResult = vercel whoami --token $Token 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Invalid token or authentication failed" -ForegroundColor Red
    Write-Host "Please check your token at: https://vercel.com/account/tokens" -ForegroundColor Yellow
    exit 1
}
Write-Host "✓ Token valid. Logged in as: $testResult" -ForegroundColor Green

# Initial deploy
Write-Host ""
Write-Host "[3/5] Deploying to Vercel..." -ForegroundColor Yellow
Write-Host "This will create a preview deployment first." -ForegroundColor Cyan
Write-Host ""

vercel --token $Token --yes

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Deploy failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✓ Preview deployment successful!" -ForegroundColor Green

# Add environment variable
Write-Host ""
Write-Host "[4/5] Setting environment variable..." -ForegroundColor Yellow
$backendUrl = "https://legislative-ai-assist-787977781915.europe-central2.run.app/api/v1"

# Check if env var already exists
$envCheck = vercel env ls production --token $Token 2>&1 | Select-String "VITE_API_BASE_URL"
if ($envCheck) {
    Write-Host "VITE_API_BASE_URL already exists. Skipping..." -ForegroundColor Yellow
} else {
    Write-Host "Adding VITE_API_BASE_URL=$backendUrl" -ForegroundColor Cyan
    echo $backendUrl | vercel env add VITE_API_BASE_URL production --token $Token
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Environment variable added" -ForegroundColor Green
    }
}

# Production deploy
Write-Host ""
Write-Host "[5/5] Deploying to production..." -ForegroundColor Yellow
vercel --prod --token $Token --yes

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Production deploy failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "✓ DEPLOYMENT SUCCESSFUL!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Get the production URL
Write-Host "Getting your production URL..." -ForegroundColor Cyan
$prodUrl = vercel ls --token $Token 2>&1 | Select-String "https://.*\.vercel\.app" | Select-Object -First 1
if ($prodUrl) {
    Write-Host ""
    Write-Host "Your frontend is live at:" -ForegroundColor Green
    Write-Host "$prodUrl" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "IMPORTANT: Update backend CORS" -ForegroundColor Yellow
    Write-Host "Run this command to allow your Vercel domain:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "gcloud run services update legislative-ai-assist \" -ForegroundColor White
    Write-Host "  --region europe-central2 \" -ForegroundColor White
    Write-Host "  --update-env-vars `"ALLOWED_ORIGINS=$prodUrl`"" -ForegroundColor White
    Write-Host ""
}

Write-Host "Done! 🎉" -ForegroundColor Green


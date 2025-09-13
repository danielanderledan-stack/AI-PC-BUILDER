@echo off
REM Discord PC Build Bot - Google Cloud Deployment Script for Windows
REM Make sure you have gcloud CLI installed and authenticated

echo 🚀 Starting Discord PC Build Bot deployment to Google Cloud...

REM Check if gcloud is installed
gcloud version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ gcloud CLI is not installed. Please install it first:
    echo    https://cloud.google.com/sdk/docs/install
    pause
    exit /b 1
)

REM Check if user is authenticated
gcloud auth list --filter=status:ACTIVE --format="value(account)" >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ You are not authenticated with gcloud. Please run:
    echo    gcloud auth login
    pause
    exit /b 1
)

REM Set project ID (replace with your project ID)
set PROJECT_ID=your-project-id-here

REM Set app name
set APP_NAME=discord-pc-bot

echo 📋 Configuration:
echo    Project ID: %PROJECT_ID%
echo    App Name: %APP_NAME%

REM Set the project
echo 🔧 Setting project...
gcloud config set project %PROJECT_ID%

REM Enable required APIs
echo 🔌 Enabling required APIs...
gcloud services enable appengine.googleapis.com
gcloud services enable cloudbuild.googleapis.com

REM Check if required files exist
if not exist "app.yaml" (
    echo ❌ app.yaml not found. Please make sure you're in the correct directory.
    pause
    exit /b 1
)

if not exist "main.py" (
    echo ❌ main.py not found. Please make sure you're in the correct directory.
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo ❌ requirements.txt not found. Please make sure you're in the correct directory.
    pause
    exit /b 1
)

REM Deploy to App Engine
echo 🚀 Deploying to Google Cloud App Engine...
gcloud app deploy app.yaml --quiet

REM Get the service URL
echo 🌐 Getting service URL...
for /f "delims=" %%i in ('gcloud app browse --no-launch-browser') do set SERVICE_URL=%%i
echo ✅ Deployment complete!
echo    Service URL: %SERVICE_URL%
echo    Health check: %SERVICE_URL%/health

echo.
echo 📝 Next steps:
echo    1. Set your environment variables in the Google Cloud Console:
echo       - DISCORD_BOT_TOKEN
echo       - GEMINI_API_KEY
echo    2. Test the health endpoint: %SERVICE_URL%/health
echo    3. Check the logs: gcloud app logs tail -s default

echo.
echo 🔧 Useful commands:
echo    View logs: gcloud app logs tail -s default
echo    Stop app: gcloud app versions stop VERSION_ID
echo    Delete app: gcloud app services delete default

pause

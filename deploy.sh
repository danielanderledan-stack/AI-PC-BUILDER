#!/bin/bash

# Discord PC Build Bot - Google Cloud Deployment Script
# Make sure you have gcloud CLI installed and authenticated

set -e  # Exit on any error

echo "🚀 Starting Discord PC Build Bot deployment to Google Cloud..."

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI is not installed. Please install it first:"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ You are not authenticated with gcloud. Please run:"
    echo "   gcloud auth login"
    exit 1
fi

# Set project ID (replace with your project ID)
PROJECT_ID="your-project-id-here"

# Set app name
APP_NAME="discord-pc-bot"

echo "📋 Configuration:"
echo "   Project ID: $PROJECT_ID"
echo "   App Name: $APP_NAME"

# Set the project
echo "🔧 Setting project..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔌 Enabling required APIs..."
gcloud services enable appengine.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Check if app.yaml exists
if [ ! -f "app.yaml" ]; then
    echo "❌ app.yaml not found. Please make sure you're in the correct directory."
    exit 1
fi

# Check if main.py exists
if [ ! -f "main.py" ]; then
    echo "❌ main.py not found. Please make sure you're in the correct directory."
    exit 1
fi

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "❌ requirements.txt not found. Please make sure you're in the correct directory."
    exit 1
fi

# Deploy to App Engine
echo "🚀 Deploying to Google Cloud App Engine..."
gcloud app deploy app.yaml --quiet

# Get the service URL
echo "🌐 Getting service URL..."
SERVICE_URL=$(gcloud app browse --no-launch-browser)
echo "✅ Deployment complete!"
echo "   Service URL: $SERVICE_URL"
echo "   Health check: $SERVICE_URL/health"

echo ""
echo "📝 Next steps:"
echo "   1. Set your environment variables in the Google Cloud Console:"
echo "      - DISCORD_BOT_TOKEN"
echo "      - GEMINI_API_KEY"
echo "   2. Test the health endpoint: $SERVICE_URL/health"
echo "   3. Check the logs: gcloud app logs tail -s default"

echo ""
echo "🔧 Useful commands:"
echo "   View logs: gcloud app logs tail -s default"
echo "   Stop app: gcloud app versions stop VERSION_ID"
echo "   Delete app: gcloud app services delete default"

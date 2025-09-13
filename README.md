# Discord PC Build Bot - Google Cloud Deployment

An intelligent Discord bot that helps users build custom PCs using AI-powered recommendations. This bot provides conversational PC building assistance with natural language processing and real-time parts recommendations.

## Features

- 🤖 **AI-Powered Recommendations**: Uses Google's Gemini AI for intelligent PC build suggestions
- 💬 **Conversational Interface**: Natural language conversations to understand user needs
- 🎯 **Budget-Aware**: Respects user budgets and provides value-focused recommendations
- 🎨 **Aesthetic Preferences**: Considers color schemes, RGB preferences, and form factors
- 🔧 **Real-time Refinement**: Allows users to refine and adjust their builds
- 📊 **Session Management**: Tracks user preferences and build history
- 🏗️ **Cloud-Ready**: Designed for Google Cloud Platform deployment

## Prerequisites

Before deploying, make sure you have:

1. **Google Cloud Account** with billing enabled
2. **Discord Application** with bot token
3. **Google Gemini API Key**
4. **gcloud CLI** installed and authenticated

## Quick Start

### 1. Clone and Setup

```bash
# Download the bot files
# Navigate to the bot directory
cd "c:\\Sanctum Pc's\\Discord bot"

# Make deployment scripts executable (Linux/Mac)
chmod +x deploy.sh
```

### 2. Configure Environment Variables

Edit `app.yaml` and replace the placeholder values:

```yaml
env_variables:
  DISCORD_BOT_TOKEN: "YOUR_ACTUAL_DISCORD_BOT_TOKEN"
  GEMINI_API_KEY: "YOUR_ACTUAL_GEMINI_API_KEY"
```

### 3. Deploy to Google Cloud

**Option A: Using the deployment script (Recommended)**

```bash
# Edit deploy.sh and set your PROJECT_ID
# Then run:
./deploy.sh  # Linux/Mac
# OR
deploy.bat   # Windows
```

**Option B: Manual deployment**

```bash
# Set your project ID
gcloud config set project YOUR_PROJECT_ID

# Deploy the application
gcloud app deploy app.yaml
```

### 4. Set Environment Variables in Google Cloud

After deployment, set your environment variables in the Google Cloud Console:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to App Engine → Settings → Environment Variables
3. Add:
   - `DISCORD_BOT_TOKEN`: Your Discord bot token
   - `GEMINI_API_KEY`: Your Gemini API key

### 5. Test the Deployment

Visit your app's health endpoint:
```
https://YOUR_PROJECT_ID.appspot.com/health
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `!build` | Start a new PC build session |
| `!cancel` | Cancel current build session |
| `!status` | Check build session status |
| `!parts` | Show current build parts |
| `!restart` | Restart build session |
| `!health` | Check bot health |
| `!collective` | View collective build statistics |

## Project Structure

```
discord-pc-bot/
├── discord_pc_bot.py      # Main bot logic
├── main.py                # Cloud deployment entry point
├── app.yaml               # Google Cloud App Engine config
├── requirements.txt       # Python dependencies
├── deploy.sh/.bat         # Deployment scripts
├── config.yaml            # Bot configuration
├── .gcloudignore          # Files to ignore during deployment
├── env.example            # Environment variables template
└── README.md              # This file
```

## Configuration

### App Engine Settings (app.yaml)

- **Runtime**: Python 3.11
- **Scaling**: Automatic (1-10 instances)
- **Health Checks**: Enabled
- **Instance Class**: F2 (recommended for better performance)

### Bot Configuration (config.yaml)

Key settings include:
- Session timeout: 1 hour
- Max concurrent sessions: 100
- Rate limiting: 60 messages/minute
- Auto-save interval: 5 minutes

## Monitoring and Logs

### View Logs

```bash
# Stream logs in real-time
gcloud app logs tail -s default

# View recent logs
gcloud app logs read -s default --limit=50
```

### Health Monitoring

The bot includes health check endpoints:
- `/health` - Bot status and readiness
- `/` - Service information

### Google Cloud Console

Monitor your deployment in the Google Cloud Console:
- **App Engine**: Service overview and scaling
- **Logging**: Detailed application logs
- **Monitoring**: Performance metrics and alerts

## Troubleshooting

### Common Issues

**Bot not responding:**
1. Check if environment variables are set correctly
2. Verify Discord bot token is valid
3. Check logs for errors: `gcloud app logs tail -s default`

**High memory usage:**
1. Increase instance class in `app.yaml`
2. Check for memory leaks in session management
3. Monitor memory usage in Google Cloud Console

**API rate limits:**
1. Check Gemini API quota and limits
2. Implement rate limiting in bot code
3. Monitor API usage in Google Cloud Console

### Debug Mode

To enable debug logging, modify `app.yaml`:

```yaml
env_variables:
  LOG_LEVEL: "DEBUG"
```

## Scaling and Performance

### Automatic Scaling

The bot is configured for automatic scaling:
- **Min instances**: 1 (always running)
- **Max instances**: 10 (scales with demand)
- **Target CPU**: 65% utilization

### Performance Optimization

1. **Session Management**: Sessions auto-expire after 1 hour
2. **File Compression**: Session data is compressed for storage
3. **Rate Limiting**: Prevents abuse and maintains performance
4. **Health Checks**: Automatic restart of unhealthy instances

## Security

### Environment Variables

Never commit sensitive data to version control:
- Discord bot tokens
- API keys
- Database credentials

### Google Cloud Security

- Use IAM roles with minimal permissions
- Enable audit logging
- Regularly rotate API keys
- Monitor for suspicious activity

## Cost Optimization

### App Engine Pricing

- **F1**: $0.05/hour (basic)
- **F2**: $0.10/hour (recommended)
- **F4**: $0.20/hour (high performance)

### Cost Monitoring

1. Set up billing alerts in Google Cloud Console
2. Monitor usage in the Billing section
3. Use cost optimization recommendations

## Support

### Getting Help

1. Check the logs: `gcloud app logs tail -s default`
2. Review this README for common issues
3. Check Google Cloud documentation
4. Verify environment variables are set correctly

### Useful Commands

```bash
# Check deployment status
gcloud app versions list

# Stop a specific version
gcloud app versions stop VERSION_ID

# Rollback to previous version
gcloud app versions migrate VERSION_ID

# Delete old versions
gcloud app versions delete VERSION_ID
```

## License

This project is for educational and personal use. Please ensure you comply with Discord's Terms of Service and Google Cloud's Terms of Service.

---

**Happy PC Building! 🖥️✨**

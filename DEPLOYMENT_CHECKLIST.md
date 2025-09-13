# Deployment Checklist

Use this checklist to ensure a successful deployment of your Discord PC Build Bot to Google Cloud.

## Pre-Deployment Checklist

### ✅ Prerequisites
- [ ] Google Cloud account with billing enabled
- [ ] Discord application created with bot token
- [ ] Google Gemini API key obtained
- [ ] gcloud CLI installed and authenticated
- [ ] All required files present in the project directory

### ✅ Configuration
- [ ] Discord bot token obtained from [Discord Developer Portal](https://discord.com/developers/applications)
- [ ] Gemini API key obtained from [Google AI Studio](https://makersuite.google.com/app/apikey)
- [ ] Google Cloud project ID identified
- [ ] Environment variables configured in `app.yaml`
- [ ] Deployment scripts updated with project ID

### ✅ Files Verification
- [ ] `discord_pc_bot.py` - Main bot logic
- [ ] `main.py` - Cloud entry point
- [ ] `app.yaml` - App Engine configuration
- [ ] `requirements.txt` - Python dependencies
- [ ] `deploy.sh` / `deploy.bat` - Deployment scripts
- [ ] `.gcloudignore` - Ignore file for deployment
- [ ] `config.yaml` - Bot configuration
- [ ] `README.md` - Documentation

## Deployment Steps

### ✅ Google Cloud Setup
- [ ] Create Google Cloud project (if not exists)
- [ ] Enable App Engine API
- [ ] Enable Cloud Build API
- [ ] Set project ID: `gcloud config set project YOUR_PROJECT_ID`
- [ ] Authenticate: `gcloud auth login`

### ✅ Bot Configuration
- [ ] Run setup script: `python setup.py`
- [ ] Verify tokens in `app.yaml`
- [ ] Test local bot functionality (optional)
- [ ] Review configuration files

### ✅ Deployment
- [ ] Run deployment script: `./deploy.sh` (Linux/Mac) or `deploy.bat` (Windows)
- [ ] Monitor deployment progress
- [ ] Verify deployment success
- [ ] Note the service URL

### ✅ Post-Deployment
- [ ] Test health endpoint: `https://YOUR_PROJECT_ID.appspot.com/health`
- [ ] Verify bot appears online in Discord
- [ ] Test bot commands: `!build`, `!status`, `!health`
- [ ] Check logs: `gcloud app logs tail -s default`
- [ ] Set up monitoring alerts (optional)

## Testing Checklist

### ✅ Bot Functionality
- [ ] Bot responds to `!build` command
- [ ] Bot creates private threads
- [ ] Conversation flow works properly
- [ ] Build generation completes successfully
- [ ] Refinement mode works
- [ ] All commands respond correctly

### ✅ Error Handling
- [ ] Bot handles invalid commands gracefully
- [ ] Bot recovers from API errors
- [ ] Session management works properly
- [ ] File operations don't cause crashes

### ✅ Performance
- [ ] Bot responds within reasonable time
- [ ] Multiple users can use bot simultaneously
- [ ] Memory usage is stable
- [ ] No memory leaks detected

## Monitoring Checklist

### ✅ Logs
- [ ] Application logs are visible in Google Cloud Console
- [ ] Error logs are properly formatted
- [ ] Log levels are appropriate
- [ ] Sensitive data is not logged

### ✅ Health Checks
- [ ] Health endpoint returns 200 OK
- [ ] Bot status is correctly reported
- [ ] Health checks run automatically
- [ ] Unhealthy instances restart properly

### ✅ Scaling
- [ ] Automatic scaling works
- [ ] Performance under load is acceptable
- [ ] Cost is within expected range
- [ ] Resource usage is optimized

## Security Checklist

### ✅ Secrets Management
- [ ] No hardcoded tokens in source code
- [ ] Environment variables are properly set
- [ ] API keys are secured
- [ ] Discord token is protected

### ✅ Access Control
- [ ] Bot permissions are minimal required
- [ ] Google Cloud IAM is properly configured
- [ ] No unnecessary permissions granted
- [ ] Access is logged and monitored

## Troubleshooting

### Common Issues
- [ ] Bot token invalid → Check Discord Developer Portal
- [ ] API key invalid → Verify Gemini API key
- [ ] Deployment fails → Check gcloud authentication
- [ ] Bot not responding → Check logs and environment variables
- [ ] High memory usage → Increase instance class or optimize code

### Support Resources
- [ ] Google Cloud Documentation
- [ ] Discord Bot Documentation
- [ ] Gemini API Documentation
- [ ] Project README.md

## Maintenance

### Regular Tasks
- [ ] Monitor bot performance weekly
- [ ] Review logs monthly
- [ ] Update dependencies quarterly
- [ ] Rotate API keys annually
- [ ] Review costs monthly

### Backup Strategy
- [ ] Session data backup strategy in place
- [ ] Configuration files version controlled
- [ ] Deployment scripts documented
- [ ] Recovery procedures documented

---

## Quick Commands Reference

```bash
# Deploy
./deploy.sh                    # Linux/Mac
deploy.bat                     # Windows

# Monitor
gcloud app logs tail -s default
gcloud app versions list
gcloud app browse

# Manage
gcloud app versions stop VERSION_ID
gcloud app versions delete VERSION_ID
gcloud app services delete default
```

**Deployment Status: [ ] Ready for Production**

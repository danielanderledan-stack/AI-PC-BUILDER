#!/usr/bin/env python3
"""
Setup script for Discord PC Build Bot
Helps configure the bot for Google Cloud deployment
"""

import os
import sys
import yaml
import re

def validate_token_format(token):
    """Validate Discord bot token format"""
    # Discord bot tokens are typically 24 characters for client ID + 27 characters for secret
    # Format: XXXXXXXXXXXXXXXX.XXXXXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXX
    pattern = r'^[A-Za-z0-9]{24}\.[A-Za-z0-9]{6,7}\.[A-Za-z0-9_-]{27}$'
    return bool(re.match(pattern, token))

def validate_api_key(api_key):
    """Validate Google API key format"""
    # Google API keys are typically 39 characters long
    return len(api_key) >= 30 and api_key.startswith('AIza')

def setup_environment():
    """Interactive setup for environment variables"""
    print("🔧 Discord PC Build Bot Setup")
    print("=" * 40)
    
    # Get Discord Bot Token
    while True:
        discord_token = input("\n🤖 Enter your Discord Bot Token: ").strip()
        if validate_token_format(discord_token):
            break
        print("❌ Invalid Discord token format. Please check your token.")
    
    # Get Gemini API Key
    while True:
        gemini_key = input("🔑 Enter your Gemini API Key: ").strip()
        if validate_api_key(gemini_key):
            break
        print("❌ Invalid API key format. Please check your key.")
    
    # Get Google Cloud Project ID
    project_id = input("☁️  Enter your Google Cloud Project ID: ").strip()
    
    # Update app.yaml
    update_app_yaml(discord_token, gemini_key)
    
    # Update deploy scripts
    update_deploy_scripts(project_id)
    
    print("\n✅ Setup complete!")
    print("\n📝 Next steps:")
    print("1. Review the configuration files")
    print("2. Run: gcloud auth login")
    print("3. Run: ./deploy.sh (Linux/Mac) or deploy.bat (Windows)")
    print("4. Set environment variables in Google Cloud Console")

def update_app_yaml(discord_token, gemini_key):
    """Update app.yaml with provided tokens"""
    try:
        with open('app.yaml', 'r') as f:
            content = f.read()
        
        content = content.replace('YOUR_DISCORD_BOT_TOKEN_HERE', discord_token)
        content = content.replace('YOUR_GEMINI_API_KEY_HERE', gemini_key)
        
        with open('app.yaml', 'w') as f:
            f.write(content)
        
        print("✅ Updated app.yaml")
    except Exception as e:
        print(f"❌ Error updating app.yaml: {e}")

def update_deploy_scripts(project_id):
    """Update deployment scripts with project ID"""
    scripts = ['deploy.sh', 'deploy.bat']
    
    for script in scripts:
        if os.path.exists(script):
            try:
                with open(script, 'r') as f:
                    content = f.read()
                
                content = content.replace('your-project-id-here', project_id)
                
                with open(script, 'w') as f:
                    f.write(content)
                
                print(f"✅ Updated {script}")
            except Exception as e:
                print(f"❌ Error updating {script}: {e}")

def check_requirements():
    """Check if required files exist"""
    required_files = [
        'discord_pc_bot.py',
        'main.py',
        'app.yaml',
        'requirements.txt'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print("❌ Missing required files:")
        for file in missing_files:
            print(f"   - {file}")
        return False
    
    return True

def main():
    """Main setup function"""
    print("🚀 Discord PC Build Bot Setup")
    print("=" * 40)
    
    # Check requirements
    if not check_requirements():
        print("\n❌ Setup cannot continue due to missing files.")
        print("Please ensure all required files are present.")
        sys.exit(1)
    
    # Check if already configured
    if os.path.exists('app.yaml'):
        with open('app.yaml', 'r') as f:
            content = f.read()
            if 'YOUR_DISCORD_BOT_TOKEN_HERE' not in content:
                print("✅ Bot appears to be already configured.")
                response = input("Do you want to reconfigure? (y/N): ").strip().lower()
                if response != 'y':
                    print("Setup cancelled.")
                    sys.exit(0)
    
    # Run setup
    setup_environment()

if __name__ == '__main__':
    main()

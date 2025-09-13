#!/usr/bin/env python3
"""
Main entry point for Discord PC Build Bot on Google Cloud Platform
"""

import os
import logging
import asyncio
from flask import Flask, request, jsonify
import threading
import time

# Configure logging for Google Cloud
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the Discord bot
try:
    from discord_pc_bot import bot, TOKEN
except ImportError as e:
    logger.error(f"Failed to import Discord bot: {e}")
    raise

# Flask app for health checks
app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Google Cloud"""
    try:
        # Check if bot is running
        if bot.is_ready():
            return jsonify({
                'status': 'healthy',
                'bot_ready': True,
                'timestamp': time.time()
            }), 200
        else:
            return jsonify({
                'status': 'starting',
                'bot_ready': False,
                'timestamp': time.time()
            }), 202
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': time.time()
        }), 500

@app.route('/', methods=['GET'])
def root():
    """Root endpoint"""
    return jsonify({
        'service': 'Discord PC Build Bot',
        'status': 'running',
        'version': '1.0.0'
    }), 200

def run_discord_bot():
    """Run the Discord bot in a separate thread"""
    try:
        logger.info("Starting Discord bot...")
        
        # Get token from environment variable
        bot_token = os.environ.get('DISCORD_BOT_TOKEN') or TOKEN
        
        if not bot_token:
            logger.error("No Discord bot token found in environment variables")
            return
        
        # Run the bot
        bot.run(bot_token)
        
    except Exception as e:
        logger.error(f"Discord bot failed to start: {e}")

def main():
    """Main function to start both Flask and Discord bot"""
    logger.info("Starting Discord PC Build Bot service...")
    
    # Start Discord bot in a separate thread
    discord_thread = threading.Thread(target=run_discord_bot, daemon=True)
    discord_thread.start()
    
    # Wait a moment for bot to initialize
    time.sleep(2)
    
    # Start Flask app for health checks
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting Flask app on port {port}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True
    )

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Simple main entry point for Discord PC Build Bot on Google Cloud Platform
"""

import os
import logging
import asyncio
import discord
from discord.ext import commands
import threading
import time

# Configure logging for Google Cloud
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, case_insensitive=True)

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    print(f'{bot.user} has connected to Discord!')

@bot.command(name='test', help='Test command')
async def test_command(ctx):
    await ctx.send('Bot is working!')

@bot.command(name='health', help='Health check')
async def health_check(ctx):
    embed = discord.Embed(
        title="🤖 Bot Health Status",
        description="Bot is running successfully!",
        color=0x00ff00
    )
    embed.add_field(name="Status", value="✅ Online", inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    await ctx.send(embed=embed)

def run_bot():
    """Run the Discord bot"""
    try:
        logger.info("Starting Discord bot...")
        
        # Get token from environment variable
        bot_token = os.environ.get('DISCORD_BOT_TOKEN')
        
        if not bot_token:
            logger.error("No Discord bot token found in environment variables")
            return
        
        # Run the bot
        bot.run(bot_token)
        
    except Exception as e:
        logger.error(f"Discord bot failed to start: {e}")

def main():
    """Main function to start the bot"""
    logger.info("Starting Discord PC Build Bot service...")
    
    # Start Discord bot in a separate thread
    discord_thread = threading.Thread(target=run_bot, daemon=True)
    discord_thread.start()
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down...")

if __name__ == '__main__':
    main()

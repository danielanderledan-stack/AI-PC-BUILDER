#!/usr/bin/env python3
"""
Discord PC Build Bot for Railway
"""

import os
import logging
import discord
from discord.ext import commands

# Configure logging
logging.basicConfig(level=logging.INFO)
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

# Start the bot
if __name__ == '__main__':
    bot_token = os.environ.get('DISCORD_BOT_TOKEN')
    if not bot_token:
        logger.error("No Discord bot token found in environment variables")
        logger.error("Please set DISCORD_BOT_TOKEN environment variable")
        exit(1)
    
    logger.info("Starting Discord bot...")
    bot.run(bot_token)

#!/usr/bin/env python3
"""
Launcher for the Monarch AI Society POC.
Starts both the MCP server and Telegram bot.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from telegram_bot import MonarchTelegramBot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def start_monarch_society():
    """Start the complete Monarch AI Society system."""
    logger.info("🏰 Starting Monarch AI Society...")
    
    # Check required environment variables
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        logger.error("❌ TELEGRAM_BOT_TOKEN environment variable required")
        logger.info("To get a token: Message @BotFather on Telegram and create a new bot")
        return
    
    # Start Telegram bot
    logger.info("🤖 Starting Telegram bot...")
    bot = MonarchTelegramBot(telegram_token)
    
    try:
        # Start bot in background
        bot_task = asyncio.create_task(bot.start_bot())
        
        logger.info("✅ Monarch AI Society is running!")
        logger.info("📱 Chat with your Monarch on Telegram")
        logger.info("🔧 MCP server available for Claude Desktop/Cursor integration")
        logger.info("Press Ctrl+C to stop")
        
        # Keep running
        await bot_task
        
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down Monarch AI Society...")
    except Exception as e:
        logger.error(f"❌ Error: {e}")

def print_setup_instructions():
    """Print setup instructions for users."""
    print("""
🏰 Monarch AI Society Setup

1. Install dependencies:
   pip install -r requirements.txt

2. Set up Telegram Bot:
   - Message @BotFather on Telegram
   - Create a new bot with /newbot
   - Get your bot token
   - Set environment variable: export TELEGRAM_BOT_TOKEN="your_token_here"

3. Optional - AWS Setup (for agent deployment):
   - Configure AWS credentials: aws configure
   - Set region: export AWS_DEFAULT_REGION="us-east-1"

4. Optional - MCP Integration:
   - Add this to your Claude Desktop config:
     {
       "mcpServers": {
         "monarch": {
           "command": "python",
           "args": ["/path/to/mcp-monarch/src/monarch.py"]
         }
       }
     }

5. Start the system:
   python launcher.py

6. Chat with your Monarch on Telegram!
   - /start - Welcome and commands
   - /vision - See the guiding vision  
   - /society - Check society status
   - /spawn api_development - Create specialist agent
   - Or just chat naturally about goals and progress

The Monarch will evaluate when to spawn new agents based on workload and efficiency.
Each agent costs part of the monthly budget but provides specialized capabilities.
""")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        print_setup_instructions()
    else:
        try:
            asyncio.run(start_monarch_society())
        except KeyboardInterrupt:
            logger.info("👋 Goodbye!")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
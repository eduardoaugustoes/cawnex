#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple launcher for Monarch AI Society with better error handling.
"""

import os
import sys
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_telegram_token():
    """Check if Telegram token is available."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN environment variable is required")
        print("")
        print("🤖 To get a Telegram bot token:")
        print("1. Open Telegram and search for @BotFather")
        print("2. Send /newbot command")
        print("3. Follow the instructions to create your bot")
        print("4. Copy the token and set it as environment variable:")
        print("")
        print("   export TELEGRAM_BOT_TOKEN='your_token_here'")
        print("   ./start.sh")
        return False
    return True

def test_imports():
    """Test required imports."""
    try:
        print("🔧 Testing imports...")

        # Add src to path
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent / "src"))

        # Test core imports
        import asyncio
        print("   ✅ asyncio")

        from telegram import Update
        print("   ✅ telegram")

        from telegram_bot import MonarchTelegramBot
        print("   ✅ telegram_bot")

        from monarch import monarch
        print("   ✅ monarch")

        return True

    except ImportError as e:
        print(f"   ❌ Import failed: {e}")
        print("   Try: source venv/bin/activate && pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        return False

def start_telegram_bot():
    """Start the Telegram bot."""
    try:
        print("🤖 Starting Telegram bot...")

        # Import after path setup
        import asyncio
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent / "src"))
        from telegram_bot import MonarchTelegramBot

        # Get token
        token = os.getenv("TELEGRAM_BOT_TOKEN")

        # Create bot
        bot = MonarchTelegramBot(token)

        print("✅ Monarch AI Society is running!")
        print("📱 Chat with your Monarch on Telegram")
        print("🔧 MCP server available for Claude Desktop integration")
        print("Press Ctrl+C to stop")
        print("")

        # Run bot
        asyncio.run(bot.start_bot())

    except KeyboardInterrupt:
        print("\n🛑 Shutting down Monarch AI Society...")
    except Exception as e:
        print(f"\n❌ Error starting bot: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main entry point."""
    print("🏰 Starting Monarch AI Society...")
    print("💰 Budget: $500/month")
    print("🎯 Vision: Build autonomous AI platform")
    print("")

    # Check telegram token
    if not check_telegram_token():
        return

    # Test imports
    if not test_imports():
        return

    # Start the bot
    start_telegram_bot()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        import traceback
        traceback.print_exc()

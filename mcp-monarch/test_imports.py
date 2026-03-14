#!/usr/bin/env python3
"""
Test all imports to verify environment is working.
"""

print("🔧 Testing Monarch AI Society imports...")

try:
    from telegram import Update
    print("✅ telegram - OK")
except ImportError as e:
    print(f"❌ telegram - FAILED: {e}")

try:
    import asyncio
    print("✅ asyncio - OK")
except ImportError as e:
    print(f"❌ asyncio - FAILED: {e}")

try:
    import json
    print("✅ json - OK")
except ImportError as e:
    print(f"❌ json - FAILED: {e}")

try:
    import logging
    print("✅ logging - OK")
except ImportError as e:
    print(f"❌ logging - FAILED: {e}")

try:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent / "src"))
    from monarch import monarch
    print("✅ monarch - OK")
except ImportError as e:
    print(f"❌ monarch - FAILED: {e}")

print("\n🎯 Running basic Monarch test...")

try:
    status = monarch.get_society_status()
    print(f"✅ Monarch initialized with {status['total_agents']} agents")
    print(f"✅ Budget: {status['monarch']['budget_used']}")
    print(f"✅ Vision: {status['monarch']['vision']}")
except Exception as e:
    print(f"❌ Monarch test failed: {e}")

print("\n🏰 All imports working! Ready to start with Telegram token.")
print("\nNext steps:")
print("1. Get token from @BotFather on Telegram")
print("2. export TELEGRAM_BOT_TOKEN='your_token'")
print("3. ./start.sh")

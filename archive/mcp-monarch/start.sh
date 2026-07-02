#!/bin/bash
# Easy startup script for Monarch AI Society

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "🔧 Creating virtual environment..."
    python3 -m venv venv
    echo "📦 Installing dependencies..."
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "✅ Virtual environment found"
fi

# Activate virtual environment
source venv/bin/activate

# Check for Telegram token
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ TELEGRAM_BOT_TOKEN environment variable is required"
    echo ""
    echo "🤖 To get a Telegram bot token:"
    echo "1. Open Telegram and search for @BotFather"
    echo "2. Send /newbot command"
    echo "3. Follow the instructions to create your bot"
    echo "4. Copy the token and set it as environment variable:"
    echo ""
    echo "   export TELEGRAM_BOT_TOKEN='your_token_here'"
    echo "   ./start.sh"
    echo ""
    exit 1
fi

echo "🏰 Starting Monarch AI Society..."
echo "💰 Budget: \$500/month"
echo "🎯 Vision: Build autonomous AI platform"
echo ""
echo "📱 Your Telegram bot should be ready for chat!"
echo "🔧 MCP server available for Claude Desktop integration"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Use the virtual environment's Python with the simple launcher
./venv/bin/python simple_launcher.py

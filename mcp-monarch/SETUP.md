# 🏰 Monarch AI Society Setup Guide

## ✅ Dependencies Fixed!

The Python environment issues have been resolved. All dependencies are now installed in a virtual environment.

## 🚀 Quick Start

### 1. Get a Telegram Bot Token

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` command
3. Choose a name for your bot (e.g., "My Monarch")
4. Choose a username (e.g., "my_monarch_bot")
5. Copy the token that BotFather gives you

### 2. Set Environment Variable

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
```

### 3. Start the Monarch

```bash
cd mcp-monarch
./start.sh
```

That's it! The script will:
- ✅ Check virtual environment (already created)
- ✅ Activate venv with all dependencies
- ✅ Verify your Telegram token
- 🚀 Start the Monarch AI Society

## 📱 Chat with Your Monarch

Find your bot on Telegram and start chatting:

- `/start` - Welcome and overview
- `/vision` - See the guiding vision
- `/society` - Check budget and agents  
- `/spawn api_development` - Request API specialist
- `/workload` - Analyze bottlenecks

Or just chat naturally:
- "How are we doing?"
- "Should we hire more specialists?"
- "What's our efficiency looking like?"

## 🤖 How It Works

1. **Monarch analyzes workload** (simulated data for POC)
2. **Identifies bottlenecks** where success rate < 75%
3. **Calculates ROI** for potential specialist agents
4. **Budget-aware decisions** - only spawn if justified
5. **Society grows organically** based on efficiency needs

## 🎯 Example Conversation

```
You: How's our development going?

Monarch: I'm monitoring 15 tasks. Seeing bottlenecks in API development 
(70% success, 40h/week) and testing (60% success, 20h/week). 

Should I spawn specialists? API developer would cost $100/mo with 4x ROI.

You: Yes, spawn the API developer

Monarch: ✅ API Development Specialist spawned! 
Budget now: $100/$500. Estimated 30% efficiency improvement.
```

## 🔧 Advanced: MCP Integration

To use with Claude Desktop:

1. Add to your Claude Desktop config:
```json
{
  "mcpServers": {
    "monarch": {
      "command": "python",
      "args": ["/path/to/mcp-monarch/src/monarch.py"]
    }
  }
}
```

2. Ask Claude: "Assess the Monarch workload" or "Spawn a testing agent"

## 📊 Test First (Optional)

Run the simple test to see agent spawning logic:

```bash
cd mcp-monarch
source venv/bin/activate
python test_simple.py
```

This shows how the Monarch evaluates efficiency and makes spawning decisions.

## 🏛️ Society Principles

- **Vision-Driven**: All agents serve the same goal
- **Resource-Aware**: Budget constraints prevent chaos
- **ROI-Based**: Only spawn when economically justified  
- **Self-Organizing**: Society grows based on real needs
- **Human-Guided**: You steer via natural conversation

## ❓ Troubleshooting

**"No module named 'telegram'"**
→ Fixed! Now using `./venv/bin/python` directly. Run `./start.sh` again.

**"TELEGRAM_BOT_TOKEN required"**  
→ Get token from @BotFather and export it: `export TELEGRAM_BOT_TOKEN="..."`

**Want to test without Telegram first?**
→ Run: `./venv/bin/python test_launcher.py` for interactive demo

**Still having import issues?**
→ Test imports: `./venv/bin/python test_imports.py`

**Bot doesn't respond**
→ Check token is correct and bot is started with `./start.sh`

**Dependencies issues**
→ Try: `source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt`

## 🎭 What's Next?

1. **Test basic spawning** via Telegram
2. **Add agent-to-agent communication** 
3. **Connect to real GitHub issues**
4. **Implement recursive councils**
5. **Build autonomous development society**

The foundation is ready - now watch your AI society grow! 🤖🏰
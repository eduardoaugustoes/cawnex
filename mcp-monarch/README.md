# 👑 Monarch AI Society POC

A proof-of-concept for a self-organizing AI society where a **Monarch** agent can spawn specialized agents to fulfill its vision.

## 🎯 Vision

*"Build autonomous AI platform that creates software from human intent"*

The Monarch embodies this vision and spawns specialized agents when efficiency demands it. Each agent operates with budget constraints and serves the collective goal.

## 🏗️ Architecture

```
Human (Telegram) ↔ Monarch (MCP Server) → Spawns Agents (AWS Lambda)
```

- **Monarch**: Central coordinator with vision and budget
- **Agents**: Specialized workers (API dev, testing, UI, DevOps, security)
- **Society**: Self-organizing with resource constraints

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd mcp-monarch
pip install -r requirements.txt
```

### 2. Setup Telegram Bot
1. Message @BotFather on Telegram
2. Create bot with `/newbot`  
3. Get token and set environment:
```bash
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
```

### 3. Optional: AWS Setup (for agent deployment)
```bash
aws configure
export AWS_DEFAULT_REGION="us-east-1"
```

### 4. Start the System
```bash
python launcher.py
```

### 5. Chat with Monarch
Find your bot on Telegram and start chatting!

## 📱 Telegram Commands

- `/start` - Welcome and overview
- `/vision` - View the guiding vision
- `/society` - See current society status  
- `/agents` - List all spawned agents
- `/spawn <specialization>` - Request new agent
- `/workload` - Analyze bottlenecks

Or just chat naturally about goals and progress.

## 🤖 Available Agent Specializations

- **api_development** - REST APIs, databases, backend services
- **testing** - Test automation, quality assurance, coverage
- **ui_implementation** - React, TypeScript, responsive design
- **devops** - AWS, infrastructure, CI/CD, deployment
- **security** - OWASP, penetration testing, compliance

## 💰 Budget System

- Monarch has monthly budget (default: $500)
- Each agent costs portion of budget when spawned
- Agents only spawn when ROI justifies cost
- Budget tracking prevents over-spending

## 🔧 MCP Integration (Optional)

Add to your Claude Desktop config:
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

## 🎭 How It Works

1. **Monarch analyzes workload** and identifies bottlenecks
2. **Efficiency drops below threshold** → considers spawning specialist  
3. **ROI calculation** → only spawn if economically justified
4. **Agent deployment** → specialized Lambda function created
5. **Society grows** → more specialized, more efficient

## 📊 Example Session

```
Human: "How are we doing on the API development?"

Monarch: "I'm seeing bottlenecks in API development (70% success rate, 40h/week). 
Should I spawn an API Development Specialist? Cost: $80/month, Expected ROI: 4x"
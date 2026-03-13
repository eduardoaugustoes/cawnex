# 🖥️ Claude Desktop Integration

## ✅ **YES! Run Monarch from localhost in Claude Desktop**

The Monarch MCP Server is specifically designed to integrate with Claude Desktop, giving Claude direct access to your AI society management tools.

## 🚀 **Quick Setup**

### **1. Auto-Setup (Recommended)**
```bash
cd mcp-monarch
./venv/bin/python setup-claude.py
```

This script will:
- ✅ Generate the correct paths for your system
- ✅ Optionally install directly to Claude Desktop config  
- ✅ Backup your existing configuration
- ✅ Provide copy-paste instructions

### **2. Manual Setup**

1. **Test the MCP server works:**
```bash
cd mcp-monarch  
./venv/bin/python test_mcp_simple.py
```

2. **Get your configuration:**
```bash
./venv/bin/python setup-claude.py
# Choose option 1 to get config to copy-paste
```

3. **Add to Claude Desktop:**
- Open Claude Desktop
- Go to Settings → Developer
- Add the MCP server configuration
- Restart Claude Desktop

## 🛠️ **Available Tools in Claude**

Once connected, Claude will have access to these Monarch tools:

### **Core Functions:**
- `assess_workload()` - Analyze efficiency and identify bottlenecks
- `spawn_agent(specialization, justification)` - Create specialized agents
- `list_agents()` - View current agent society status
- `send_telegram_message(message)` - Send to Telegram bot (if running)

### **Resources:**
- `monarch://vision` - Read the foundational vision
- `monarch://society` - Get real-time society status

## 💬 **Example Claude Conversations**

### **Getting Started:**
```
You: "What tools do you have access to?"

Claude: "I have access to the Monarch AI Society tools! I can:
- Assess workload and identify bottlenecks
- Spawn specialized AI agents based on ROI analysis  
- List current agents and their status
- View the society vision and status
Would you like me to check the current state of your AI society?"
```

### **Society Management:**
```
You: "How's our AI society doing?"

Claude: "Let me check the Monarch status... [calls assess_workload]

Your AI society is handling 15 tasks with some bottlenecks:
- API development: 70% success rate, 40h/week (inefficient)
- Testing: 60% success rate, 20h/week (needs improvement)  
- UI implementation: 80% success rate (acceptable)

The Monarch has $500 budget available. Based on ROI analysis, I'd recommend spawning an API Development Specialist (estimated 4x return on $100/month investment). Should I create one?"
```

### **Agent Spawning:**
```
You: "Yes, spawn the API specialist"

Claude: "Creating API Development Specialist... [calls spawn_agent]

✅ Agent spawned successfully!
- Name: API Development Specialist
- Specialization: API development  
- Budget: $100/month
- Skills: Python, FastAPI, OpenAPI, database design
- Expected ROI: 4x

Your society now has specialized API capabilities. Budget remaining: $400/$500."
```

### **Continuous Monitoring:**
```
You: "Check if we need any other specialists"

Claude: "Analyzing current efficiency... [calls assess_workload]

After adding the API specialist, I see testing is still a bottleneck (60% success rate). The ROI analysis suggests a Testing Specialist would provide 2x return for $75/month. 

However, UI implementation is now performing well (80% success) so no specialist needed there.

Would you like me to spawn the Testing Specialist as well?"
```

## 🔧 **Troubleshooting**

### **"No tools found"**
- Check Claude Desktop config is correct
- Restart Claude Desktop after adding config
- Verify paths in configuration point to your actual files

### **"Server connection failed"**  
- Run test: `./venv/bin/python test_mcp_simple.py`
- Check virtual environment: `source venv/bin/activate`
- Verify dependencies: `pip install -r requirements.txt`

### **"Permission denied"**
- Make sure Python files are executable
- Check file paths in configuration are absolute paths

## 🎯 **What This Enables**

With Claude Desktop + Monarch MCP:

✅ **Natural conversation** about AI society management  
✅ **Real-time analysis** of efficiency and bottlenecks  
✅ **Intelligent agent spawning** based on ROI calculations  
✅ **Budget tracking** to prevent over-expansion  
✅ **Society monitoring** through Claude's interface  

## 🌟 **Advanced Usage**

Once working, you can:

1. **Combine with other tools** - Use Claude's other capabilities alongside Monarch
2. **Automate decisions** - "Check every hour if we need new specialists"
3. **Analysis and reporting** - "Generate a weekly society performance report"
4. **Strategic planning** - "Plan our society expansion for next quarter"

## 🔮 **Future Enhancements**

- **Agent-to-agent communication** - Agents will form councils
- **Real GitHub integration** - Connect to actual development work
- **Performance metrics** - Track agent efficiency over time
- **Budget optimization** - AI-driven resource allocation

---

**The foundation is ready - now Claude becomes your AI society management interface!** 🤖🏛️
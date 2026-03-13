#!/usr/bin/env python3
"""
Test the Monarch AI Society POC locally without AWS deployment.
Demonstrates the core concepts with simulated agents.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from monarch import monarch, MonarchAgent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_monarch_society():
    """Test the Monarch society creation and agent spawning."""
    
    print("🏰 Testing Monarch AI Society POC\n")
    
    # 1. Show initial state
    print("👑 Initial Monarch State:")
    status = monarch.get_society_status()
    print(f"   Vision: {status['monarch']['vision']}")
    print(f"   Budget: {status['monarch']['budget_used']}")
    print(f"   Agents: {status['total_agents']}\n")
    
    # 2. Analyze workload  
    print("📊 Workload Analysis:")
    workload = monarch.assess_workload()
    print(f"   Current tasks: {workload['current_tasks']}")
    print(f"   Bottlenecks: {', '.join(workload['bottlenecks'])}")
    print(f"   Recommendation: {workload['recommendation']}\n")
    
    # 3. Test agent spawning for each bottleneck
    for domain in ["api_development", "testing", "ui_implementation"]:
        print(f"🤖 Testing spawn for {domain}...")
        
        # Check if spawn is needed
        spawn_req = monarch.evaluate_spawn_need(domain)
        if spawn_req:
            print(f"   ✅ Spawn justified: {spawn_req.justification}")
            print(f"   💰 Cost: ${spawn_req.estimated_monthly_cost:.2f}")
            print(f"   📈 Expected ROI: {spawn_req.expected_roi:.1f}x")
            
            # Simulate spawning (without actual AWS deployment)
            try:
                # Override deployment to simulation
                original_deploy = monarch._deploy_agent_lambda
                monarch._deploy_agent_lambda = simulate_deployment
                
                agent = await monarch.spawn_agent(spawn_req)
                print(f"   🚀 Spawned: {agent.name} ({agent.specialization})")
                
                # Restore original deployment method
                monarch._deploy_agent_lambda = original_deploy
                
            except Exception as e:
                print(f"   ❌ Failed: {str(e)}")
        else:
            print(f"   ⏸️  No spawn needed for {domain}")
        
        print()
    
    # 4. Show final society state
    print("🏛️  Final Society State:")
    final_status = monarch.get_society_status() 
    print(f"   Total agents: {final_status['total_agents']}")
    print(f"   Budget used: {final_status['monarch']['budget_used']}")
    
    if final_status['agents']:
        print("   Active agents:")
        for agent in final_status['agents']:
            print(f"     • {agent['name']} - {agent['specialization']} (${agent['budget']})")
    
    if final_status['recommendations']:
        print("   Recommendations:")
        for rec in final_status['recommendations']:
            print(f"     • {rec}")
    
    print("\n✅ POC Test Complete!")
    print("\nNext steps:")
    print("1. Set TELEGRAM_BOT_TOKEN and run: python launcher.py")
    print("2. Chat with Monarch on Telegram")
    print("3. Watch society grow based on your conversations")

async def simulate_deployment(agent):
    """Simulate AWS Lambda deployment."""
    print(f"   🔄 Simulating deployment of {agent.name}...")
    await asyncio.sleep(0.5)  # Simulate deployment time
    agent.status = "active"
    print(f"   ✅ {agent.name} deployed successfully (simulated)")

def demonstrate_mcp_tools():
    """Demonstrate MCP tool functionality."""
    print("\n🔧 MCP Tools Demonstration:")
    
    tools = [
        "assess_workload",
        "spawn_agent", 
        "list_agents",
        "send_telegram_message"
    ]
    
    print("Available MCP tools:")
    for tool in tools:
        print(f"   • {tool}")
    
    print("\nTo use with Claude Desktop:")
    print('1. Add to config: {"mcpServers": {"monarch": {"command": "python", "args": ["./mcp-monarch/src/monarch.py"]}}}')
    print("2. Claude can then call monarch tools directly")
    print("3. Example: 'Hey Claude, assess the Monarch workload'")

if __name__ == "__main__":
    try:
        asyncio.run(test_monarch_society())
        demonstrate_mcp_tools()
    except KeyboardInterrupt:
        print("\n👋 Test interrupted")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)
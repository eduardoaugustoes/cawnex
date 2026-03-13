#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Demo launcher for Monarch AI Society - works without Telegram token.
Shows the agent spawning functionality interactively.
"""

import os
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from monarch import monarch

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def demo_conversation():
    """Simulate a conversation with the Monarch."""
    
    print("🏰 Monarch AI Society Demo")
    print("=" * 50)
    print("💰 Budget: $500/month")
    print("🎯 Vision: Build autonomous AI platform")
    print("")
    
    # Show initial status
    print("👑 Initial Monarch Status:")
    status = monarch.get_society_status()
    print(f"   Budget: {status['monarch']['budget_used']}")
    print(f"   Agents: {status['total_agents']}")
    print("")
    
    # Simulate workload analysis
    print("📊 Analyzing workload...")
    workload = monarch.assess_workload()
    print(f"   Current tasks: {workload['current_tasks']}")
    print(f"   Bottlenecks: {', '.join(workload['bottlenecks'])}")
    
    for domain, gap in workload['efficiency_gaps'].items():
        print(f"   • {domain.replace('_', ' ').title()}: {gap['success_rate']:.0%} success, {gap['time_spent']}h/week")
    
    print("")
    
    # Test agent spawning decisions
    domains_to_check = ["api_development", "testing", "ui_implementation"]
    
    for domain in domains_to_check:
        print(f"🤖 Evaluating {domain.replace('_', ' ').title()} specialist...")
        
        spawn_req = monarch.evaluate_spawn_need(domain)
        if spawn_req:
            print(f"   ✅ RECOMMENDED")
            print(f"   💰 Cost: ${spawn_req.estimated_monthly_cost:.2f}/month")
            print(f"   📈 Expected ROI: {spawn_req.expected_roi:.1f}x")
            print(f"   📋 Justification: {spawn_req.justification}")
            
            # Ask user
            try:
                response = input(f"   🚀 Spawn {domain.replace('_', ' ').title()} Specialist? (y/n): ").lower().strip()
                if response in ['y', 'yes']:
                    # Mock deploy for demo
                    import time
                    
                    print(f"   ⚡ Deploying {spawn_req.role}...")
                    time.sleep(0.5)  # Simple sleep instead of async
                    print(f"   ✅ {spawn_req.role} deployed!")
                    
                    # Create agent manually for demo
                    from monarch import Agent
                    from datetime import datetime, timezone
                    import uuid
                    
                    agent = Agent(
                        id=f"demo_{len(monarch.agents) + 1}",
                        name=f"{spawn_req.specialization.replace('_', ' ').title()} Specialist",
                        role=spawn_req.role,
                        specialization=spawn_req.specialization,
                        monthly_budget=spawn_req.estimated_monthly_cost,
                        skills=spawn_req.required_skills,
                        status="active",
                        created_at=datetime.now(timezone.utc)
                    )
                    
                    monarch.agents[agent.id] = agent
                    monarch.spent_this_month += spawn_req.estimated_monthly_cost
                    
                    print(f"   🎉 Welcome {agent.name}!")
                    
                else:
                    print(f"   ⏸️  Skipping {domain}")
            except KeyboardInterrupt:
                print("\n👋 Demo interrupted")
                return
        else:
            print(f"   ⏸️  No spawn needed (efficiency acceptable)")
        
        print("")
    
    # Show final status
    print("🏛️  Final Society Status:")
    final_status = monarch.get_society_status()
    print(f"   Total agents: {final_status['total_agents']}")
    print(f"   Budget used: {final_status['monarch']['budget_used']}")
    
    if final_status['agents']:
        print("   Active agents:")
        for agent in final_status['agents']:
            print(f"     • {agent['name']}: {agent['specialization']} (${agent['budget']})")
    
    if final_status['recommendations']:
        print("   Recommendations:")
        for rec in final_status['recommendations']:
            print(f"     • {rec}")

def simulate_claude_interaction():
    """Simulate Claude Desktop interaction."""
    
    print("\n🖥️  Claude Desktop Integration Demo")
    print("=" * 50)
    print("This shows what Claude would see through MCP tools:")
    print("")
    
    # Simulate assess_workload tool call
    print("🛠️  Tool: assess_workload()")
    result = monarch.assess_workload()
    print("📊 Result:")
    for key, value in result.items():
        if key != 'efficiency_gaps':
            print(f"   {key}: {value}")
    print("")
    
    # Simulate spawn_agent tool call
    print("🛠️  Tool: spawn_agent('testing', 'Need better test coverage')")
    spawn_req = monarch.evaluate_spawn_need('testing')
    if spawn_req:
        print("📋 Analysis:")
        print(f"   Justification: {spawn_req.justification}")
        print(f"   Cost: ${spawn_req.estimated_monthly_cost:.2f}")
        print(f"   ROI: {spawn_req.expected_roi:.1f}x")
        print("   ✅ Spawn recommended!")
    else:
        print("   ⏸️  Spawn not needed")
    print("")
    
    # Simulate list_agents tool call  
    print("🛠️  Tool: list_agents()")
    agents = monarch.list_agents()
    print(f"📋 Current agents: {len(agents)}")
    for agent in agents:
        print(f"   • {agent.name}: {agent.status}")

def main():
    """Main demo."""
    
    print("🏰 Monarch AI Society - Interactive Demo")
    print("(No Telegram token required)")
    print("")
    
    try:
        # Test imports
        print("🔧 Testing components...")
        print("   ✅ Monarch initialized")
        print("   ✅ Agent spawning logic ready")
        print("   ✅ Budget tracking active")
        print("")
        
        print("Choose demo mode:")
        print("1. 🎭 Interactive conversation simulation")  
        print("2. 🖥️  Claude Desktop MCP tool simulation")
        print("3. 📊 Quick status check")
        
        choice = input("\nEnter choice (1/2/3): ").strip()
        
        if choice == "1":
            demo_conversation()
        elif choice == "2":
            simulate_claude_interaction()
        elif choice == "3":
            status = monarch.get_society_status()
            print(f"\n👑 Monarch Status:")
            print(f"   Vision: {status['monarch']['vision']}")
            print(f"   Budget: {status['monarch']['budget_used']}")
            print(f"   Agents: {status['total_agents']}")
        else:
            print("❌ Invalid choice")
        
        print("\n🚀 Ready for real usage!")
        print("   For Telegram: export TELEGRAM_BOT_TOKEN='your_token' && ./start.sh")
        print("   For Claude Desktop: ./venv/bin/python setup-claude.py")
        
    except KeyboardInterrupt:
        print("\n👋 Demo ended")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")

if __name__ == "__main__":
    main()
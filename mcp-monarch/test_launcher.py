#!/usr/bin/env python3
"""
Test launcher for Monarch AI Society without requiring Telegram token.
Shows the agent spawning logic in action.
"""

import asyncio
import sys
from pathlib import Path

# Add src directory to path  
sys.path.insert(0, str(Path(__file__).parent / "src"))

from monarch import monarch

async def demo_monarch_society():
    """Interactive demo of Monarch decision-making."""
    
    print("🏰 Monarch AI Society Demo")
    print("=" * 50)
    print(f"👑 Vision: {monarch.vision['primary']}")
    print(f"💰 Budget: ${monarch.monthly_budget:.2f}")
    print(f"🤖 Agents: {len(monarch.agents)}")
    print()
    
    print("📊 Analyzing workload...")
    workload = monarch.assess_workload()
    print(f"   Current tasks: {workload['current_tasks']}")
    print(f"   Bottlenecks: {', '.join(workload['bottlenecks'])}")
    print()
    
    print("🔍 Evaluating agent spawning needs...")
    
    for domain in ["api_development", "testing", "ui_implementation"]:
        print(f"\n🤖 Checking {domain}:")
        
        spawn_req = monarch.evaluate_spawn_need(domain)
        if spawn_req:
            print(f"   ✅ RECOMMENDED: {spawn_req.justification}")
            print(f"   💰 Cost: ${spawn_req.estimated_monthly_cost:.2f}/month")
            print(f"   📈 ROI: {spawn_req.expected_roi:.1f}x")
            
            # Ask user if they want to spawn
            try:
                response = input(f"   🚀 Spawn {domain.replace('_', ' ').title()} Specialist? (y/n): ").lower()
                if response in ['y', 'yes']:
                    # Override the deployment to be instant for demo
                    original_deploy = monarch._deploy_agent_lambda
                    
                    async def instant_deploy(agent):
                        print(f"   ⚡ Deploying {agent.name}...")
                        await asyncio.sleep(0.5)
                        agent.status = "active"
                        print(f"   ✅ {agent.name} deployed successfully!")
                    
                    monarch._deploy_agent_lambda = instant_deploy
                    
                    agent = await monarch.spawn_agent(spawn_req)
                    print(f"   🎉 {agent.name} joined the society!")
                    
                    # Restore original method
                    monarch._deploy_agent_lambda = original_deploy
                else:
                    print(f"   ⏸️  Skipping {domain}")
            
            except KeyboardInterrupt:
                print("\n👋 Demo interrupted")
                return
        else:
            print(f"   ⏸️  No spawn needed (efficiency acceptable)")
    
    print(f"\n🏛️  Final Society State:")
    status = monarch.get_society_status()
    print(f"   Total agents: {status['total_agents']}")
    print(f"   Budget used: {status['monarch']['budget_used']}")
    
    if status['agents']:
        print("   Active agents:")
        for agent in status['agents']:
            print(f"     • {agent['name']} - {agent['specialization']} (${agent['budget']})")
    
    print(f"\n🎯 Key Insights:")
    print("   • Monarch makes ROI-based spawning decisions")
    print("   • Budget constraints prevent over-expansion")
    print("   • Each agent brings specialized skills")
    print("   • Society grows based on efficiency needs")
    
    print(f"\n🚀 Ready for real Telegram integration!")
    print("   1. Get token from @BotFather")
    print("   2. export TELEGRAM_BOT_TOKEN='your_token'") 
    print("   3. ./start.sh")

if __name__ == "__main__":
    try:
        asyncio.run(demo_monarch_society())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
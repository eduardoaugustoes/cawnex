#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple test of Monarch functionality - no async needed.
Tests the core functions that work with Claude Desktop.
"""

import json
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_monarch_functions():
    """Test the core Monarch functions."""

    print("🔧 Testing Monarch Functions for Claude Desktop...")

    try:
        from monarch import monarch

        # Test 1: Society status
        print("\n👑 Testing society status...")
        status = monarch.get_society_status()
        print(f"   Vision: {status['monarch']['vision']}")
        print(f"   Budget: {status['monarch']['budget_used']}")
        print(f"   Agents: {status['total_agents']}")

        # Test 2: Workload assessment
        print("\n📊 Testing workload assessment...")
        workload = monarch.assess_workload()
        print(f"   Current tasks: {workload['current_tasks']}")
        print(f"   Bottlenecks: {', '.join(workload['bottlenecks'])}")

        # Test 3: Agent spawn evaluation
        print("\n🤖 Testing spawn evaluation...")
        spawn_req = monarch.evaluate_spawn_need("api_development")
        if spawn_req:
            print(f"   ✅ Spawn justified: {spawn_req.justification}")
            print(f"   💰 Cost: ${spawn_req.estimated_monthly_cost:.2f}")
            print(f"   📈 ROI: {spawn_req.expected_roi:.1f}x")
            print("   (Would create agent in real usage)")
        else:
            print("   ⏸️  No spawn needed")

        # Test 4: List agents (should be empty initially)
        print("\n📋 Testing agent listing...")
        agents = monarch.list_agents()
        print(f"   Total agents: {len(agents)}")
        if agents:
            for agent in agents:
                print(f"   • {agent.name}: {agent.status}")

        print("\n✅ All Monarch functions working!")
        return True

    except Exception as e:
        print(f"❌ Monarch function test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def show_claude_desktop_setup():
    """Show how to set up Claude Desktop integration."""

    import os
    current_path = os.path.abspath(".")
    venv_python = f"{current_path}/venv/bin/python"
    monarch_script = f"{current_path}/src/monarch.py"

    print("\n🖥️  Claude Desktop Setup")
    print("=" * 50)

    print(f"\n1. 📍 Paths for your system:")
    print(f"   Virtual env Python: {venv_python}")
    print(f"   Monarch script: {monarch_script}")

    print(f"\n2. 📋 Configuration for Claude Desktop:")
    print("   Open Claude Desktop → Settings → Developer")
    print("   Add this MCP server configuration:")

    config = {
        "mcpServers": {
            "monarch": {
                "command": venv_python,
                "args": [monarch_script],
                "env": {
                    "PYTHONPATH": f"{current_path}/src"
                }
            }
        }
    }

    print(f"\n```json\n{json.dumps(config, indent=2)}\n```")

    print(f"\n3. 🚀 Usage in Claude Desktop:")
    print("   After adding config and restarting Claude:")
    print("")
    print('   You: "What tools do you have access to?"')
    print('   Claude: "I have access to Monarch AI Society tools..."')
    print("")
    print('   You: "Assess the Monarch workload"')
    print('   Claude: "The Monarch is handling 15 tasks with bottlenecks in..."')
    print("")
    print('   You: "Should we spawn an API development specialist?"')
    print('   Claude: "Let me check... Yes, ROI analysis shows 4x return..."')
    print("")
    print('   You: "Spawn the API developer"')
    print('   Claude: "API Development Specialist spawned successfully!"')

def test_mcp_tools():
    """Test MCP-style tool functionality."""

    print("\n🛠️  MCP Tools Simulation")
    print("=" * 50)
    print("This shows what Claude would see when calling tools:")
    print("")

    from monarch import monarch

    # Tool 1: assess_workload
    print("🔧 Tool: assess_workload()")
    result = monarch.assess_workload()
    print("   Output:")
    print(f"     current_tasks: {result['current_tasks']}")
    print(f"     bottlenecks: {result['bottlenecks']}")
    print(f"     recommendation: {result['recommendation']}")
    print("")

    # Tool 2: list_agents
    print("🔧 Tool: list_agents()")
    agents = monarch.list_agents()
    print(f"   Output: {len(agents)} agents found")
    if agents:
        for agent in agents:
            print(f"     • {agent.name}: {agent.status}")
    else:
        print("     • No agents spawned yet")
    print("")

    # Tool 3: spawn_agent evaluation
    print("🔧 Tool: spawn_agent('testing', 'Need better test coverage')")
    spawn_req = monarch.evaluate_spawn_need('testing')
    if spawn_req:
        print("   Analysis:")
        print(f"     justified: True")
        print(f"     cost: ${spawn_req.estimated_monthly_cost:.2f}")
        print(f"     roi: {spawn_req.expected_roi:.1f}x")
        print(f"     reason: {spawn_req.justification}")
        print("   Result: Would spawn Testing Specialist")
    else:
        print("   Result: Spawn not justified (efficiency acceptable)")

def main():
    """Main test function."""

    try:
        print("🏰 Monarch MCP Integration Test\n")

        # Test core functions
        functions_ok = test_monarch_functions()

        if functions_ok:
            print("\n🎉 Core functions working!")

            # Show Claude Desktop setup
            show_claude_desktop_setup()

            # Show MCP tools in action
            test_mcp_tools()

            print("\n✅ Everything ready for Claude Desktop integration!")
            print("\nNext steps:")
            print("1. Run: ./venv/bin/python setup-claude.py")
            print("2. Add config to Claude Desktop")
            print("3. Restart Claude Desktop")
            print("4. Ask Claude: 'What tools do you have access to?'")

        else:
            print("\n❌ Some functions failed. Check errors above.")

    except KeyboardInterrupt:
        print("\n👋 Test interrupted")
    except Exception as e:
        print(f"\n💥 Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

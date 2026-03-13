#!/usr/bin/env python3
"""
Test the Monarch MCP server directly.
This simulates what Claude Desktop does when connecting.
"""

import json
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_mcp_server():
    """Test MCP server functionality."""
    
    print("🔧 Testing Monarch MCP Server...")
    
    try:
        from monarch import server, monarch
        
        # Test list_resources
        print("\n📚 Testing list_resources...")
        resources = await server._handlers["list_resources"]()
        for resource in resources:
            print(f"   • {resource.name}: {resource.uri}")
        
        # Test read_resource  
        print("\n📖 Testing read_resource...")
        vision_content = await server._handlers["read_resource"]("monarch://vision")
        print("   Vision content preview:")
        vision_data = json.loads(vision_content)
        print(f"   Primary: {vision_data['primary']}")
        
        # Test list_tools
        print("\n🛠️  Testing list_tools...")
        tools = await server._handlers["list_tools"]()
        for tool in tools:
            print(f"   • {tool.name}: {tool.description}")
        
        # Test tool call
        print("\n⚡ Testing tool call (assess_workload)...")
        result = await server._handlers["call_tool"]("assess_workload", {})
        workload_data = json.loads(result[0].text)
        print(f"   Tasks: {workload_data['current_tasks']}")
        print(f"   Bottlenecks: {', '.join(workload_data['bottlenecks'])}")
        
        # Test agent spawning
        print("\n🤖 Testing agent spawn...")
        spawn_result = await server._handlers["call_tool"]("spawn_agent", {
            "specialization": "testing",
            "justification": "Need better test coverage"
        })
        spawn_data = json.loads(spawn_result[0].text)
        print(f"   Result: {spawn_data.get('status', 'unknown')}")
        
        print("\n✅ MCP Server working perfectly!")
        print("\n🎯 Ready for Claude Desktop integration")
        
    except Exception as e:
        print(f"❌ MCP Server test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def show_claude_config():
    """Show Claude Desktop configuration."""
    
    import os
    current_dir = os.path.abspath(".")
    
    print("\n🖥️  Claude Desktop Configuration:")
    print("Add this to your Claude Desktop settings:")
    
    config = {
        "mcpServers": {
            "monarch": {
                "command": "python3",
                "args": [f"{current_dir}/src/monarch.py"]
            }
        }
    }
    
    print(f"\n```json\n{json.dumps(config, indent=2)}\n```")
    
    print(f"\n📍 Path: {current_dir}/src/monarch.py")
    print(f"\n📋 Steps:")
    print("1. Open Claude Desktop")
    print("2. Go to Settings → Developer")  
    print("3. Add MCP Server configuration above")
    print("4. Restart Claude Desktop")
    print("5. Ask Claude: 'What tools do you have from Monarch?'")

if __name__ == "__main__":
    import asyncio
    
    try:
        print("🏰 Monarch MCP Server Test\n")
        
        success = asyncio.run(test_mcp_server())
        
        if success:
            show_claude_config()
        
    except KeyboardInterrupt:
        print("\n👋 Test interrupted")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
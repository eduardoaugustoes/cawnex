#!/usr/bin/env python3
"""
Generate Claude Desktop configuration for Monarch MCP server.
This script creates the exact configuration needed for your system.
"""

import json
import os
import platform
from pathlib import Path

def get_claude_config_path():
    """Get the Claude Desktop configuration path for this OS."""
    
    system = platform.system()
    
    if system == "Darwin":  # macOS
        return os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
    elif system == "Windows":
        return os.path.expanduser("~/AppData/Roaming/Claude/claude_desktop_config.json") 
    else:  # Linux
        return os.path.expanduser("~/.config/claude/claude_desktop_config.json")

def generate_config():
    """Generate MCP server configuration."""
    
    # Get current directory and required paths
    current_dir = os.path.abspath(".")
    venv_python = os.path.join(current_dir, "venv", "bin", "python")
    
    # On Windows, use python.exe
    if platform.system() == "Windows":
        venv_python = os.path.join(current_dir, "venv", "Scripts", "python.exe")
    
    monarch_script = os.path.join(current_dir, "src", "monarch.py")
    src_path = os.path.join(current_dir, "src")
    
    # Verify paths exist
    if not os.path.exists(venv_python):
        print(f"❌ Virtual environment Python not found: {venv_python}")
        print("   Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt")
        return None
    
    if not os.path.exists(monarch_script):
        print(f"❌ Monarch script not found: {monarch_script}")
        return None
    
    config = {
        "mcpServers": {
            "monarch": {
                "command": venv_python,
                "args": [monarch_script],
                "env": {
                    "PYTHONPATH": src_path
                }
            }
        }
    }
    
    return config

def backup_existing_config(config_path):
    """Backup existing Claude configuration."""
    
    if os.path.exists(config_path):
        backup_path = config_path + ".backup"
        print(f"📋 Backing up existing config to: {backup_path}")
        
        with open(config_path, 'r') as f:
            existing = f.read()
        
        with open(backup_path, 'w') as f:
            f.write(existing)
        
        return True
    
    return False

def merge_with_existing_config(config_path, new_config):
    """Merge with existing Claude Desktop config."""
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                existing_config = json.load(f)
        except json.JSONDecodeError:
            print("⚠️  Existing config has JSON errors, creating new one")
            existing_config = {}
    else:
        existing_config = {}
    
    # Merge MCP servers
    if "mcpServers" not in existing_config:
        existing_config["mcpServers"] = {}
    
    existing_config["mcpServers"]["monarch"] = new_config["mcpServers"]["monarch"]
    
    return existing_config

def main():
    """Main setup function."""
    
    print("🏰 Monarch AI Society - Claude Desktop Setup")
    print("=" * 55)
    
    # Generate configuration
    config = generate_config()
    if not config:
        return
    
    print(f"\n✅ Generated configuration:")
    print(json.dumps(config, indent=2))
    
    # Get Claude Desktop config path
    config_path = get_claude_config_path()
    print(f"\n📍 Claude Desktop config path: {config_path}")
    
    # Ask user what to do
    print(f"\nWhat would you like to do?")
    print("1. 📋 Just show the configuration (copy-paste manually)")
    print("2. 💾 Save to file claude_desktop_config.json")  
    print("3. 🔧 Auto-install to Claude Desktop config")
    
    try:
        choice = input("\nEnter choice (1/2/3): ").strip()
        
        if choice == "1":
            print(f"\n📋 Copy this configuration to Claude Desktop Settings → Developer:")
            print(f"\n```json\n{json.dumps(config, indent=2)}\n```")
            
        elif choice == "2":
            output_file = "claude_desktop_config.json"
            with open(output_file, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"\n💾 Configuration saved to: {output_file}")
            print(f"   Copy contents to Claude Desktop Settings → Developer")
            
        elif choice == "3":
            # Create directory if needed
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            # Backup existing config
            backup_existing_config(config_path)
            
            # Merge with existing config
            final_config = merge_with_existing_config(config_path, config)
            
            # Write configuration
            with open(config_path, 'w') as f:
                json.dump(final_config, f, indent=2)
            
            print(f"\n🔧 Configuration installed to: {config_path}")
            print(f"🔄 Please restart Claude Desktop to load the new configuration")
            
        else:
            print("❌ Invalid choice")
            return
            
    except KeyboardInterrupt:
        print("\n👋 Setup cancelled")
        return
    
    print(f"\n🚀 Next steps:")
    print("1. 🔄 Restart Claude Desktop")
    print("2. 💬 Ask Claude: 'What tools do you have access to?'")
    print("3. 🤖 Try: 'Assess the Monarch workload'")
    print("4. ⚡ Try: 'Spawn an API development specialist'")
    
    print(f"\n🎯 Available Monarch Tools in Claude:")
    print("   • assess_workload - Check efficiency and bottlenecks")
    print("   • spawn_agent - Create specialized agents")
    print("   • list_agents - See current agent society")
    print("   • send_telegram_message - Bridge to Telegram (if bot running)")
    
    print(f"\n📚 Resources:")
    print("   • monarch://vision - The guiding vision")
    print("   • monarch://society - Current society status")

if __name__ == "__main__":
    main()
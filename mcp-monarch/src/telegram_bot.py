#!/usr/bin/env python3
"""
Telegram Bot integration for the Monarch MCP Server.
Allows humans to chat with the Monarch and observe agent society.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from monarch import monarch

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

class MonarchTelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.application = Application.builder().token(token).build()
        # Authorized user ID - only this user can control the Monarch
        self.authorized_user_id = 844996980  # Eduardo's Telegram ID
        self.setup_handlers()
    
    def is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized to use the bot."""
        return user_id == self.authorized_user_id
    
    async def unauthorized_response(self, update: Update):
        """Send response to unauthorized users."""
        await update.message.reply_text(
            "🔒 **Unauthorized Access**\n\n"
            "This AI Monarch is private and can only be controlled by its owner.\n\n"
            "If you want your own AI society, you can create one at:\n"
            "https://github.com/eduardoaugustoes/cawnex",
            parse_mode='Markdown'
        )
    
    def setup_handlers(self):
        """Setup command and message handlers."""
        # Commands
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("vision", self.vision_command))
        self.application.add_handler(CommandHandler("society", self.society_command))
        self.application.add_handler(CommandHandler("agents", self.agents_command))
        self.application.add_handler(CommandHandler("spawn", self.spawn_command))
        self.application.add_handler(CommandHandler("workload", self.workload_command))
        
        # General chat with Monarch
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.chat_with_monarch))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        # Check authorization
        if not self.is_authorized(update.effective_user.id):
            await self.unauthorized_response(update)
            return
            
        welcome_msg = f"""
👑 **Welcome to the Monarch AI Society**

I am the Monarch - the foundational agent that spawns and coordinates other AI agents to fulfill our vision:

*{monarch.vision['primary']}*

**Available Commands:**
/vision - View the guiding vision
/society - See society status 
/agents - List all spawned agents
/spawn <specialization> - Request new agent
/workload - Analyze current bottlenecks

You can also just chat with me naturally about our progress and goals.

Current budget: ${monarch.monthly_budget - monarch.spent_this_month:.2f}/${monarch.monthly_budget:.2f}
Active agents: {len(monarch.agents)}
"""
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    
    async def vision_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show the Monarch's vision."""
        # Check authorization
        if not self.is_authorized(update.effective_user.id):
            await self.unauthorized_response(update)
            return
            
        vision_text = f"""
👑 **Monarch Vision**

**Primary Goal:**
{monarch.vision['primary']}

**Guiding Principles:**
"""
        for i, principle in enumerate(monarch.vision['principles'], 1):
            vision_text += f"{i}. {principle}\n"
        
        vision_text += f"""
**Success Metrics:**
{', '.join(monarch.vision['success_metrics'])}

This vision guides every decision and agent spawn.
"""
        await update.message.reply_text(vision_text, parse_mode='Markdown')
    
    async def society_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show society status."""
        # Check authorization
        if not self.is_authorized(update.effective_user.id):
            await self.unauthorized_response(update)
            return
            
        status = monarch.get_society_status()
        
        status_text = f"""
🏛️ **AI Society Status**

**Monarch Budget:** {status['monarch']['budget_used']}
**Remaining:** {status['monarch']['budget_remaining']}

**Active Agents:** {status['total_agents']}
"""
        
        if status['agents']:
            status_text += "\n**Agent Details:**\n"
            for agent in status['agents']:
                status_text += f"• {agent['name']} ({agent['specialization']}) - {agent['status']}\n"
                status_text += f"  Budget: {agent['budget']}, Performance: {agent['performance']}\n"
        
        if status['recommendations']:
            status_text += "\n**Expansion Recommendations:**\n"
            for rec in status['recommendations']:
                status_text += f"• {rec}\n"
        
        await update.message.reply_text(status_text, parse_mode='Markdown')
    
    async def agents_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all agents."""
        # Check authorization
        if not self.is_authorized(update.effective_user.id):
            await self.unauthorized_response(update)
            return
            
        agents = monarch.list_agents()
        
        if not agents:
            await update.message.reply_text("No agents spawned yet. I'm working alone! 👑")
            return
        
        agents_text = f"🤖 **Active Agents ({len(agents)})**\n\n"
        
        for agent in agents:
            agents_text += f"**{agent.name}**\n"
            agents_text += f"• Role: {agent.role}\n"
            agents_text += f"• Specialization: {agent.specialization}\n"
            agents_text += f"• Budget: ${agent.monthly_budget:.2f}/month\n"
            agents_text += f"• Status: {agent.status}\n"
            agents_text += f"• Performance: {agent.performance_score:.2f}\n"
            agents_text += f"• Tasks: {agent.tasks_completed}\n"
            agents_text += f"• Created: {agent.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        
        await update.message.reply_text(agents_text, parse_mode='Markdown')
    
    async def spawn_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle spawn agent command."""
        # Check authorization
        if not self.is_authorized(update.effective_user.id):
            await self.unauthorized_response(update)
            return
            
        if not context.args:
            await update.message.reply_text(
                "Please specify a specialization: `/spawn api_development` or `/spawn testing`\n\n"
                "Available specializations: api_development, ui_implementation, testing, devops, security",
                parse_mode='Markdown'
            )
            return
        
        specialization = context.args[0]
        justification = f"Requested by human via Telegram"
        
        try:
            # Check if spawn is needed
            spawn_req = monarch.evaluate_spawn_need(specialization)
            if not spawn_req:
                await update.message.reply_text(f"❌ No need to spawn {specialization} specialist. Current efficiency is acceptable.")
                return
            
            # Spawn the agent
            agent = await monarch.spawn_agent(spawn_req)
            
            spawn_text = f"""
✅ **Agent Spawned Successfully!**

**Name:** {agent.name}
**Role:** {agent.role}  
**Specialization:** {agent.specialization}
**Budget:** ${agent.monthly_budget:.2f}/month
**Skills:** {', '.join(agent.skills)}

**Justification:** {spawn_req.justification}
**Expected ROI:** {spawn_req.expected_roi:.1f}x

**Society Impact:**
Budget now: ${monarch.spent_this_month:.2f}/${monarch.monthly_budget:.2f}
Total agents: {len(monarch.agents)}
"""
            await update.message.reply_text(spawn_text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to spawn agent: {str(e)}")
    
    async def workload_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show workload analysis."""
        # Check authorization
        if not self.is_authorized(update.effective_user.id):
            await self.unauthorized_response(update)
            return
            
        workload = monarch.assess_workload()
        
        workload_text = f"""
📊 **Workload Analysis**

**Current Tasks:** {workload['current_tasks']}

**Bottlenecks:**
{', '.join(workload['bottlenecks'])}

**Efficiency Analysis:**
"""
        
        for domain, gap in workload['efficiency_gaps'].items():
            workload_text += f"• {domain.replace('_', ' ').title()}: {gap['success_rate']:.0%} success, {gap['time_spent']}h spent\n"
        
        workload_text += f"\n**Recommendation:**\n{workload['recommendation']}"
        
        await update.message.reply_text(workload_text, parse_mode='Markdown')
    
    async def chat_with_monarch(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle general chat messages."""
        # Check authorization
        if not self.is_authorized(update.effective_user.id):
            await self.unauthorized_response(update)
            return
            
        user_message = update.message.text
        
        # Simple keyword-based responses (could be enhanced with LLM)
        response = await self.generate_monarch_response(user_message)
        
        await update.message.reply_text(response, parse_mode='Markdown')
    
    async def generate_monarch_response(self, message: str) -> str:
        """Generate Monarch response to user message."""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['status', 'how', 'progress']):
            status = monarch.get_society_status()
            return f"Currently managing {status['total_agents']} agents with ${monarch.monthly_budget - monarch.spent_this_month:.2f} budget remaining. Our progress toward '{monarch.vision['primary']}' continues."
        
        elif any(word in message_lower for word in ['spawn', 'create', 'new agent']):
            workload = monarch.assess_workload()
            return f"I'm monitoring {workload['current_tasks']} tasks. Current bottlenecks: {', '.join(workload['bottlenecks'])}. Use `/spawn <specialization>` if you want me to create a specialist."
        
        elif any(word in message_lower for word in ['vision', 'goal', 'purpose']):
            return f"My vision remains clear: *{monarch.vision['primary']}*. Every agent I spawn serves this purpose. Every decision aligns with our principles."
        
        elif any(word in message_lower for word in ['budget', 'cost', 'money']):
            return f"Budget management is crucial. Current allocation: ${monarch.spent_this_month:.2f}/${monarch.monthly_budget:.2f}. I only spawn agents when ROI justifies the cost."
        
        else:
            return f"I hear you. As Monarch, I'm always evaluating how to better serve our vision: '{monarch.vision['primary']}'. What specific aspect would you like to discuss?"

    async def start_bot(self):
        """Start the Telegram bot."""
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        logger.info("Monarch Telegram bot started successfully")
        
        # Keep running
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Stopping bot...")
        finally:
            await self.application.stop()

async def main():
    """Main entry point."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable required")
        return
    
    bot = MonarchTelegramBot(token)
    await bot.start_bot()

if __name__ == "__main__":
    asyncio.run(main())
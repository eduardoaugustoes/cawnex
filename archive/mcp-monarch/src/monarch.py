#!/usr/bin/env python3
"""
Monarch MCP Server - The foundational agent that can spawn others.

The Monarch embodies the vision and has the power to create specialized agents
when needed to fulfill that vision more efficiently.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource, Tool, TextContent, ImageContent, EmbeddedResource
)

# Vision - The DNA of our society
MONARCH_VISION = {
    "primary": "Build autonomous AI platform that creates software from human intent",
    "principles": [
        "Ship working software over perfect documentation",
        "Users over internal complexity",
        "Self-improvement is mandatory",
        "Efficiency over politics"
    ],
    "success_metrics": ["user_value_created", "development_velocity", "cost_efficiency"]
}

@dataclass
class Agent:
    id: str
    name: str
    role: str
    specialization: str
    monthly_budget: float
    skills: List[str]
    status: str  # "active", "idle", "spawning"
    created_at: datetime
    performance_score: float = 0.0
    tasks_completed: int = 0

@dataclass
class SpawnRequest:
    role: str
    specialization: str
    justification: str
    estimated_monthly_cost: float
    required_skills: List[str]
    expected_roi: float

class MonarchAgent:
    def __init__(self):
        self.vision = MONARCH_VISION
        self.monthly_budget = 500.0  # Monarch's total budget
        self.spent_this_month = 0.0
        self.agents: Dict[str, Agent] = {}
        self.telegram_bot_token = None

    def assess_workload(self) -> Dict[str, Any]:
        """Analyze current workload and identify needs for specialization."""
        # TODO: Integrate with actual task data
        return {
            "current_tasks": 15,
            "bottlenecks": ["API development", "UI implementation", "testing"],
            "efficiency_gaps": {
                "api_development": {"time_spent": 40, "success_rate": 0.7},
                "ui_implementation": {"time_spent": 30, "success_rate": 0.8},
                "testing": {"time_spent": 20, "success_rate": 0.6}
            },
            "recommendation": "Consider specialized agents for testing and API development"
        }

    def evaluate_spawn_need(self, domain: str) -> Optional[SpawnRequest]:
        """Determine if we need a specialized agent for a domain."""
        workload = self.assess_workload()

        if domain in workload["bottlenecks"]:
            gap = workload["efficiency_gaps"].get(domain)
            if gap and gap["success_rate"] < 0.75:
                return SpawnRequest(
                    role=f"{domain.replace('_', '-')}-specialist",
                    specialization=domain,
                    justification=f"Low success rate ({gap['success_rate']}) and high time spent ({gap['time_spent']}h)",
                    estimated_monthly_cost=min(100.0, gap["time_spent"] * 2.5),
                    required_skills=self._get_skills_for_domain(domain),
                    expected_roi=gap["time_spent"] / 10  # ROI estimate
                )
        return None

    def _get_skills_for_domain(self, domain: str) -> List[str]:
        skill_map = {
            "api_development": ["python", "fastapi", "openapi", "database-design"],
            "ui_implementation": ["react", "typescript", "css", "figma"],
            "testing": ["pytest", "playwright", "test-automation", "quality-assurance"],
            "devops": ["aws", "cdk", "docker", "ci-cd"],
            "security": ["owasp", "penetration-testing", "encryption", "compliance"]
        }
        return skill_map.get(domain, ["general-programming"])

    async def spawn_agent(self, request: SpawnRequest) -> Agent:
        """Create a new specialized agent."""
        if self.spent_this_month + request.estimated_monthly_cost > self.monthly_budget:
            raise Exception(f"Insufficient budget. Need ${request.estimated_monthly_cost}, have ${self.monthly_budget - self.spent_this_month}")

        agent = Agent(
            id=f"agent_{uuid.uuid4().hex[:8]}",
            name=f"{request.specialization.title()} Specialist",
            role=request.role,
            specialization=request.specialization,
            monthly_budget=request.estimated_monthly_cost,
            skills=request.required_skills,
            status="spawning",
            created_at=datetime.now(timezone.utc)
        )

        # TODO: Actually deploy agent Lambda function
        await self._deploy_agent_lambda(agent)

        self.agents[agent.id] = agent
        self.spent_this_month += request.estimated_monthly_cost

        return agent

    async def _deploy_agent_lambda(self, agent: Agent):
        """Deploy the agent as AWS Lambda function."""
        try:
            from agent_deployer import deployer

            # Create agent config for deployment
            agent_config = {
                "id": agent.id,
                "role": agent.role,
                "specialization": agent.specialization,
                "skills": agent.skills,
                "monthly_budget": agent.monthly_budget,
                "vision": self.vision
            }

            print(f"🚀 Deploying {agent.name} (${agent.monthly_budget}/mo)")

            # Deploy to AWS Lambda
            function_arn = await deployer.deploy_agent(agent_config)
            agent.status = "active"

            print(f"✅ {agent.name} deployed successfully: {function_arn}")

        except Exception as e:
            print(f"❌ Failed to deploy {agent.name}: {str(e)}")
            agent.status = "failed"
            # For POC, don't fail completely - just mark as failed
            pass

    def list_agents(self) -> List[Agent]:
        """Get all spawned agents."""
        return list(self.agents.values())

    def get_society_status(self) -> Dict[str, Any]:
        """Get current state of the AI society."""
        return {
            "monarch": {
                "vision": self.vision["primary"],
                "budget_used": f"${self.spent_this_month:.2f}/${self.monthly_budget:.2f}",
                "budget_remaining": f"${self.monthly_budget - self.spent_this_month:.2f}"
            },
            "agents": [
                {
                    "id": agent.id,
                    "name": agent.name,
                    "specialization": agent.specialization,
                    "budget": f"${agent.monthly_budget:.2f}",
                    "status": agent.status,
                    "performance": f"{agent.performance_score:.2f}",
                    "tasks_completed": agent.tasks_completed
                }
                for agent in self.agents.values()
            ],
            "total_agents": len(self.agents),
            "recommendations": self._get_expansion_recommendations()
        }

    def _get_expansion_recommendations(self) -> List[str]:
        """Suggest areas for expansion."""
        workload = self.assess_workload()
        recommendations = []

        for bottleneck in workload["bottlenecks"]:
            if bottleneck not in [a.specialization for a in self.agents.values()]:
                spawn_req = self.evaluate_spawn_need(bottleneck)
                if spawn_req and spawn_req.estimated_monthly_cost < (self.monthly_budget - self.spent_this_month):
                    recommendations.append(f"Consider spawning {spawn_req.role} (ROI: {spawn_req.expected_roi:.1f}x)")

        return recommendations

# Global monarch instance
monarch = MonarchAgent()

# MCP Server setup
server = Server("monarch")

@server.list_resources()
async def handle_list_resources() -> list[Resource]:
    """List available resources."""
    return [
        Resource(
            uri="monarch://vision",
            name="Monarch Vision",
            description="The foundational vision that guides all agents",
            mimeType="application/json"
        ),
        Resource(
            uri="monarch://society",
            name="Society Status",
            description="Current state of the AI agent society",
            mimeType="application/json"
        )
    ]

@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read resource content."""
    if uri == "monarch://vision":
        return json.dumps(monarch.vision, indent=2)
    elif uri == "monarch://society":
        return json.dumps(monarch.get_society_status(), indent=2)
    else:
        raise ValueError(f"Unknown resource: {uri}")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="assess_workload",
            description="Analyze current workload and identify bottlenecks",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="spawn_agent",
            description="Create a new specialized agent to help fulfill the vision",
            inputSchema={
                "type": "object",
                "properties": {
                    "specialization": {
                        "type": "string",
                        "description": "Domain of specialization (e.g., 'api_development', 'testing', 'ui_implementation')"
                    },
                    "justification": {
                        "type": "string",
                        "description": "Why this agent is needed"
                    }
                },
                "required": ["specialization", "justification"]
            }
        ),
        Tool(
            name="list_agents",
            description="List all spawned agents and their status",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="send_telegram_message",
            description="Send message to Telegram bot for human interaction",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to send"
                    }
                },
                "required": ["message"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "assess_workload":
            result = monarch.assess_workload()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "spawn_agent":
            specialization = arguments["specialization"]
            justification = arguments["justification"]

            # Evaluate if we should spawn
            spawn_req = monarch.evaluate_spawn_need(specialization)
            if not spawn_req:
                return [TextContent(type="text", text=f"No spawn needed for {specialization}. Current efficiency is acceptable.")]

            # Create the agent
            agent = await monarch.spawn_agent(spawn_req)

            result = {
                "status": "spawned",
                "agent": {
                    "id": agent.id,
                    "name": agent.name,
                    "specialization": agent.specialization,
                    "budget": f"${agent.monthly_budget:.2f}",
                    "skills": agent.skills
                },
                "justification": justification,
                "society_impact": f"Budget now: ${monarch.spent_this_month:.2f}/${monarch.monthly_budget:.2f}"
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "list_agents":
            agents = monarch.list_agents()
            result = {
                "total_agents": len(agents),
                "agents": [
                    {
                        "name": agent.name,
                        "specialization": agent.specialization,
                        "status": agent.status,
                        "budget": f"${agent.monthly_budget:.2f}",
                        "performance": f"{agent.performance_score:.2f}",
                        "created": agent.created_at.isoformat()
                    }
                    for agent in agents
                ]
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "send_telegram_message":
            message = arguments["message"]
            # TODO: Implement Telegram bot integration
            result = {"status": "sent", "message": message}
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    """Run the Monarch MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="monarch",
                server_version="0.1.0",
                capabilities={}
            )
        )

if __name__ == "__main__":
    asyncio.run(main())

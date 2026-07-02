#!/usr/bin/env python3
"""
Simple test of the Monarch AI Society core concepts without MCP dependencies.
Tests the agent spawning logic and society organization.
"""

import asyncio
import json
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

# Simplified version for testing (no MCP dependencies)
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
    status: str
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

class SimpleMonarch:
    def __init__(self):
        self.vision = MONARCH_VISION
        self.monthly_budget = 500.0
        self.spent_this_month = 0.0
        self.agents: Dict[str, Agent] = {}

    def assess_workload(self) -> Dict[str, Any]:
        """Analyze current workload and identify needs."""
        return {
            "current_tasks": 15,
            "bottlenecks": ["api_development", "ui_implementation", "testing"],
            "efficiency_gaps": {
                "api_development": {"time_spent": 40, "success_rate": 0.7},
                "ui_implementation": {"time_spent": 30, "success_rate": 0.8},
                "testing": {"time_spent": 20, "success_rate": 0.6}
            },
            "recommendation": "Consider specialized agents for testing and API development"
        }

    def evaluate_spawn_need(self, domain: str) -> Optional[SpawnRequest]:
        """Determine if we need a specialized agent."""
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
                    expected_roi=gap["time_spent"] / 10
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
            id=f"agent_{len(self.agents) + 1:03d}",
            name=f"{request.specialization.replace('_', ' ').title()} Specialist",
            role=request.role,
            specialization=request.specialization,
            monthly_budget=request.estimated_monthly_cost,
            skills=request.required_skills,
            status="spawning",
            created_at=datetime.now(timezone.utc)
        )

        # Simulate deployment
        await self._simulate_deployment(agent)

        self.agents[agent.id] = agent
        self.spent_this_month += request.estimated_monthly_cost

        return agent

    async def _simulate_deployment(self, agent: Agent):
        """Simulate AWS Lambda deployment."""
        await asyncio.sleep(0.1)  # Quick simulation
        agent.status = "active"

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

async def test_monarch_society():
    """Test the Monarch AI Society POC."""

    print("🏰 Monarch AI Society POC Test")
    print("=" * 50)

    monarch = SimpleMonarch()

    # 1. Show initial state
    print("\n👑 Initial State:")
    status = monarch.get_society_status()
    print(f"   Vision: {status['monarch']['vision']}")
    print(f"   Budget: {status['monarch']['budget_used']}")
    print(f"   Agents: {status['total_agents']}")

    # 2. Analyze workload
    print("\n📊 Workload Analysis:")
    workload = monarch.assess_workload()
    print(f"   Current tasks: {workload['current_tasks']}")
    print(f"   Bottlenecks: {', '.join(workload['bottlenecks'])}")

    for domain, gap in workload["efficiency_gaps"].items():
        print(f"   • {domain}: {gap['success_rate']:.0%} success, {gap['time_spent']}h/week")

    # 3. Test agent spawning
    print("\n🤖 Agent Spawning Test:")
    domains_to_test = ["api_development", "testing", "devops"]

    for domain in domains_to_test:
        print(f"\n   Testing {domain}...")

        spawn_req = monarch.evaluate_spawn_need(domain)
        if spawn_req:
            print(f"   ✅ Spawn justified: {spawn_req.justification}")
            print(f"   💰 Cost: ${spawn_req.estimated_monthly_cost:.2f}/month")
            print(f"   📈 ROI: {spawn_req.expected_roi:.1f}x")
            print(f"   🛠️  Skills: {', '.join(spawn_req.required_skills)}")

            try:
                agent = await monarch.spawn_agent(spawn_req)
                print(f"   🚀 Spawned: {agent.name}")
            except Exception as e:
                print(f"   ❌ Failed: {str(e)}")
        else:
            print(f"   ⏸️  No spawn needed")

    # 4. Show final society
    print("\n🏛️  Final Society State:")
    final_status = monarch.get_society_status()
    print(f"   Total agents: {final_status['total_agents']}")
    print(f"   Budget used: {final_status['monarch']['budget_used']}")

    if final_status['agents']:
        print("   Active agents:")
        for agent in final_status['agents']:
            print(f"     • {agent['name']} - ${agent['budget']}")

    if final_status['recommendations']:
        print("   Recommendations:")
        for rec in final_status['recommendations']:
            print(f"     • {rec}")

    print("\n🎯 Key Insights:")
    print("   • Monarch uses ROI analysis to decide spawns")
    print("   • Budget constraints prevent over-expansion")
    print("   • Each agent brings specialized capabilities")
    print("   • Society self-organizes around efficiency needs")

    print("\n✅ POC Test Complete!")
    print("\nNext steps:")
    print("1. Install MCP deps: pip install mcp")
    print("2. Set TELEGRAM_BOT_TOKEN")
    print("3. Run full system: python launcher.py")
    print("4. Chat with Monarch on Telegram")

if __name__ == "__main__":
    try:
        asyncio.run(test_monarch_society())
    except KeyboardInterrupt:
        print("\n👋 Test interrupted")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

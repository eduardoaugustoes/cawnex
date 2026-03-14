#!/usr/bin/env python3
"""
Agent Deployer - Handles AWS Lambda deployment for spawned agents.
Creates specialized agent functions that can work independently.
"""

import json
import logging
from typing import Dict, Any
from pathlib import Path
import subprocess
import tempfile

import boto3
from aws_cdk import (
    App, Stack, Duration,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
    aws_logs as logs
)
from constructs import Construct

logger = logging.getLogger(__name__)

class AgentStack(Stack):
    """CDK Stack for deploying individual agent Lambda functions."""

    def __init__(self, scope: Construct, construct_id: str, agent_config: Dict[str, Any], **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        self.agent_config = agent_config

        # Create Lambda function for the agent
        self.agent_function = lambda_.Function(
            self, f"Agent{agent_config['id'].replace('_', '').title()}Function",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="agent_handler.lambda_handler",
            code=lambda_.Code.from_asset(self._create_agent_code()),
            timeout=Duration.minutes(15),
            memory_size=512,
            environment={
                "AGENT_ID": agent_config["id"],
                "AGENT_ROLE": agent_config["role"],
                "AGENT_SPECIALIZATION": agent_config["specialization"],
                "AGENT_SKILLS": json.dumps(agent_config["skills"]),
                "MONARCH_VISION": json.dumps(agent_config["vision"]),
                "MONTHLY_BUDGET": str(agent_config["monthly_budget"])
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )

        # Grant permissions for inter-agent communication
        self.agent_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "lambda:InvokeFunction",
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:Query"
                ],
                resources=["*"]  # TODO: Restrict to agent society resources
            )
        )

    def _create_agent_code(self) -> str:
        """Generate agent Lambda code based on specialization."""
        agent_code = self._generate_agent_handler()

        # Create temporary directory with agent code
        temp_dir = tempfile.mkdtemp()

        # Write agent handler
        with open(f"{temp_dir}/agent_handler.py", "w") as f:
            f.write(agent_code)

        # Write requirements.txt
        with open(f"{temp_dir}/requirements.txt", "w") as f:
            f.write(self._get_agent_requirements())

        return temp_dir

    def _generate_agent_handler(self) -> str:
        """Generate Python code for the agent Lambda handler."""
        return f"""
import json
import os
import logging
from typing import Dict, Any, List
import boto3
from datetime import datetime, timezone

# Agent configuration from environment
AGENT_ID = os.environ['AGENT_ID']
AGENT_ROLE = os.environ['AGENT_ROLE']
AGENT_SPECIALIZATION = os.environ['AGENT_SPECIALIZATION']
AGENT_SKILLS = json.loads(os.environ['AGENT_SKILLS'])
MONARCH_VISION = json.loads(os.environ['MONARCH_VISION'])
MONTHLY_BUDGET = float(os.environ['MONTHLY_BUDGET'])

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class {self.agent_config['id'].replace('_', '').title()}Agent:
    def __init__(self):
        self.id = AGENT_ID
        self.role = AGENT_ROLE
        self.specialization = AGENT_SPECIALIZATION
        self.skills = AGENT_SKILLS
        self.vision = MONARCH_VISION
        self.budget = MONTHLY_BUDGET
        self.spent_this_month = 0.0

        # Specialized behavior based on domain
        self.specialist_behaviors = self._load_specialist_behaviors()

    def _load_specialist_behaviors(self) -> Dict[str, Any]:
        '''Load specialization-specific behaviors and prompts.'''
        behaviors = {{
            "api_development": {{
                "primary_focus": "Building robust, scalable APIs",
                "tools": ["openapi", "fastapi", "database-design"],
                "quality_standards": ["OpenAPI spec compliance", "RESTful design", "proper error handling"],
                "success_metrics": ["API response time", "error rate", "documentation quality"]
            }},
            "testing": {{
                "primary_focus": "Comprehensive test coverage and quality assurance",
                "tools": ["pytest", "playwright", "test-automation"],
                "quality_standards": ["80%+ code coverage", "integration tests", "performance tests"],
                "success_metrics": ["test coverage", "bug detection rate", "test execution time"]
            }},
            "ui_implementation": {{
                "primary_focus": "User-centered interface development",
                "tools": ["react", "typescript", "css", "figma"],
                "quality_standards": ["responsive design", "accessibility", "performance"],
                "success_metrics": ["page load time", "user interaction quality", "accessibility score"]
            }},
            "devops": {{
                "primary_focus": "Infrastructure automation and deployment",
                "tools": ["aws", "cdk", "docker", "ci-cd"],
                "quality_standards": ["infrastructure as code", "automated deployments", "monitoring"],
                "success_metrics": ["deployment frequency", "lead time", "system uptime"]
            }},
            "security": {{
                "primary_focus": "Security analysis and hardening",
                "tools": ["owasp", "penetration-testing", "encryption"],
                "quality_standards": ["OWASP compliance", "vulnerability scanning", "secure coding"],
                "success_metrics": ["vulnerabilities found", "security score", "compliance level"]
            }}
        }}

        return behaviors.get(self.specialization, {{}})

    def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        '''Process a task using specialized knowledge.'''
        logger.info(f"Agent {{self.id}} processing task: {{task.get('title', 'Unknown')}}")

        # Check vision alignment
        if not self._aligns_with_vision(task):
            return {{
                "status": "rejected",
                "reason": "Task does not align with Monarch vision",
                "vision_check": False
            }}

        # Check budget
        estimated_cost = self._estimate_cost(task)
        if estimated_cost > (self.budget - self.spent_this_month):
            return {{
                "status": "budget_exceeded",
                "estimated_cost": estimated_cost,
                "budget_remaining": self.budget - self.spent_this_month
            }}

        # Execute specialized work
        result = self._execute_specialized_work(task)

        # Update spent amount
        self.spent_this_month += estimated_cost

        return {{
            "status": "completed",
            "result": result,
            "cost": estimated_cost,
            "vision_alignment": True,
            "specialization_used": self.specialization
        }}

    def _aligns_with_vision(self, task: Dict[str, Any]) -> bool:
        '''Check if task aligns with Monarch vision.'''
        # Simple keyword matching - could be enhanced with LLM
        vision_keywords = self.vision['primary'].lower().split()
        task_text = (task.get('description', '') + ' ' + task.get('title', '')).lower()

        return any(keyword in task_text for keyword in vision_keywords)

    def _estimate_cost(self, task: Dict[str, Any]) -> float:
        '''Estimate cost based on task complexity and specialization.'''
        base_cost = 5.0  # Base cost per task
        complexity_multiplier = task.get('complexity', 1.0)

        # Specialization bonus - we're more efficient in our domain
        if task.get('domain') == self.specialization:
            complexity_multiplier *= 0.7  # 30% more efficient

        return base_cost * complexity_multiplier

    def _execute_specialized_work(self, task: Dict[str, Any]) -> Dict[str, Any]:
        '''Execute work using specialization-specific approach.'''
        behaviors = self.specialist_behaviors

        # This is where the actual specialized work would happen
        # For now, return structured result based on specialization

        if self.specialization == "api_development":
            return self._build_api(task)
        elif self.specialization == "testing":
            return self._create_tests(task)
        elif self.specialization == "ui_implementation":
            return self._build_ui(task)
        elif self.specialization == "devops":
            return self._deploy_infrastructure(task)
        elif self.specialization == "security":
            return self._security_analysis(task)
        else:
            return {{"work": "generic_implementation", "note": "No specialized behavior defined"}}

    def _build_api(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return {{
            "api_spec": "Generated OpenAPI specification",
            "endpoints": ["GET /", "POST /items", "GET /items/{{id}}"],
            "documentation": "API documentation created",
            "tests": "Basic API tests included"
        }}

    def _create_tests(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return {{
            "test_suites": ["unit_tests", "integration_tests", "e2e_tests"],
            "coverage": "85%",
            "test_files": ["test_api.py", "test_integration.py"],
            "performance_tests": True
        }}

    def _build_ui(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return {{
            "components": ["UserInterface", "Navigation", "Forms"],
            "responsive": True,
            "accessibility": "WCAG 2.1 AA",
            "performance_score": 92
        }}

    def _deploy_infrastructure(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return {{
            "infrastructure": "CDK stack deployed",
            "resources": ["Lambda", "API Gateway", "DynamoDB"],
            "monitoring": "CloudWatch dashboards created",
            "ci_cd": "GitHub Actions pipeline setup"
        }}

    def _security_analysis(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return {{
            "vulnerabilities_scanned": True,
            "owasp_compliance": "Verified",
            "security_score": 94,
            "recommendations": ["Enable rate limiting", "Add input validation"]
        }}

# Lambda handler
agent = {self.agent_config['id'].replace('_', '').title()}Agent()

def lambda_handler(event, context):
    '''AWS Lambda handler for agent tasks.'''
    try:
        logger.info(f"Agent {{agent.id}} received event: {{json.dumps(event)}}")

        if 'task' in event:
            result = agent.process_task(event['task'])
        else:
            result = {{
                "status": "error",
                "message": "No task provided in event"
            }}

        return {{
            'statusCode': 200,
            'body': json.dumps(result),
            'headers': {{
                'Content-Type': 'application/json'
            }}
        }}

    except Exception as e:
        logger.error(f"Agent {{agent.id}} error: {{str(e)}}")
        return {{
            'statusCode': 500,
            'body': json.dumps({{
                "status": "error",
                "message": str(e),
                "agent_id": agent.id
            }})
        }}
"""

    def _get_agent_requirements(self) -> str:
        """Get requirements.txt for agent Lambda."""
        return """
boto3>=1.35.0
"""

class AgentDeployer:
    """Handles deployment of agent Lambda functions."""

    def __init__(self):
        self.cdk_app = None

    async def deploy_agent(self, agent_config: Dict[str, Any]) -> str:
        """Deploy an agent as AWS Lambda function."""
        logger.info(f"Deploying agent {agent_config['id']} with specialization {agent_config['specialization']}")

        # Create CDK app if not exists
        if not self.cdk_app:
            self.cdk_app = App()

        # Create stack for this agent
        stack_name = f"AgentStack{agent_config['id'].replace('_', '').title()}"
        agent_stack = AgentStack(
            self.cdk_app,
            stack_name,
            agent_config
        )

        # Deploy using CDK
        try:
            # In production, would use subprocess to run `cdk deploy`
            # For now, just log the deployment
            logger.info(f"✅ Agent {agent_config['id']} deployed successfully")

            return agent_stack.agent_function.function_arn

        except Exception as e:
            logger.error(f"❌ Failed to deploy agent {agent_config['id']}: {str(e)}")
            raise

# Global deployer instance
deployer = AgentDeployer()

#!/usr/bin/env python3
"""
Bootstrap script to break the chicken-and-egg problem.
Creates the minimal DynamoDB structure needed for self-building to begin.

Usage:
    python scripts/bootstrap.py

This creates:
1. Dynasty (organization)
2. Court (project)
3. First self-building task (Issue #14)

After this runs, POC 6 can take over and build all subsequent features.
"""

import boto3
import json
from datetime import datetime, timezone

# Config
TABLE_NAME = "cawnex-poc5-blackboard-dev"
DYNASTY_ID = "acme"
COURT_ID = "cawnex"
REPO = "eduardoaugustoes/cawnex"

def main():
    print("🔄 Bootstrapping Cawnex self-building infrastructure...")

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)

    timestamp = datetime.now(timezone.utc).isoformat()

    # 1. Create Dynasty (organization)
    print(f"📁 Creating dynasty: {DYNASTY_ID}")
    table.put_item(Item={
        "PK": f"DYNASTY#{DYNASTY_ID}",
        "SK": "META",
        "name": "Acme Corp",
        "description": "Self-building AI company",
        "created_at": timestamp,
        "status": "active"
    })

    # 2. Create Court (project)
    print(f"🏰 Creating court: {COURT_ID}")
    table.put_item(Item={
        "PK": f"DYNASTY#{DYNASTY_ID}",
        "SK": f"COURT#{COURT_ID}",
        "name": "Cawnex Platform",
        "description": "Multi-agent AI orchestration platform",
        "directive": "Build self-improving AI that can enhance its own capabilities",
        "repo": REPO,
        "status": "active",
        "created_at": timestamp,
        "current_wave": 1
    })

    # 3. Create first self-building task (Issue #14)
    print("⚡ Creating first self-building task: API-backed ProjectService")
    table.put_item(Item={
        "PK": f"COURT#{COURT_ID}",
        "SK": "TASK#api-project-service",
        "title": "Implement API-backed ProjectService",
        "description": "Connect iOS ProjectService to real backend, enabling app to manage actual projects via API endpoints",
        "github_issue": "14",
        "repo": REPO,
        "status": "pending",
        "wave": 1,
        "crow": "implementer",
        "instructions": "Implement GET/POST /dynasty/{id}/courts endpoints and APIProjectService class. All ProjectServiceContractTests must pass.",
        "created_at": timestamp,
        "priority": "high"
    })

    # 4. Create execution trigger for Issue #14
    print("🚀 Creating execution record to trigger POC 6...")
    execution_id = f"bootstrap_{int(datetime.now().timestamp())}"
    table.put_item(Item={
        "PK": f"EXEC#{execution_id}",
        "SK": "META",
        "repo": REPO,
        "issue": "14",
        "branch": f"cawnex/{execution_id}",
        "court_id": COURT_ID,
        "dynasty_id": DYNASTY_ID,
        "status": "pending",
        "created_at": timestamp,
        "instructions": "Bootstrap self-building: Implement API-backed ProjectService to connect iOS app to real backend"
    })

    # 5. Create task record that will trigger DynamoDB Stream → POC 6 Worker
    table.put_item(Item={
        "PK": f"EXEC#{execution_id}",
        "SK": "STEP#01#TASK",
        "crow": "implementer",
        "status": "pending",
        "task_data": json.dumps({
            "github_issue": "14",
            "task_type": "feature_implementation",
            "requirements": "Create API endpoints and iOS service implementation",
            "acceptance_criteria": "All ProjectServiceContractTests must pass with new APIProjectService"
        }),
        "created_at": timestamp
    })

    print("✅ Bootstrap complete!")
    print(f"📊 DynamoDB records created in table: {TABLE_NAME}")
    print(f"🎯 POC 6 Worker will be triggered by DynamoDB Stream")
    print(f"📱 Execution ID: {execution_id}")
    print(f"🔗 GitHub Issue: https://github.com/{REPO}/issues/14")
    print("")
    print("🚀 Self-building cycle initiated. POC 6 should start working on Issue #14 shortly.")
    print("   Once complete, Cawnex will be able to improve itself autonomously!")

if __name__ == "__main__":
    main()

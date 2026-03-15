"""Tests for MemoryStore — DynamoDB-backed agent memory."""

from __future__ import annotations

from murder.blackboard import Blackboard
from murder.memory_store import MemoryStore


TENANT = "test-tenant"
PROJECT = "test-project"


def test_write_and_read_memory(dynamodb_table: object) -> None:
    blackboard = Blackboard(dynamodb_table)
    memory_store = MemoryStore(blackboard)

    memory_store.write_memory(TENANT, PROJECT, "agent#implementer", "- [IMPL] Added auth middleware")

    content = memory_store.read_memory(TENANT, PROJECT, "agent#implementer")
    assert content == "- [IMPL] Added auth middleware"


def test_read_nonexistent_returns_empty(dynamodb_table: object) -> None:
    blackboard = Blackboard(dynamodb_table)
    memory_store = MemoryStore(blackboard)

    content = memory_store.read_memory(TENANT, PROJECT, "agent#planner")
    assert content == ""


def test_read_all_agent_memories(dynamodb_table: object) -> None:
    blackboard = Blackboard(dynamodb_table)
    memory_store = MemoryStore(blackboard)

    memory_store.write_memory(TENANT, PROJECT, "agent#planner", "- [PLAN] decomposed into 3 tasks")
    memory_store.write_memory(TENANT, PROJECT, "agent#implementer", "- [IMPL] changed app.js, routes.js")
    memory_store.write_memory(TENANT, PROJECT, "agent#reviewer", "- [REVIEW] missing error handling")

    memories = memory_store.read_all_agent_memories(TENANT, PROJECT)

    assert memories["planner"] == "- [PLAN] decomposed into 3 tasks"
    assert memories["implementer"] == "- [IMPL] changed app.js, routes.js"
    assert memories["reviewer"] == "- [REVIEW] missing error handling"


def test_read_project_memory_concatenates(dynamodb_table: object) -> None:
    blackboard = Blackboard(dynamodb_table)
    memory_store = MemoryStore(blackboard)

    memory_store.write_memory(TENANT, PROJECT, "project#conventions", "- Use async/await consistently")
    memory_store.write_memory(TENANT, PROJECT, "project#mistakes", "- Never mutate req.body directly")

    combined = memory_store.read_project_memory(TENANT, PROJECT)

    assert "Use async/await consistently" in combined
    assert "Never mutate req.body directly" in combined
    assert "## Conventions" in combined or "## conventions".title() in combined


def test_overwrite_memory(dynamodb_table: object) -> None:
    blackboard = Blackboard(dynamodb_table)
    memory_store = MemoryStore(blackboard)

    memory_store.write_memory(TENANT, PROJECT, "agent#fixer", "- [FIX] first write")
    memory_store.write_memory(TENANT, PROJECT, "agent#fixer", "- [FIX] second write")

    content = memory_store.read_memory(TENANT, PROJECT, "agent#fixer")
    assert content == "- [FIX] second write"
    assert "first write" not in content

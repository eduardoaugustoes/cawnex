"""Tests for reflection module — learning extraction and memory accumulation."""

from __future__ import annotations

from murder.blackboard import Blackboard
from murder.memory_store import MemoryStore
from murder.reflection import (
    MAX_MEMORY_TOKENS,
    append_learnings,
    extract_learnings,
    reflect_on_crow,
)


TENANT = "test-tenant"
PROJECT = "test-project"


# --- extract_learnings ---


def test_extract_learnings_reviewer_rejected() -> None:
    outcome = {
        "approved": False,
        "blocking_issues": ["Missing error handling in auth route", "No test coverage for /login"],
    }
    learnings = extract_learnings("reviewer", outcome, "completed")

    assert len(learnings) == 2
    assert any("Missing error handling" in l for l in learnings)
    assert any("No test coverage" in l for l in learnings)
    assert all(l.startswith("[REVIEW]") for l in learnings)


def test_extract_learnings_reviewer_approved() -> None:
    outcome = {
        "approved": True,
        "non_blocking_issues": ["Consider extracting validation logic", "Add JSDoc to public functions"],
    }
    learnings = extract_learnings("reviewer", outcome, "completed")

    assert len(learnings) == 1
    assert learnings[0].startswith("[QUALITY]")
    assert "Consider extracting" in learnings[0]


def test_extract_learnings_reviewer_approved_no_suggestions() -> None:
    outcome = {"approved": True, "non_blocking_issues": []}
    learnings = extract_learnings("reviewer", outcome, "completed")
    assert learnings == []


def test_extract_learnings_implementer() -> None:
    outcome = {
        "files_changed": ["src/app.js", "src/routes/auth.js"],
        "summary": "Implemented JWT middleware with token validation",
    }
    learnings = extract_learnings("implementer", outcome, "completed")

    assert len(learnings) == 1
    assert learnings[0].startswith("[IMPL]")
    assert "JWT middleware" in learnings[0]
    assert "src/app.js" in learnings[0]


def test_extract_learnings_implementer_no_files() -> None:
    outcome = {"files_changed": [], "summary": "Nothing changed"}
    learnings = extract_learnings("implementer", outcome, "completed")
    assert learnings == []


def test_extract_learnings_planner() -> None:
    outcome = {
        "tasks": [
            {"name": "Add login endpoint"},
            {"name": "Add JWT middleware"},
            {"name": "Add tests"},
        ]
    }
    learnings = extract_learnings("planner", outcome, "completed")

    assert len(learnings) == 1
    assert learnings[0].startswith("[PLAN]")
    assert "Add login endpoint" in learnings[0]
    assert "Add JWT middleware" in learnings[0]


def test_extract_learnings_planner_no_tasks() -> None:
    outcome = {"tasks": []}
    learnings = extract_learnings("planner", outcome, "completed")
    assert learnings == []


def test_extract_learnings_fixer() -> None:
    outcome = {
        "issues_addressed": ["Missing error handling", "Wrong status code"],
        "files_changed": ["src/routes/auth.js"],
    }
    learnings = extract_learnings("fixer", outcome, "completed")

    assert len(learnings) == 1
    assert learnings[0].startswith("[FIX]")
    assert "Missing error handling" in learnings[0]
    assert "src/routes/auth.js" in learnings[0]


def test_extract_learnings_fixer_no_issues() -> None:
    outcome = {"issues_addressed": [], "files_changed": ["src/app.js"]}
    learnings = extract_learnings("fixer", outcome, "completed")
    assert learnings == []


def test_extract_learnings_failed_crow() -> None:
    outcome = {"error": "Git push rejected: branch protection rule"}
    learnings = extract_learnings("implementer", outcome, "failed")

    assert len(learnings) == 1
    assert learnings[0].startswith("[FAILURE]")
    assert "Git push rejected" in learnings[0]


def test_extract_learnings_empty_outcome() -> None:
    learnings = extract_learnings("reviewer", {}, "completed")
    assert learnings == []


# --- append_learnings ---


def test_append_learnings_to_empty() -> None:
    result = append_learnings("", ["[PLAN] Decomposed into: task A, task B"])
    assert result == "- [PLAN] Decomposed into: task A, task B"


def test_append_learnings_to_existing() -> None:
    existing = "- [PLAN] First learning"
    result = append_learnings(existing, ["[IMPL] Second learning"])

    lines = result.split("\n")
    assert len(lines) == 2
    assert "First learning" in lines[0]
    assert "Second learning" in lines[1]


def test_append_learnings_prunes_oldest() -> None:
    # Build content that is slightly over budget when new learnings are added
    long_learning = "x" * 200  # ~50 tokens each
    existing_lines = [f"- [OLD] learning {i}: {long_learning}" for i in range(8)]
    existing = "\n".join(existing_lines)

    # Verify it's already near budget
    new_learning = f"[NEW] fresh learning: {'y' * 200}"
    result = append_learnings(existing, [new_learning], max_tokens=MAX_MEMORY_TOKENS)

    result_tokens = len(result) // 4
    assert result_tokens <= MAX_MEMORY_TOKENS
    # The newest learning must be preserved
    assert "[NEW] fresh learning" in result


def test_append_no_learnings_returns_unchanged() -> None:
    existing = "- [PLAN] Some learning"
    result = append_learnings(existing, [])
    assert result == existing


# --- reflect_on_crow (integration with DynamoDB) ---


def test_reflect_on_crow_writes_to_store(dynamodb_table: object) -> None:
    blackboard = Blackboard(dynamodb_table)
    memory_store = MemoryStore(blackboard)

    outcome = {
        "approved": False,
        "blocking_issues": ["Unhandled promise rejection in middleware"],
    }
    learnings = reflect_on_crow(
        memory_store, TENANT, PROJECT, "reviewer", outcome, "completed"
    )

    assert len(learnings) == 1
    assert "[REVIEW]" in learnings[0]

    stored = memory_store.read_memory(TENANT, PROJECT, "agent#reviewer")
    assert "Unhandled promise rejection" in stored


def test_reflect_on_crow_no_learnings_skips_write(dynamodb_table: object) -> None:
    blackboard = Blackboard(dynamodb_table)
    memory_store = MemoryStore(blackboard)

    # Reviewer approved with no suggestions — no learnings expected
    outcome = {"approved": True, "non_blocking_issues": []}
    learnings = reflect_on_crow(
        memory_store, TENANT, PROJECT, "reviewer", outcome, "completed"
    )

    assert learnings == []
    # No memory item should have been written
    stored = memory_store.read_memory(TENANT, PROJECT, "agent#reviewer")
    assert stored == ""


def test_reflect_accumulates_across_calls(dynamodb_table: object) -> None:
    blackboard = Blackboard(dynamodb_table)
    memory_store = MemoryStore(blackboard)

    reflect_on_crow(
        memory_store, TENANT, PROJECT, "fixer",
        {"issues_addressed": ["Missing null check"], "files_changed": ["app.js"]},
        "completed",
    )
    reflect_on_crow(
        memory_store, TENANT, PROJECT, "fixer",
        {"issues_addressed": ["Wrong status code"], "files_changed": ["routes.js"]},
        "completed",
    )

    stored = memory_store.read_memory(TENANT, PROJECT, "agent#fixer")
    assert "Missing null check" in stored
    assert "Wrong status code" in stored

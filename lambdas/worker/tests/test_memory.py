"""Tests for memory synthesis and injection."""

from __future__ import annotations

import pytest

from worker.memory import inject_memory, synthesize_memory


class TestSynthesizeMemory:
    def test_empty_list_returns_empty(self) -> None:
        assert synthesize_memory([]) == ""

    def test_planner_entry(self) -> None:
        entries = [
            {
                "crow_type": "planner",
                "tasks": [{"name": "add endpoint"}, {"name": "add test"}],
                "context_files": ["src/app.py", "tests/test_app.py"],
                "summary": "planned 2 tasks",
            }
        ]
        result = synthesize_memory(entries)
        assert "## Project Memory" in result
        assert "Planner: planned 2 tasks" in result
        assert "add endpoint" in result
        assert "src/app.py" in result

    def test_implementer_entry(self) -> None:
        entries = [
            {
                "crow_type": "implementer",
                "files_changed": ["src/routes.py", "tests/test_routes.py"],
                "commit_message": "feat: add health endpoint",
                "summary": "implemented health",
            }
        ]
        result = synthesize_memory(entries)
        assert "Implementer: changed 2 files" in result
        assert "feat: add health endpoint" in result

    def test_reviewer_approved(self) -> None:
        entries = [
            {
                "crow_type": "reviewer",
                "approved": True,
                "summary": "code looks good",
            }
        ]
        result = synthesize_memory(entries)
        assert "Reviewer: approved" in result
        assert "code looks good" in result

    def test_reviewer_rejected(self) -> None:
        entries = [
            {
                "crow_type": "reviewer",
                "approved": False,
                "issues": ["missing error handling", "no test for edge case"],
                "suggestions": ["add try/catch"],
                "summary": "needs fixes",
            }
        ]
        result = synthesize_memory(entries)
        assert "Reviewer: rejected with 2 issues" in result
        assert "missing error handling" in result

    def test_fixer_entry(self) -> None:
        entries = [
            {
                "crow_type": "fixer",
                "files_changed": ["src/routes.py"],
                "issues_addressed": ["error handling", "edge case test"],
                "summary": "fixed both issues",
            }
        ]
        result = synthesize_memory(entries)
        assert "Fixer: addressed 2 issues" in result

    def test_full_pipeline(self) -> None:
        entries = [
            {
                "crow_type": "planner",
                "tasks": [{"name": "health"}],
                "context_files": ["src/app.py"],
                "summary": "plan",
            },
            {
                "crow_type": "implementer",
                "files_changed": ["src/routes.py"],
                "commit_message": "feat: health",
                "summary": "done",
            },
            {
                "crow_type": "reviewer",
                "approved": True,
                "summary": "lgtm",
            },
        ]
        result = synthesize_memory(entries)
        assert result.startswith("## Project Memory")
        lines = result.strip().split("\n")
        # Header + 3 bullet lines
        assert len(lines) == 4
        assert "Planner" in lines[1]
        assert "Implementer" in lines[2]
        assert "Reviewer" in lines[3]

    def test_unknown_crow_type_with_summary(self) -> None:
        entries = [{"crow_type": "scout", "summary": "explored codebase"}]
        result = synthesize_memory(entries)
        assert "scout: explored codebase" in result

    def test_unknown_crow_type_without_summary(self) -> None:
        entries = [{"crow_type": "scout"}]
        result = synthesize_memory(entries)
        assert result == ""


class TestInjectMemory:
    def test_appends_memory_to_prompt(self) -> None:
        prompt = "You are an implementer."
        memory = "## Project Memory\n- Planner: 2 tasks"
        result = inject_memory(prompt, memory)
        assert result == "You are an implementer.\n\n## Project Memory\n- Planner: 2 tasks"

    def test_noop_when_empty(self) -> None:
        prompt = "You are an implementer."
        assert inject_memory(prompt, "") == prompt

    def test_preserves_original_prompt(self) -> None:
        prompt = "System prompt with\nmultiple lines."
        memory = "## Project Memory\n- bullet"
        result = inject_memory(prompt, memory)
        assert result.startswith(prompt)
        assert result.endswith(memory)

"""Tests for context builder — artifact chain glue."""

import json

from murder.enums import CrowType
from murder.context_builder import build_instructions, build_planner_instructions


class TestBuildPlannerInstructions:
    def test_includes_directive_and_description(self) -> None:
        result = build_planner_instructions("Add auth", "JWT authentication")
        assert "Add auth" in result
        assert "JWT authentication" in result
        assert "planner" in result.lower()

    def test_mentions_tasks_format(self) -> None:
        result = build_planner_instructions("Add auth", "JWT")
        assert "tasks" in result


class TestBuildImplementerInstructions:
    def test_includes_all_tasks(self) -> None:
        outcome = {
            "tasks": [
                {
                    "name": "create endpoint",
                    "description": "Add /login POST",
                    "files_to_modify": ["src/auth.py"],
                    "context_files": ["src/config.py"],
                },
                {
                    "name": "add test",
                    "description": "Test the endpoint",
                    "files_to_modify": ["tests/test_auth.py"],
                    "context_files": ["src/auth.py"],
                },
            ]
        }
        result = build_instructions(CrowType.IMPLEMENTER, outcome, "JWT auth")
        assert "create endpoint" in result
        assert "add test" in result
        assert "src/auth.py" in result
        assert "tests/test_auth.py" in result
        assert "JWT auth" in result

    def test_deduplicates_context_files(self) -> None:
        outcome = {
            "tasks": [
                {"name": "t1", "context_files": ["a.py", "b.py"]},
                {"name": "t2", "context_files": ["b.py", "c.py"]},
            ]
        }
        result = build_instructions(CrowType.IMPLEMENTER, outcome, "desc")
        parsed = json.loads(result.split("Task details:\n")[1])
        assert parsed["context_files"] == ["a.py", "b.py", "c.py"]

    def test_handles_empty_tasks(self) -> None:
        result = build_instructions(CrowType.IMPLEMENTER, {"tasks": []}, "desc")
        assert "implementer" in result.lower()


class TestBuildReviewerInstructions:
    def test_asks_for_review(self) -> None:
        result = build_instructions(CrowType.REVIEWER, {}, "JWT auth")
        assert "review" in result.lower()
        assert "approved" in result
        assert "JWT auth" in result

    def test_includes_planner_tasks_when_provided(self) -> None:
        planner_outcome = {
            "tasks": [
                {"name": "add endpoint", "description": "GET /health"},
                {"name": "add test", "description": "Test /health"},
            ]
        }
        result = build_instructions(
            CrowType.REVIEWER, {}, "JWT auth", planner_outcome=planner_outcome
        )
        assert "add endpoint" in result
        assert "add test" in result
        assert "Planned tasks" in result

    def test_works_without_planner_outcome(self) -> None:
        result = build_instructions(CrowType.REVIEWER, {}, "JWT auth")
        assert "Planned tasks" not in result
        assert "approved" in result


class TestBuildFixerInstructions:
    def test_includes_issues_and_suggestions(self) -> None:
        outcome = {
            "issues": ["missing error handling"],
            "suggestions": ["add logging"],
        }
        result = build_instructions(CrowType.FIXER, outcome, "JWT auth")
        assert "missing error handling" in result
        assert "add logging" in result
        assert "JWT auth" in result

    def test_handles_none_outcome(self) -> None:
        result = build_instructions(CrowType.FIXER, None, "desc")
        assert "fixer" in result.lower()

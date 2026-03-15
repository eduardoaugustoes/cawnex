"""Tests for context builder — artifact chain glue."""

import json

from murder.enums import CrowType
from murder.context_builder import (
    build_instructions,
    build_planner_instructions,
    build_planner_split_instructions,
)


class TestBuildPlannerInstructions:
    def test_includes_directive_and_description(self) -> None:
        result = build_planner_instructions("Add auth", "JWT authentication")
        assert "Add auth" in result
        assert "JWT authentication" in result
        assert "planner" in result.lower()

    def test_mentions_tasks_format(self) -> None:
        result = build_planner_instructions("Add auth", "JWT")
        assert "tasks" in result

    def test_includes_estimated_hours_in_output_contract(self) -> None:
        result = build_planner_instructions("Add auth", "JWT")
        assert "estimated_hours" in result


class TestBuildPlannerSplitInstructions:
    def test_mentions_oversized_task_names(self) -> None:
        oversized = [
            {"name": "Implement JWT auth", "estimated_hours": 16},
            {"name": "Setup CI/CD pipeline", "estimated_hours": 12},
        ]
        result = build_planner_split_instructions(oversized, "Build auth system", "JWT MVI")
        assert "Implement JWT auth" in result
        assert "16h" in result
        assert "Setup CI/CD pipeline" in result
        assert "12h" in result

    def test_includes_original_directive_and_description(self) -> None:
        oversized = [{"name": "Big task", "estimated_hours": 10}]
        result = build_planner_split_instructions(oversized, "Build auth system", "JWT MVI")
        assert "Build auth system" in result
        assert "JWT MVI" in result

    def test_instructs_to_produce_tasks_within_limit(self) -> None:
        oversized = [{"name": "Big task", "estimated_hours": 10}]
        result = build_planner_split_instructions(oversized, "directive", "desc")
        assert "8" in result
        assert "tasks" in result.lower()


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


class TestBuildReviewerInstructionsWithFixerContext:
    def test_includes_fixer_context_when_provided(self) -> None:
        fixer_outcome = {
            "summary": "Added null guard and wrote tests",
            "files_changed": ["src/handler.py", "tests/test_handler.py"],
            "issues_addressed": ["missing null check", "no test coverage"],
        }
        result = build_instructions(
            CrowType.REVIEWER, {}, "JWT auth", fixer_outcome=fixer_outcome
        )
        assert "Recent Fixes Applied" in result
        assert "Added null guard and wrote tests" in result
        assert "src/handler.py" in result
        assert "missing null check" in result

    def test_no_fixer_context_when_not_provided(self) -> None:
        result = build_instructions(CrowType.REVIEWER, {}, "JWT auth")
        assert "Recent Fixes Applied" not in result


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

    def test_fixer_instructions_without_fix_history(self) -> None:
        outcome = {"issues": ["null pointer"], "suggestions": []}
        result = build_instructions(CrowType.FIXER, outcome, "JWT auth")
        assert "Previous Fix Attempts" not in result
        assert "null pointer" in result

    def test_fixer_instructions_with_fix_history(self) -> None:
        outcome = {"issues": ["still broken"], "suggestions": []}
        fix_history = [
            {
                "iteration": 1,
                "reviewer_issues": ["null pointer", "missing test"],
                "fixer_summary": "Added null check in handler",
                "fixer_files_changed": ["src/handler.py"],
            }
        ]
        result = build_instructions(CrowType.FIXER, outcome, "JWT auth", fix_history=fix_history)
        assert "Previous Fix Attempts" in result
        assert "Do NOT repeat approaches that already failed" in result
        assert "Attempt 1" in result
        assert "null pointer" in result
        assert "missing test" in result
        assert "Added null check in handler" in result
        assert "src/handler.py" in result
        assert "Reviewer still found issues" in result
        assert "still broken" in result

    def test_fixer_uses_blocking_issues_when_present(self) -> None:
        """Fixer uses blocking_issues when available, falls back to issues."""
        outcome = {
            "blocking_issues": ["SQL injection at db.py:42"],
            "non_blocking_issues": ["rename x to user_id"],
            "issues": ["SQL injection at db.py:42", "rename x to user_id"],
            "suggestions": [],
        }
        result = build_instructions(CrowType.FIXER, outcome, "JWT auth")
        assert "SQL injection at db.py:42" in result
        assert "blocking_issues" in result

    def test_fixer_falls_back_to_issues_when_blocking_issues_absent(self) -> None:
        outcome = {
            "issues": ["missing error handling"],
            "suggestions": [],
        }
        result = build_instructions(CrowType.FIXER, outcome, "JWT auth")
        assert "missing error handling" in result

    def test_fixer_includes_non_blocking_as_informational(self) -> None:
        outcome = {
            "blocking_issues": ["SQL injection"],
            "non_blocking_issues": ["rename x to y"],
            "issues": ["SQL injection", "rename x to y"],
        }
        result = build_instructions(CrowType.FIXER, outcome, "JWT auth")
        assert "rename x to y" in result
        assert "do NOT prioritize" in result

    def test_fixer_instructions_with_multiple_history_entries(self) -> None:
        outcome = {"issues": ["still wrong"], "suggestions": []}
        fix_history = [
            {
                "iteration": 1,
                "reviewer_issues": ["bug A"],
                "fixer_summary": "tried approach X",
                "fixer_files_changed": ["a.py"],
            },
            {
                "iteration": 2,
                "reviewer_issues": ["bug B"],
                "fixer_summary": "tried approach Y",
                "fixer_files_changed": ["b.py"],
            },
        ]
        result = build_instructions(CrowType.FIXER, outcome, "desc", fix_history=fix_history)
        assert "Attempt 1" in result
        assert "Attempt 2" in result
        assert "tried approach X" in result
        assert "tried approach Y" in result

"""Tests for executor — full flow with mocked git + Claude."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from worker.claude import ClaudeResult
from worker.config import ExecutionConfig
from worker.enums import CrowType
from worker.executor import _build_failed, _build_outcome, execute
from worker.logging import StructuredLogger


def _make_snapshot(**overrides: object) -> dict:
    base = {
        "crow_type": "implementer",
        "crow_id": "cr_impl_01",
        "repo": "owner/repo",
        "branch": "cawnex/w001-auth",
        "instructions": "Implement OAuth middleware",
        "budget_remaining": 5_000_000,
    }
    base.update(overrides)
    return base


def _make_claude_result(raw: str = '{"changes": [], "summary": "done"}') -> ClaudeResult:
    return ClaudeResult(
        raw_output=raw,
        tokens_in=100,
        tokens_out=50,
        duration_ms=500,
        model="test",
    )


def _make_logger() -> StructuredLogger:
    return StructuredLogger(component="test", tenant="acme", project="proj")


def _make_config() -> ExecutionConfig:
    return ExecutionConfig(efs_mount="/efs", github_token="test-token")


class TestBuildOutcome:
    def test_planner_outcome(self) -> None:
        parsed = {"tasks": [{"name": "t1"}], "context_files": ["a.py"], "summary": "plan"}
        result = _build_outcome(CrowType.PLANNER, parsed)
        assert result["tasks"] == [{"name": "t1"}]
        assert result["context_files"] == ["a.py"]
        assert result["summary"] == "plan"

    def test_implementer_outcome(self) -> None:
        parsed = {
            "changes": [{"path": "a.py"}, {"path": "b.py"}],
            "commit_message": "feat: auth",
            "summary": "done",
        }
        result = _build_outcome(CrowType.IMPLEMENTER, parsed)
        assert result["files_changed"] == ["a.py", "b.py"]
        assert result["commit_message"] == "feat: auth"

    def test_reviewer_outcome(self) -> None:
        parsed = {
            "approved": True,
            "blocking_issues": [],
            "non_blocking_issues": ["rename x to user_id"],
            "issues": ["rename x to user_id"],
            "suggestions": ["nice"],
            "summary": "lgtm",
        }
        result = _build_outcome(CrowType.REVIEWER, parsed)
        assert result["approved"] is True
        assert result["blocking_issues"] == []
        assert result["non_blocking_issues"] == ["rename x to user_id"]
        assert result["issues"] == ["rename x to user_id"]
        assert result["suggestions"] == ["nice"]

    def test_reviewer_outcome_defaults_empty_lists_when_fields_absent(self) -> None:
        parsed = {"approved": False, "issues": ["bug"], "suggestions": [], "summary": "needs fix"}
        result = _build_outcome(CrowType.REVIEWER, parsed)
        assert result["blocking_issues"] == []
        assert result["non_blocking_issues"] == []
        assert result["issues"] == ["bug"]

    def test_fixer_outcome(self) -> None:
        parsed = {
            "changes": [{"path": "fix.py"}],
            "commit_message": "fix: null check",
            "summary": "fixed",
            "issues_addressed": ["null check"],
        }
        result = _build_outcome(CrowType.FIXER, parsed)
        assert result["issues_addressed"] == ["null check"]

    def test_empty_parsed(self) -> None:
        result = _build_outcome(CrowType.IMPLEMENTER, {})
        assert result["files_changed"] == []
        assert result["summary"] == ""


class TestBuildFailed:
    def test_returns_valid_contract(self) -> None:
        result = _build_failed(CrowType.IMPLEMENTER, "timeout")
        assert result["status"] == "failed"
        assert result["outcome"]["error"] == "timeout"
        assert result["completed_at"]
        assert result["cost"]["credits"] == 0


class TestExecute:
    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch("worker.executor.gather_planner_context", return_value="context")
    def test_planner_flow(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        mock_claude.return_value = _make_claude_result(
            '{"tasks": [{"name": "auth"}], "context_files": ["a.py"], "summary": "plan"}'
        )
        snapshot = _make_snapshot(crow_type="planner")
        result = execute(snapshot, logger=_make_logger(), config=_make_config())

        assert result["status"] == "completed"
        assert result["outcome"]["tasks"] == [{"name": "auth"}]
        assert result["cost"]["tokens_in"] == 100
        mock_cleanup.assert_called_once()

    @patch("worker.executor.create_pr")
    @patch("worker.executor.commit_and_push", return_value="abc123")
    @patch("worker.executor.apply_changes", return_value=["src/auth.py"])
    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch("worker.executor.gather_implementer_context", return_value="context")
    def test_implementer_flow_with_pr(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
        mock_apply: MagicMock,
        mock_push: MagicMock,
        mock_pr: MagicMock,
    ) -> None:
        mock_claude.return_value = _make_claude_result(
            '{"changes": [{"path": "src/auth.py", "action": "create", "content": "code"}], '
            '"commit_message": "feat: auth", "summary": "implemented auth"}'
        )
        mock_pr.return_value = {"number": 42, "html_url": "https://github.com/o/r/pull/42"}

        result = execute(_make_snapshot(), logger=_make_logger(), config=_make_config())

        assert result["status"] == "completed"
        assert result["git_commit"] == "abc123"
        assert result["pr"]["number"] == 42
        mock_apply.assert_called_once()
        mock_push.assert_called_once()

    @patch("worker.executor._build_git_diff", return_value=("diff content", ["file.py"]))
    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch("worker.executor.gather_reviewer_context", return_value="diff context")
    def test_reviewer_flow(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
        mock_diff: MagicMock,
    ) -> None:
        mock_claude.return_value = _make_claude_result(
            '{"approved": false, "issues": ["bug at line 5"], "suggestions": [], "summary": "needs fix"}'
        )
        snapshot = _make_snapshot(crow_type="reviewer")
        result = execute(snapshot, logger=_make_logger(), config=_make_config())

        assert result["status"] == "completed"
        assert result["outcome"]["approved"] is False
        assert "git_commit" not in result
        mock_context.assert_called_once_with("/wt", "diff content", ["file.py"])

    @patch("worker.executor._build_git_diff", return_value=("diff", ["fix.py"]))
    @patch("worker.executor.commit_and_push", return_value="def456")
    @patch("worker.executor.apply_changes", return_value=["fix.py"])
    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch("worker.executor.gather_fixer_context", return_value="fixer context")
    def test_fixer_flow_no_pr(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
        mock_apply: MagicMock,
        mock_push: MagicMock,
        mock_diff: MagicMock,
    ) -> None:
        mock_claude.return_value = _make_claude_result(
            '{"changes": [{"path": "fix.py", "action": "modify", "content": "fixed"}], '
            '"commit_message": "fix: null check", "summary": "fixed it", '
            '"issues_addressed": ["null check"]}'
        )
        snapshot = _make_snapshot(crow_type="fixer", instructions='{"issues": ["null check"]}')
        result = execute(snapshot, logger=_make_logger(), config=_make_config())

        assert result["status"] == "completed"
        assert result["git_commit"] == "def456"
        assert "pr" not in result

    def test_budget_exhausted_returns_failed(self) -> None:
        snapshot = _make_snapshot(budget_remaining=0)
        result = execute(snapshot, logger=_make_logger(), config=_make_config())
        assert result["status"] == "failed"
        assert "Budget exhausted" in result["outcome"]["error"]

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.ensure_repo", side_effect=RuntimeError("clone failed"))
    def test_git_error_returns_failed(
        self, mock_ensure: MagicMock, mock_cleanup: MagicMock
    ) -> None:
        result = execute(_make_snapshot(), logger=_make_logger(), config=_make_config())
        assert result["status"] == "failed"
        assert "clone failed" in result["outcome"]["error"]

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch("worker.executor.gather_implementer_context", return_value="ctx")
    def test_unparseable_claude_output(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        mock_claude.return_value = _make_claude_result("This is not JSON at all")
        result = execute(_make_snapshot(), logger=_make_logger(), config=_make_config())
        assert result["status"] == "completed"
        assert result["outcome"]["files_changed"] == []

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch("worker.executor.gather_planner_context", return_value="ctx")
    def test_cleanup_called_on_success(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        mock_claude.return_value = _make_claude_result('{"tasks": [], "summary": "ok"}')
        execute(
            _make_snapshot(crow_type="planner"),
            logger=_make_logger(),
            config=_make_config(),
        )
        mock_cleanup.assert_called_once_with("/repo", "/wt")

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude", side_effect=RuntimeError("API error"))
    @patch("worker.executor.gather_planner_context", return_value="ctx")
    def test_cleanup_called_on_error(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        result = execute(
            _make_snapshot(crow_type="planner"),
            logger=_make_logger(),
            config=_make_config(),
        )
        assert result["status"] == "failed"
        mock_cleanup.assert_called_once_with("/repo", "/wt")

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch("worker.executor.gather_planner_context", return_value="ctx")
    def test_timeout_returns_failed(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        import time

        def slow_claude(*args: object, **kwargs: object) -> None:
            time.sleep(5)

        mock_claude.side_effect = slow_claude
        snapshot = _make_snapshot(crow_type="planner", timeout_seconds=1)
        result = execute(snapshot, logger=_make_logger(), config=_make_config())
        assert result["status"] == "failed"
        assert "timeout" in result["outcome"]["error"].lower()
        mock_cleanup.assert_called_once()

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch("worker.executor.gather_implementer_context", return_value="ctx")
    def test_memory_injection_when_enabled(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        mock_claude.return_value = _make_claude_result('{"changes": [], "summary": "done"}')
        config = ExecutionConfig(
            efs_mount="/efs", github_token="test-token", memory_injection_enabled=True
        )
        snapshot = _make_snapshot(
            memory=[
                {
                    "crow_type": "planner",
                    "tasks": [{"name": "health"}],
                    "context_files": ["src/app.py"],
                    "summary": "planned",
                }
            ]
        )
        result = execute(snapshot, logger=_make_logger(), config=config)
        assert result["status"] == "completed"

        # Verify memory was injected into system prompt
        system_prompt = mock_claude.call_args[0][0]
        assert "## Project Memory" in system_prompt
        assert "Planner" in system_prompt

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch("worker.executor.gather_implementer_context", return_value="ctx")
    def test_no_memory_injection_when_disabled(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        mock_claude.return_value = _make_claude_result('{"changes": [], "summary": "done"}')
        config = ExecutionConfig(
            efs_mount="/efs", github_token="test-token", memory_injection_enabled=False
        )
        snapshot = _make_snapshot(
            memory=[{"crow_type": "planner", "tasks": [], "summary": "plan"}]
        )
        result = execute(snapshot, logger=_make_logger(), config=config)
        assert result["status"] == "completed"

        system_prompt = mock_claude.call_args[0][0]
        assert "## Project Memory" not in system_prompt

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch("worker.executor.gather_implementer_context", return_value="ctx")
    def test_no_memory_injection_when_no_entries(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        mock_claude.return_value = _make_claude_result('{"changes": [], "summary": "done"}')
        config = ExecutionConfig(
            efs_mount="/efs", github_token="test-token", memory_injection_enabled=True
        )
        snapshot = _make_snapshot(memory=[])
        result = execute(snapshot, logger=_make_logger(), config=config)
        assert result["status"] == "completed"

        system_prompt = mock_claude.call_args[0][0]
        assert "## Project Memory" not in system_prompt

    def test_config_from_env_fallback(self) -> None:
        """Execute uses ExecutionConfig.from_env() when no config passed."""
        snapshot = _make_snapshot(budget_remaining=0)
        result = execute(snapshot, logger=_make_logger())
        assert result["status"] == "failed"  # budget check before any config use

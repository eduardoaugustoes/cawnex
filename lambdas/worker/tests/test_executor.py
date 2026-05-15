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
    @patch("worker.executor.gather_planner_context", return_value=("context", {"files_read": [], "files_failed": [], "failure_reasons": {}}))
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
    @patch("worker.executor.gather_implementer_context", return_value=("context", {"files_read": [], "files_failed": [], "failure_reasons": {}}))
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
    @patch("worker.executor.gather_reviewer_context", return_value=("diff context", {"files_read": [], "files_failed": [], "failure_reasons": {}}))
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
    @patch("worker.executor.gather_fixer_context", return_value=("fixer context", {"files_read": [], "files_failed": [], "failure_reasons": {}}))
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
    @patch("worker.executor.gather_implementer_context", return_value=("ctx", {"files_read": [], "files_failed": [], "failure_reasons": {}}))
    def test_unparseable_implementer_output_fails_crow(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        """Implementer that produces no parseable `changes` must FAIL the crow,
        not complete with empty output — otherwise Murder advances to reviewer
        and the reviewer sees a phantom diff (see dogfood run 3 incident)."""
        mock_claude.return_value = _make_claude_result("This is not JSON at all")
        result = execute(_make_snapshot(), logger=_make_logger(), config=_make_config())
        assert result["status"] == "failed"
        assert "no file changes" in result["outcome"]["error"]

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch("worker.executor.gather_planner_context", return_value=("ctx", {"files_read": [], "files_failed": [], "failure_reasons": {}}))
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
    @patch("worker.executor.gather_planner_context", return_value=("ctx", {"files_read": [], "files_failed": [], "failure_reasons": {}}))
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
    @patch("worker.executor.gather_planner_context", return_value=("ctx", {"files_read": [], "files_failed": [], "failure_reasons": {}}))
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
    @patch("worker.executor.gather_planner_context", return_value=("ctx", {"files_read": [], "files_failed": [], "failure_reasons": {}}))
    def test_memory_injection_when_enabled(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        # Use planner crow so the empty-changes guard doesn't fire and we
        # don't need to mock apply_changes/commit_and_push for this test.
        mock_claude.return_value = _make_claude_result('{"tasks": [{"name": "x"}], "summary": "ok"}')
        config = ExecutionConfig(
            efs_mount="/efs", github_token="test-token", memory_injection_enabled=True
        )
        snapshot = _make_snapshot(
            crow_type="planner",
            memory=[
                {
                    "crow_type": "planner",
                    "tasks": [{"name": "health"}],
                    "context_files": ["src/app.py"],
                    "summary": "planned",
                }
            ],
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
    @patch("worker.executor.gather_planner_context", return_value=("ctx", {"files_read": [], "files_failed": [], "failure_reasons": {}}))
    def test_no_memory_injection_when_disabled(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        mock_claude.return_value = _make_claude_result('{"tasks": [{"name": "x"}], "summary": "ok"}')
        config = ExecutionConfig(
            efs_mount="/efs", github_token="test-token", memory_injection_enabled=False
        )
        snapshot = _make_snapshot(
            crow_type="planner",
            memory=[{"crow_type": "planner", "tasks": [], "summary": "plan"}],
        )
        result = execute(snapshot, logger=_make_logger(), config=config)
        assert result["status"] == "completed"

        system_prompt = mock_claude.call_args[0][0]
        assert "## Project Memory" not in system_prompt

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch("worker.executor.gather_planner_context", return_value=("ctx", {"files_read": [], "files_failed": [], "failure_reasons": {}}))
    def test_no_memory_injection_when_no_entries(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        mock_claude.return_value = _make_claude_result('{"tasks": [{"name": "x"}], "summary": "ok"}')
        config = ExecutionConfig(
            efs_mount="/efs", github_token="test-token", memory_injection_enabled=True
        )
        snapshot = _make_snapshot(crow_type="planner", memory=[])
        result = execute(snapshot, logger=_make_logger(), config=config)
        assert result["status"] == "completed"

        system_prompt = mock_claude.call_args[0][0]
        assert "## Project Memory" not in system_prompt

    def test_config_from_env_fallback(self) -> None:
        """Execute uses ExecutionConfig.from_env() when no config passed."""
        snapshot = _make_snapshot(budget_remaining=0)
        result = execute(snapshot, logger=_make_logger())
        assert result["status"] == "failed"  # budget check before any config use


class TestToolUseWiring:
    """Implementer crow runs the agentic loop; others stay one-shot."""

    @patch("worker.executor.create_pr")
    @patch("worker.executor.commit_and_push", return_value="abc123")
    @patch("worker.executor.apply_changes", return_value=[])
    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch(
        "worker.executor.gather_implementer_context",
        return_value=("ctx", {"files_read": [], "files_failed": [], "failure_reasons": {}}),
    )
    def test_implementer_invokes_call_claude_with_tools(
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
            '{"changes": [{"path": "x.py", "action": "create", "content": "x = 1\\n"}], '
            '"commit_message": "feat: x", "summary": "done"}'
        )

        execute(_make_snapshot(crow_type="implementer"), logger=_make_logger(), config=_make_config())

        kwargs = mock_claude.call_args.kwargs
        tools = kwargs.get("tools")
        executor = kwargs.get("tool_executor")
        assert tools is not None
        assert len(tools) >= 4  # read_file, glob_files, grep_files, list_dir
        assert executor is not None
        # tool_executor is a WorktreeTools bound to the worktree
        assert executor.worktree_dir == "/wt"

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch(
        "worker.executor.gather_planner_context",
        return_value=("ctx", {"files_read": [], "files_failed": [], "failure_reasons": {}}),
    )
    def test_planner_stays_one_shot(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        mock_claude.return_value = _make_claude_result('{"tasks": []}')

        execute(_make_snapshot(crow_type="planner"), logger=_make_logger(), config=_make_config())

        kwargs = mock_claude.call_args.kwargs
        assert kwargs.get("tools") is None
        assert kwargs.get("tool_executor") is None


class TestEmptyChangesGuard:
    """Implementer/fixer that emits no `changes` must fail explicitly so
    Murder doesn't advance to a phantom-diff reviewer."""

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch(
        "worker.executor.gather_implementer_context",
        return_value=("ctx", {"files_read": [], "files_failed": [], "failure_reasons": {}}),
    )
    def test_implementer_with_no_changes_key_fails(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        # JSON parses but has no `changes` key — this is the dogfood run 3 shape
        mock_claude.return_value = _make_claude_result(
            '{"summary": "I read everything", "commit_message": ""}'
        )
        result = execute(
            _make_snapshot(crow_type="implementer"),
            logger=_make_logger(),
            config=_make_config(),
        )
        assert result["status"] == "failed"
        assert "no file changes" in result["outcome"]["error"]

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch(
        "worker.executor.gather_implementer_context",
        return_value=("ctx", {"files_read": [], "files_failed": [], "failure_reasons": {}}),
    )
    def test_implementer_with_explicit_empty_changes_fails(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        mock_claude.return_value = _make_claude_result(
            '{"changes": [], "summary": "decided not to change anything"}'
        )
        result = execute(
            _make_snapshot(crow_type="implementer"),
            logger=_make_logger(),
            config=_make_config(),
        )
        assert result["status"] == "failed"
        assert "no file changes" in result["outcome"]["error"]

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch(
        "worker.executor.gather_fixer_context",
        return_value=("ctx", {"files_read": [], "files_failed": [], "failure_reasons": {}}),
    )
    @patch("worker.executor._build_git_diff", return_value=("", []))
    def test_fixer_with_no_changes_fails(
        self,
        mock_diff: MagicMock,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        mock_claude.return_value = _make_claude_result(
            '{"summary": "issues unclear"}'
        )
        result = execute(
            _make_snapshot(crow_type="fixer"),
            logger=_make_logger(),
            config=_make_config(),
        )
        assert result["status"] == "failed"
        assert "no file changes" in result["outcome"]["error"]

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch(
        "worker.executor.gather_planner_context",
        return_value=("ctx", {"files_read": [], "files_failed": [], "failure_reasons": {}}),
    )
    def test_planner_with_no_changes_is_ok(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        """Planner never writes file changes — the guard must not fire on planner."""
        mock_claude.return_value = _make_claude_result(
            '{"tasks": [{"name": "do thing"}], "context_files": [], "summary": "ok"}'
        )
        result = execute(
            _make_snapshot(crow_type="planner"),
            logger=_make_logger(),
            config=_make_config(),
        )
        assert result["status"] == "completed"

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch(
        "worker.executor.gather_reviewer_context",
        return_value=("diff", {"files_read": [], "files_failed": [], "failure_reasons": {}}),
    )
    @patch("worker.executor._build_git_diff", return_value=("some diff", ["f.py"]))
    def test_reviewer_with_no_changes_is_ok(
        self,
        mock_diff: MagicMock,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        """Reviewer never writes file changes — the guard must not fire on reviewer."""
        mock_claude.return_value = _make_claude_result(
            '{"approved": true, "blocking_issues": [], "summary": "looks good"}'
        )
        result = execute(
            _make_snapshot(crow_type="reviewer"),
            logger=_make_logger(),
            config=_make_config(),
        )
        assert result["status"] == "completed"


class TestGitDiffBase:
    """_build_git_diff must compare against origin/main, not local main,
    because the worker's local main can be days behind origin and would
    produce phantom diffs of unrelated commits."""

    def test_default_base_is_origin_main(self) -> None:
        """Smoke: the default base_branch parameter must be 'origin/main'."""
        from inspect import signature

        from worker.executor import _build_git_diff

        sig = signature(_build_git_diff)
        assert sig.parameters["base_branch"].default == "origin/main"


class TestMaxTokensPerCrowType:
    """Implementer/fixer must get a higher max_tokens budget than planner/reviewer
    because they serialize entire file contents into JSON `content` strings,
    while planner/reviewer only emit short task lists or verdicts."""

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch(
        "worker.executor.gather_implementer_context",
        return_value=("ctx", {"files_read": [], "files_failed": [], "failure_reasons": {}}),
    )
    @patch("worker.executor.apply_changes", return_value=[])
    @patch("worker.executor.commit_and_push", return_value="abc")
    @patch("worker.executor.create_pr", return_value={"number": 1, "html_url": "x"})
    def test_implementer_gets_high_max_tokens(
        self,
        mock_pr: MagicMock,
        mock_push: MagicMock,
        mock_apply: MagicMock,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        mock_claude.return_value = _make_claude_result(
            '{"changes": [{"path": "x.py", "action": "create", "content": "x"}], "commit_message": "feat", "summary": "ok"}'
        )
        execute(_make_snapshot(crow_type="implementer"), logger=_make_logger(), config=_make_config())
        kwargs = mock_claude.call_args.kwargs
        assert kwargs["max_tokens"] >= 32_000, (
            f"implementer max_tokens={kwargs['max_tokens']} is too low — "
            "file-content serialization truncates at 8K"
        )

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch(
        "worker.executor.gather_planner_context",
        return_value=("ctx", {"files_read": [], "files_failed": [], "failure_reasons": {}}),
    )
    def test_planner_keeps_default_max_tokens(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        mock_claude.return_value = _make_claude_result('{"tasks": [{"name": "x"}], "summary": "ok"}')
        execute(_make_snapshot(crow_type="planner"), logger=_make_logger(), config=_make_config())
        kwargs = mock_claude.call_args.kwargs
        # Planner doesn't need the high cap — keep cost low
        assert kwargs["max_tokens"] <= 16_384


class TestTruncationGuard:
    """When the model hits max_tokens mid-JSON, the guard error must say
    "truncated" so the operator knows to raise the cap, not "no changes"."""

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch(
        "worker.executor.gather_implementer_context",
        return_value=("ctx", {"files_read": [], "files_failed": [], "failure_reasons": {}}),
    )
    def test_truncated_implementer_fails_with_specific_reason(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        truncated_result = ClaudeResult(
            raw_output='{"changes": [{"path": "a.py", "action": "create", "content": "x = 1\\n',
            tokens_in=100,
            tokens_out=32_768,
            duration_ms=1000,
            model="test",
            truncated=True,
        )
        mock_claude.return_value = truncated_result
        result = execute(
            _make_snapshot(crow_type="implementer"),
            logger=_make_logger(),
            config=_make_config(),
        )
        assert result["status"] == "failed"
        assert "truncated" in result["outcome"]["error"]
        assert "max_tokens" in result["outcome"]["error"]


class TestStructuredOutputPath:
    """When call_claude returns structured_output (Claude called submit_result),
    the executor must prefer it over parse_json_output(raw_output)."""

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch(
        "worker.executor.gather_implementer_context",
        return_value=("ctx", {"files_read": [], "files_failed": [], "failure_reasons": {}}),
    )
    @patch("worker.executor.apply_changes", return_value=["x.py"])
    @patch("worker.executor.commit_and_push", return_value="abc123")
    @patch(
        "worker.executor.create_pr",
        return_value={"number": 1, "html_url": "https://example.invalid/1"},
    )
    def test_implementer_prefers_structured_output_over_raw(
        self,
        mock_pr: MagicMock,
        mock_push: MagicMock,
        mock_apply: MagicMock,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        # raw_output is junk prose — would parse to {}. structured_output
        # is the real payload (as if Claude called submit_result).
        result_obj = ClaudeResult(
            raw_output="Let me think about this...",
            tokens_in=10,
            tokens_out=5,
            duration_ms=100,
            model="test",
            structured_output={
                "changes": [{"path": "x.py", "action": "create", "content": "x = 1\n"}],
                "commit_message": "feat: x",
                "summary": "added x",
            },
        )
        mock_claude.return_value = result_obj

        result = execute(
            _make_snapshot(crow_type="implementer"),
            logger=_make_logger(),
            config=_make_config(),
        )

        assert result["status"] == "completed"
        # apply_changes received the structured payload's changes, NOT the
        # raw text (which would have parsed to nothing).
        mock_apply.assert_called_once()
        applied = mock_apply.call_args[0][1]
        assert applied[0]["path"] == "x.py"

    @patch("worker.executor.cleanup_worktree")
    @patch("worker.executor.create_worktree", return_value="/wt")
    @patch("worker.executor.ensure_repo", return_value="/repo")
    @patch("worker.executor.call_claude")
    @patch(
        "worker.executor.gather_implementer_context",
        return_value=("ctx", {"files_read": [], "files_failed": [], "failure_reasons": {}}),
    )
    def test_implementer_includes_submit_result_in_tools(
        self,
        mock_context: MagicMock,
        mock_claude: MagicMock,
        mock_ensure: MagicMock,
        mock_wt: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        mock_claude.return_value = _make_claude_result(
            '{"changes": [], "summary": "noop"}'
        )
        # Will fail at empty-changes guard, but we only care about the tools list
        execute(
            _make_snapshot(crow_type="implementer"),
            logger=_make_logger(),
            config=_make_config(),
        )

        tools = mock_claude.call_args.kwargs["tools"]
        tool_names = [t["name"] for t in tools]
        assert "submit_result" in tool_names
        assert "read_file" in tool_names
        assert "glob_files" in tool_names

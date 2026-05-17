"""Tests for git + github investigation tools."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from council.tools.git import get_pr_diff, git_log_for_file, read_integration_file
from council.tools.github import get_pr_metadata


def test_git_log_for_file_returns_recent_commits() -> None:
    log_output = b"""abc123 alice 2026-01-01 added foo
def456 bob 2026-01-02 refactored foo
"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout=log_output, stderr=b""
        )
        result = git_log_for_file(repo_path="/r", file_path="foo.py", max_entries=5)
        assert len(result["commits"]) == 2
        assert result["commits"][0]["sha"] == "abc123"


def test_get_pr_diff_reads_from_worktree() -> None:
    diff_output = b"""diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -1 +1,2 @@
+# new line
"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout=diff_output, stderr=b""
        )
        result = get_pr_diff(worktree_path="/r/.pr-42")
        assert "new line" in result["diff"]


def test_read_integration_file_reads_from_integration_worktree(
    tmp_path: Path,
) -> None:
    integration = tmp_path / ".integration"
    integration.mkdir()
    (integration / "merged.py").write_text("merged content")
    result = read_integration_file(integration_path=str(integration), path="merged.py")
    assert result["content"] == "merged content"


def test_get_pr_metadata_fetches_from_github_api() -> None:
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = (
            b'{"number":42,"title":"Fix bug","user":{"login":"alice"},'
            b'"head":{"sha":"abc"},"body":"Description here"}'
        )
        result = get_pr_metadata(repo="org/r", pr_number=42, github_token="t")
        assert result["title"] == "Fix bug"
        assert result["author"] == "alice"

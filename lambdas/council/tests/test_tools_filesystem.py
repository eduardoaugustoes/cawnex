"""Tests for filesystem investigation tools."""

import os
import tempfile
from collections.abc import Iterator

import pytest

from council.tools.filesystem import grep, list_directory, read_file


@pytest.fixture
def tmp_repo() -> Iterator[str]:
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(f"{d}/apps/api", exist_ok=True)
        with open(f"{d}/apps/api/foo.py", "w") as f:
            f.write("def hello():\n    return 'world'\n")
        yield d


def test_read_file_returns_full_contents(tmp_repo: str) -> None:
    result = read_file(path=f"{tmp_repo}/apps/api/foo.py")
    assert "def hello" in result["content"]


def test_read_file_returns_line_range(tmp_repo: str) -> None:
    result = read_file(path=f"{tmp_repo}/apps/api/foo.py", line_start=1, line_end=1)
    assert result["content"].startswith("def hello")
    assert "return" not in result["content"]


def test_read_file_missing_returns_error(tmp_repo: str) -> None:
    result = read_file(path=f"{tmp_repo}/no/such/file.py")
    assert result["error"] == "file_not_found"


def test_grep_finds_matches(tmp_repo: str) -> None:
    result = grep(pattern="hello", path=tmp_repo)
    assert any("foo.py" in m["file"] for m in result["matches"])


def test_grep_empty_results_is_not_error(tmp_repo: str) -> None:
    result = grep(pattern="nonexistent_pattern", path=tmp_repo)
    assert result["matches"] == []
    assert "error" not in result


def test_list_directory_lists_files(tmp_repo: str) -> None:
    result = list_directory(path=f"{tmp_repo}/apps/api")
    assert "foo.py" in result["entries"]

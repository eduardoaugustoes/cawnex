"""Tests for worktree-scoped tools used by the implementer's tool-use loop."""

from __future__ import annotations

import os

import pytest

from worker.logging import StructuredLogger
from worker.tools import (
    WORKTREE_TOOL_SCHEMAS,
    WorktreeTools,
)


def _make_tools(tmp_path: object) -> WorktreeTools:
    logger = StructuredLogger("test")
    return WorktreeTools(worktree_dir=str(tmp_path), logger=logger)


def test_read_file_returns_content_for_existing_file(tmp_path: object) -> None:
    path = os.path.join(str(tmp_path), "foo.md")
    with open(path, "w") as f:
        f.write("hello world")

    tools = _make_tools(tmp_path)
    result = tools.read_file("foo.md")

    assert result["content"] == "hello world"
    assert result.get("error") is None
    assert "foo.md" in tools.files_read


def test_read_file_records_path_in_files_read(tmp_path: object) -> None:
    with open(os.path.join(str(tmp_path), "a.py"), "w") as f:
        f.write("x = 1")

    tools = _make_tools(tmp_path)
    tools.read_file("a.py")
    tools.read_file("a.py")  # duplicate

    assert tools.files_read == {"a.py"}


def test_read_file_missing_returns_error(tmp_path: object) -> None:
    tools = _make_tools(tmp_path)
    result = tools.read_file("ghost.py")

    assert "error" in result
    assert "not found" in result["error"].lower()


def test_read_file_blocks_path_escape_with_dotdot(tmp_path: object) -> None:
    tools = _make_tools(tmp_path)
    result = tools.read_file("../../../etc/passwd")

    assert "error" in result
    assert "escapes worktree" in result["error"]


def test_read_file_blocks_absolute_path_outside_worktree(tmp_path: object) -> None:
    tools = _make_tools(tmp_path)
    # An absolute path resolves to itself; if it's outside the worktree dir,
    # the safety guard should reject it.
    result = tools.read_file("/etc/passwd")

    assert "error" in result
    assert "escapes worktree" in result["error"]


def test_read_file_truncates_large_files(tmp_path: object) -> None:
    path = os.path.join(str(tmp_path), "big.txt")
    with open(path, "w") as f:
        f.write("x" * 50)

    tools = _make_tools(tmp_path)
    result = tools.read_file("big.txt", max_bytes=10)

    assert result["content"] == "x" * 10
    assert result["truncated"] is True
    assert result["size_bytes"] == 50


def test_read_file_does_not_mark_truncated_for_small_files(tmp_path: object) -> None:
    with open(os.path.join(str(tmp_path), "small.txt"), "w") as f:
        f.write("hi")

    tools = _make_tools(tmp_path)
    result = tools.read_file("small.txt")

    assert result["content"] == "hi"
    assert result["truncated"] is False


def test_read_file_caps_total_files_read(tmp_path: object) -> None:
    for i in range(60):
        with open(os.path.join(str(tmp_path), f"f{i}.py"), "w") as f:
            f.write(f"# {i}")

    tools = _make_tools(tmp_path)
    tools.max_files_read = 5

    for i in range(10):
        tools.read_file(f"f{i}.py")

    # First 5 succeed, rest return cap-hit error
    assert len(tools.files_read) == 5
    cap_result = tools.read_file("f9.py")
    assert "error" in cap_result
    assert "limit" in cap_result["error"].lower()


def test_glob_files_returns_relative_paths(tmp_path: object) -> None:
    base = str(tmp_path)
    os.makedirs(os.path.join(base, "src"))
    os.makedirs(os.path.join(base, "tests"))
    for name in ("src/a.py", "src/b.py", "tests/test_a.py", "README.md"):
        with open(os.path.join(base, name), "w") as f:
            f.write("x")

    tools = _make_tools(tmp_path)
    result = tools.glob_files("**/*.py")

    assert "src/a.py" in result["matches"]
    assert "src/b.py" in result["matches"]
    assert "tests/test_a.py" in result["matches"]
    assert "README.md" not in result["matches"]


def test_glob_files_skips_skip_dirs(tmp_path: object) -> None:
    base = str(tmp_path)
    os.makedirs(os.path.join(base, "node_modules"))
    os.makedirs(os.path.join(base, ".git"))
    os.makedirs(os.path.join(base, "src"))
    with open(os.path.join(base, "node_modules", "x.js"), "w") as f:
        f.write("ignored")
    with open(os.path.join(base, ".git", "config"), "w") as f:
        f.write("ignored")
    with open(os.path.join(base, "src", "a.js"), "w") as f:
        f.write("ok")

    tools = _make_tools(tmp_path)
    result = tools.glob_files("**/*.js")

    assert "src/a.js" in result["matches"]
    assert all("node_modules" not in m for m in result["matches"])
    assert all(".git" not in m for m in result["matches"])


def test_glob_files_caps_results(tmp_path: object) -> None:
    base = str(tmp_path)
    for i in range(150):
        with open(os.path.join(base, f"f{i}.txt"), "w") as f:
            f.write("x")

    tools = _make_tools(tmp_path)
    result = tools.glob_files("*.txt", max_results=20)

    assert len(result["matches"]) == 20
    assert result["truncated"] is True


def test_grep_files_returns_path_line_text(tmp_path: object) -> None:
    base = str(tmp_path)
    with open(os.path.join(base, "a.py"), "w") as f:
        f.write("hello\nworld\nhello again\n")
    with open(os.path.join(base, "b.py"), "w") as f:
        f.write("nothing here\n")

    tools = _make_tools(tmp_path)
    result = tools.grep_files("hello")

    matches = result["matches"]
    paths = {(m["path"], m["line"]) for m in matches}
    assert ("a.py", 1) in paths
    assert ("a.py", 3) in paths
    # b.py has no match
    assert all(m["path"] != "b.py" for m in matches)


def test_grep_files_respects_path_glob(tmp_path: object) -> None:
    base = str(tmp_path)
    os.makedirs(os.path.join(base, "src"))
    os.makedirs(os.path.join(base, "docs"))
    with open(os.path.join(base, "src", "main.py"), "w") as f:
        f.write("needle\n")
    with open(os.path.join(base, "docs", "readme.md"), "w") as f:
        f.write("needle\n")

    tools = _make_tools(tmp_path)
    result = tools.grep_files("needle", path_glob="src/**/*.py")

    assert any(m["path"] == "src/main.py" for m in result["matches"])
    assert all(m["path"] != "docs/readme.md" for m in result["matches"])


def test_grep_files_caps_total_matches(tmp_path: object) -> None:
    with open(os.path.join(str(tmp_path), "spam.txt"), "w") as f:
        for _ in range(200):
            f.write("hit\n")

    tools = _make_tools(tmp_path)
    result = tools.grep_files("hit", max_matches=10)

    assert len(result["matches"]) == 10
    assert result["truncated"] is True


def test_list_dir_returns_immediate_children(tmp_path: object) -> None:
    base = str(tmp_path)
    os.makedirs(os.path.join(base, "src"))
    os.makedirs(os.path.join(base, "tests"))
    with open(os.path.join(base, "README.md"), "w") as f:
        f.write("x")

    tools = _make_tools(tmp_path)
    result = tools.list_dir(".")

    names = result["entries"]
    assert "src/" in names
    assert "tests/" in names
    assert "README.md" in names


def test_list_dir_blocks_path_escape(tmp_path: object) -> None:
    tools = _make_tools(tmp_path)
    result = tools.list_dir("../../../")

    assert "error" in result
    assert "escapes worktree" in result["error"]


def test_list_dir_returns_error_for_missing_path(tmp_path: object) -> None:
    tools = _make_tools(tmp_path)
    result = tools.list_dir("does/not/exist")

    assert "error" in result


def test_schemas_advertise_expected_tools() -> None:
    names = {schema["name"] for schema in WORKTREE_TOOL_SCHEMAS}
    assert names == {"read_file", "glob_files", "grep_files", "list_dir"}
    # Every schema must declare type: object input_schema with required fields
    for schema in WORKTREE_TOOL_SCHEMAS:
        assert schema["input_schema"]["type"] == "object"
        assert "properties" in schema["input_schema"]


def test_execute_dispatches_to_correct_tool(tmp_path: object) -> None:
    with open(os.path.join(str(tmp_path), "a.py"), "w") as f:
        f.write("contents")

    tools = _make_tools(tmp_path)

    read = tools.execute("read_file", {"path": "a.py"})
    assert read["content"] == "contents"

    listed = tools.execute("list_dir", {"path": "."})
    assert "a.py" in listed["entries"]


def test_execute_unknown_tool_returns_error(tmp_path: object) -> None:
    tools = _make_tools(tmp_path)
    result = tools.execute("hack_the_planet", {})

    assert "error" in result
    assert "unknown tool" in result["error"].lower()


def test_execute_handles_missing_required_input(tmp_path: object) -> None:
    tools = _make_tools(tmp_path)
    # read_file requires "path"
    result = tools.execute("read_file", {})

    assert "error" in result

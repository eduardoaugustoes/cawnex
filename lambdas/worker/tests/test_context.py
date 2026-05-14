"""Tests for context gathering — filesystem-based, no git dependency."""

from __future__ import annotations

import os

from worker.context import (
    _read_file_safe,
    _walk_tree,
    gather_fixer_context,
    gather_implementer_context,
    gather_planner_context,
    gather_reviewer_context,
)


def test_read_file_safe_reads_small_file(tmp_path: object) -> None:
    p = os.path.join(str(tmp_path), "small.txt")
    with open(p, "w") as f:
        f.write("hello")
    assert _read_file_safe(p) == "hello"


def test_read_file_safe_skips_large_file(tmp_path: object) -> None:
    p = os.path.join(str(tmp_path), "big.txt")
    with open(p, "w") as f:
        f.write("x" * 60_000)
    assert _read_file_safe(p) is None


def test_read_file_safe_returns_none_on_missing() -> None:
    assert _read_file_safe("/nonexistent/file.txt") is None


def test_walk_tree_skips_dirs_and_exts(tmp_path: object) -> None:
    base = str(tmp_path)
    os.makedirs(os.path.join(base, "src"))
    os.makedirs(os.path.join(base, "node_modules"))
    os.makedirs(os.path.join(base, ".git"))
    with open(os.path.join(base, "src", "main.py"), "w") as f:
        f.write("code")
    with open(os.path.join(base, "node_modules", "pkg.js"), "w") as f:
        f.write("pkg")
    with open(os.path.join(base, ".git", "config"), "w") as f:
        f.write("git")
    with open(os.path.join(base, "image.png"), "w") as f:
        f.write("binary")
    with open(os.path.join(base, "readme.md"), "w") as f:
        f.write("docs")

    files = _walk_tree(base)
    assert "src/main.py" in files
    assert "readme.md" in files
    assert "image.png" not in files
    assert "node_modules/pkg.js" not in files
    assert ".git/config" not in files


def test_gather_planner_context_includes_tree_and_files(tmp_path: object) -> None:
    base = str(tmp_path)
    os.makedirs(os.path.join(base, "src"))
    with open(os.path.join(base, "src", "app.py"), "w") as f:
        f.write("print('app')")
    with open(os.path.join(base, "README.md"), "w") as f:
        f.write("# Project")

    ctx, audit = gather_planner_context(base, max_files=5)
    assert "File Tree" in ctx
    assert "src/app.py" in ctx
    assert "print('app')" in ctx
    assert "# Project" in ctx
    assert "src/app.py" in audit["files_read"]
    assert "README.md" in audit["files_read"]


def test_gather_planner_context_respects_max_files(tmp_path: object) -> None:
    base = str(tmp_path)
    for i in range(10):
        with open(os.path.join(base, f"file{i}.py"), "w") as f:
            f.write(f"# file {i}")

    ctx, audit = gather_planner_context(base, max_files=3)
    file_sections = ctx.count("## file")
    assert file_sections == 3
    assert len(audit["files_read"]) == 3


def test_gather_implementer_context_reads_specified_files(tmp_path: object) -> None:
    base = str(tmp_path)
    os.makedirs(os.path.join(base, "src"))
    with open(os.path.join(base, "src", "a.py"), "w") as f:
        f.write("module_a")
    with open(os.path.join(base, "src", "b.py"), "w") as f:
        f.write("module_b")
    with open(os.path.join(base, "src", "c.py"), "w") as f:
        f.write("module_c")

    ctx, audit = gather_implementer_context(
        base,
        files_to_read=["src/a.py"],
        files_to_modify=["src/b.py"],
    )
    assert "module_a" in ctx
    assert "module_b" in ctx
    assert "[read]" in ctx
    assert "[modify]" in ctx
    assert "module_c" not in ctx
    assert "src/a.py" in audit["files_read"]
    assert "src/b.py" in audit["files_read"]


def test_gather_implementer_context_deduplicates(tmp_path: object) -> None:
    base = str(tmp_path)
    with open(os.path.join(base, "file.py"), "w") as f:
        f.write("code")

    ctx, _ = gather_implementer_context(
        base,
        files_to_read=["file.py"],
        files_to_modify=["file.py"],
    )
    assert ctx.count("code") == 1


def test_gather_implementer_context_audits_missing_files(tmp_path: object) -> None:
    base = str(tmp_path)
    with open(os.path.join(base, "exists.py"), "w") as f:
        f.write("real")

    ctx, audit = gather_implementer_context(
        base,
        files_to_read=["exists.py", "ghost.py"],
        files_to_modify=[],
    )
    assert "real" in ctx
    assert "exists.py" in audit["files_read"]
    assert "ghost.py" in audit["files_failed"]
    assert audit["failure_reasons"]["ghost.py"] == "missing"


def test_gather_reviewer_context_includes_diff(tmp_path: object) -> None:
    base = str(tmp_path)
    with open(os.path.join(base, "file.py"), "w") as f:
        f.write("modified content")

    ctx, audit = gather_reviewer_context(
        base,
        git_diff="+added line\n-removed line",
        changed_files=["file.py"],
    )
    assert "Git Diff" in ctx
    assert "+added line" in ctx
    assert "modified content" in ctx
    assert "file.py" in audit["files_read"]


def test_gather_reviewer_context_empty_diff(tmp_path: object) -> None:
    ctx, audit = gather_reviewer_context(str(tmp_path), git_diff="", changed_files=[])
    assert isinstance(ctx, str)
    assert audit["files_read"] == []


def test_gather_fixer_context_includes_feedback(tmp_path: object) -> None:
    base = str(tmp_path)
    with open(os.path.join(base, "handler.py"), "w") as f:
        f.write("def handle(): pass")

    ctx, audit = gather_fixer_context(
        base,
        issues=["Missing null check in handler.py:42"],
        suggestions=["Add input validation"],
        git_diff="+new code",
        changed_files=["handler.py"],
    )
    assert "Reviewer Feedback" in ctx
    assert "Missing null check" in ctx
    assert "Add input validation" in ctx
    assert "+new code" in ctx
    assert "handler.py" in audit["files_read"]


def test_gather_reviewer_context_limits_files(tmp_path: object) -> None:
    base = str(tmp_path)
    files = [f"file{i}.py" for i in range(15)]
    for f in files:
        with open(os.path.join(base, f), "w") as fh:
            fh.write(f"content of {f}")

    ctx, _ = gather_reviewer_context(base, git_diff="diff", changed_files=files)
    # Should only include first 10
    assert "file9.py" in ctx
    assert "file10.py" not in ctx

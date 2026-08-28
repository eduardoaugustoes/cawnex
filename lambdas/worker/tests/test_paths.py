"""Tests for paths — the single containment primitive."""

from __future__ import annotations

import os

from worker.paths import resolve_within


def test_plain_relative_path_resolves(tmp_path: str) -> None:
    root = str(tmp_path)
    result = resolve_within(root, "src/app.py")
    assert result == os.path.join(os.path.realpath(root), "src/app.py")


def test_root_itself_is_allowed(tmp_path: str) -> None:
    root = str(tmp_path)
    assert resolve_within(root, ".") == os.path.realpath(root)


def test_parent_traversal_rejected(tmp_path: str) -> None:
    assert resolve_within(str(tmp_path), "../escape.txt") is None


def test_deep_traversal_rejected(tmp_path: str) -> None:
    assert resolve_within(str(tmp_path), "../../../../../../etc/passwd") is None


def test_absolute_path_outside_rejected(tmp_path: str) -> None:
    assert resolve_within(str(tmp_path), "/etc/passwd") is None


def test_absolute_path_inside_allowed(tmp_path: str) -> None:
    root = os.path.realpath(str(tmp_path))
    inside = os.path.join(root, "pkg/mod.py")
    assert resolve_within(root, inside) == inside


def test_symlink_escaping_root_rejected(tmp_path: str) -> None:
    root = str(tmp_path)
    link = os.path.join(root, "leak.txt")
    os.symlink("/etc/passwd", link)
    assert resolve_within(root, "leak.txt") is None


def test_sibling_prefix_not_treated_as_inside(tmp_path: str) -> None:
    """/mnt/worktrees/cr_1 must not admit /mnt/worktrees/cr_1-evil."""
    root = os.path.join(str(tmp_path), "cr_1")
    os.makedirs(root)
    os.makedirs(os.path.join(str(tmp_path), "cr_1-evil"))
    assert resolve_within(root, "../cr_1-evil/x.txt") is None


def test_empty_candidate_rejected(tmp_path: str) -> None:
    assert resolve_within(str(tmp_path), "") is None


def test_null_byte_rejected(tmp_path: str) -> None:
    assert resolve_within(str(tmp_path), "ok\x00/etc/passwd") is None

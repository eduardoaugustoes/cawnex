"""Tests for per-advisor tool palette + scope enforcement."""

from council.enums import AdvisorType
from council.tools.palette import execute_tool, get_palette, is_in_scope


def test_security_palette_includes_git_log_for_file() -> None:
    tools = get_palette(AdvisorType.SECURITY)
    assert any(t["name"] == "git_log_for_file" for t in tools)


def test_ux_palette_does_not_include_git_log_for_file() -> None:
    tools = get_palette(AdvisorType.UX)
    assert not any(t["name"] == "git_log_for_file" for t in tools)


def test_ux_read_file_on_ios_path_is_in_scope() -> None:
    assert is_in_scope(
        AdvisorType.UX, "read_file", {"path": "/repo/apps/ios/foo.swift"}
    )


def test_ux_read_file_on_api_path_is_out_of_scope() -> None:
    assert not is_in_scope(
        AdvisorType.UX, "read_file", {"path": "/repo/apps/api/foo.py"}
    )


def test_cost_read_file_on_infra_path_is_in_scope() -> None:
    assert is_in_scope(
        AdvisorType.COST, "read_file", {"path": "/repo/infra/lib/foo.ts"}
    )


def test_cost_read_file_on_api_path_is_out_of_scope() -> None:
    assert not is_in_scope(
        AdvisorType.COST, "read_file", {"path": "/repo/apps/api/foo.py"}
    )


def test_security_read_file_on_anywhere_is_in_scope() -> None:
    assert is_in_scope(
        AdvisorType.SECURITY, "read_file", {"path": "/repo/anywhere/foo.py"}
    )


def test_execute_tool_returns_out_of_scope_error_for_disallowed_path() -> None:
    result = execute_tool(
        advisor=AdvisorType.UX,
        tool_name="read_file",
        args={"path": "/repo/apps/api/foo.py"},
        context={"repo_path": "/repo", "github_token": ""},
    )
    assert result["tool_error"] == "out_of_scope"
    assert result["advisor"] == "ux"

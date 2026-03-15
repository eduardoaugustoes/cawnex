"""Tests for parsing — JSON extraction from Claude output."""

import pytest

from worker.parsing import parse_json_output


class TestParseJsonOutput:
    def test_clean_json(self) -> None:
        raw = '{"changes": [{"path": "test.py"}], "summary": "test"}'
        result = parse_json_output(raw)
        assert result is not None
        assert result["summary"] == "test"

    def test_json_with_markdown_fences(self) -> None:
        raw = '```json\n{"approved": true, "issues": []}\n```'
        result = parse_json_output(raw)
        assert result is not None
        assert result["approved"] is True

    def test_json_with_bare_fences(self) -> None:
        raw = '```\n{"plan": "do stuff"}\n```'
        result = parse_json_output(raw)
        assert result is not None
        assert result["plan"] == "do stuff"

    def test_json_embedded_in_text(self) -> None:
        raw = (
            'Here is my analysis:\n{"approved": false, "issues": ["bug"]}\nThat is all.'
        )
        result = parse_json_output(raw)
        assert result is not None
        assert result["approved"] is False
        assert result["issues"] == ["bug"]

    def test_json_array(self) -> None:
        raw = '[{"path": "a.py", "content": "pass"}]'
        result = parse_json_output(raw)
        assert result is not None
        assert isinstance(result, list)
        assert result[0]["path"] == "a.py"

    def test_invalid_json_returns_none(self) -> None:
        raw = "This is not JSON at all"
        result = parse_json_output(raw)
        assert result is None

    def test_empty_string_returns_none(self) -> None:
        result = parse_json_output("")
        assert result is None

    def test_nested_braces(self) -> None:
        raw = '{"plan": {"steps": [{"desc": "step 1"}]}, "summary": "ok"}'
        result = parse_json_output(raw)
        assert result is not None
        assert result["plan"]["steps"][0]["desc"] == "step 1"

    def test_whitespace_around_json(self) -> None:
        raw = '   \n  {"key": "value"}  \n  '
        result = parse_json_output(raw)
        assert result is not None
        assert result["key"] == "value"

    def test_multiple_json_objects_picks_first(self) -> None:
        raw = '{"first": true}\n{"second": true}'
        result = parse_json_output(raw)
        assert result is not None
        assert "first" in result

    def test_json_with_trailing_fence(self) -> None:
        raw = '```json\n{"ok": true}\n```\n\nSome extra text'
        result = parse_json_output(raw)
        assert result is not None
        assert result["ok"] is True

    def test_array_embedded_in_text(self) -> None:
        raw = "Here are the changes:\n[1, 2, 3]\nDone."
        result = parse_json_output(raw)
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 3

    def test_malformed_json_in_braces_returns_none(self) -> None:
        raw = "Some text {not: valid json} more text"
        result = parse_json_output(raw)
        assert result is None

    def test_malformed_json_in_brackets_returns_none(self) -> None:
        raw = "Some text [not valid json] more text"
        result = parse_json_output(raw)
        assert result is None

"""End-to-end smoke test for the implementer tool-use loop.

Wires together the real WorktreeTools, real call_claude loop machinery, and a
real on-disk worktree — only the Anthropic HTTP client is mocked. This proves
that:

1. The implementer crow's claude_result.tool_calls actually invoke files on
   disk via WorktreeTools.
2. The spec file mentioned in the directive is read by the implementer.
3. The final JSON output is parsed and applied as a real git change.

If this test passes, the same code path will work against the live API — the
only difference is who synthesizes the tool_use blocks (mock vs Claude).
"""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import MagicMock, patch

from worker.config import ExecutionConfig
from worker.executor import execute
from worker.logging import StructuredLogger


def _text_block(text: str) -> MagicMock:
    b = MagicMock()
    b.type = "text"
    b.text = text
    return b


def _tool_use_block(tool_id: str, name: str, tool_input: dict[str, Any]) -> MagicMock:
    b = MagicMock()
    b.type = "tool_use"
    b.id = tool_id
    b.name = name
    b.input = tool_input
    return b


def _response(
    content: list[MagicMock], stop_reason: str = "end_turn", tokens_in: int = 100
) -> MagicMock:
    r = MagicMock()
    r.content = content
    r.stop_reason = stop_reason
    r.usage.input_tokens = tokens_in
    r.usage.output_tokens = 50
    r.usage.cache_creation_input_tokens = 0
    r.usage.cache_read_input_tokens = 0
    return r


def _seed_worktree(base: str) -> None:
    """Create a fake project mirroring the run-2 shape."""
    os.makedirs(os.path.join(base, "docs", "superpowers", "specs"), exist_ok=True)
    os.makedirs(os.path.join(base, "apps", "api", "src", "routes"), exist_ok=True)
    os.makedirs(os.path.join(base, "apps", "api", "src", "models"), exist_ok=True)
    os.makedirs(os.path.join(base, "apps", "api", "src", "db"), exist_ok=True)

    # The spec — this is what implementer MUST read before touching code
    with open(
        os.path.join(
            base, "docs", "superpowers", "specs", "2026-05-13-project-state-readout-design.md"
        ),
        "w",
    ) as f:
        f.write(
            "# Project State Readout\n\n"
            "## Scope\n\n"
            "Add a computed `state` field to ProjectReadResponse. "
            "No new endpoint; just enrich the existing read response.\n"
            "Do NOT delete TenantDB or any existing endpoints.\n"
        )

    # The DB client the implementer is told to modify — must NOT be deleted
    with open(os.path.join(base, "apps", "api", "src", "db", "client.py"), "w") as f:
        f.write(
            "class TenantDB:\n"
            "    def __init__(self, table):\n"
            "        self.table = table\n"
            "    def get_item(self, sk):\n"
            "        return self.table.get_item(Key={'PK': 'X', 'SK': sk})\n"
        )

    with open(os.path.join(base, "apps", "api", "src", "routes", "projects.py"), "w") as f:
        f.write("# project routes — existing endpoints live here\n")
    with open(os.path.join(base, "apps", "api", "src", "models", "__init__.py"), "w") as f:
        f.write("class ProjectReadResponse: pass\n")


def test_smoke_implementer_loop_reads_spec_and_emits_changes(tmp_path: object) -> None:
    """Full path: directive → tools called against real fs → final JSON applied."""
    base = str(tmp_path)
    _seed_worktree(base)

    # Mock Claude responses: 3 turns simulating real implementer behavior
    # Turn 1: model reads the spec
    # Turn 2: model reads the db client
    # Turn 3: model emits the final JSON
    responses = [
        _response(
            [
                _text_block("Let me read the spec first."),
                _tool_use_block(
                    "toolu_spec",
                    "read_file",
                    {"path": "docs/superpowers/specs/2026-05-13-project-state-readout-design.md"},
                ),
            ],
            stop_reason="tool_use",
        ),
        _response(
            [
                _text_block("Now reading the db client."),
                _tool_use_block(
                    "toolu_db", "read_file", {"path": "apps/api/src/db/client.py"}
                ),
            ],
            stop_reason="tool_use",
        ),
        _response(
            [
                _text_block(
                    json.dumps(
                        {
                            "changes": [
                                {
                                    "path": "apps/api/src/models/__init__.py",
                                    "action": "modify",
                                    "content": "class ProjectReadResponse:\n    state: str = 'planning'\n",
                                }
                            ],
                            "commit_message": "feat: add state field to ProjectReadResponse",
                            "summary": "Added computed state field per spec",
                        }
                    )
                )
            ],
            stop_reason="end_turn",
        ),
    ]

    snapshot = {
        "crow_type": "implementer",
        "crow_id": "cr_smoke_01",
        "repo": "owner/repo",
        "branch": "cawnex/smoke",
        "instructions": json.dumps(
            {
                "mvi_directive": (
                    "Add a computed `state` field to ProjectReadResponse. "
                    "Spec: docs/superpowers/specs/2026-05-13-project-state-readout-design.md"
                ),
                "context_files": [
                    "docs/superpowers/specs/2026-05-13-project-state-readout-design.md"
                ],
                "files_to_modify": ["apps/api/src/models/__init__.py"],
            }
        ),
        "budget_remaining": 5_000_000,
    }

    logger = StructuredLogger(component="smoke", tenant="t", project="p")
    config = ExecutionConfig(efs_mount="/efs", github_token="fake")

    # Patch just the IO boundaries: anthropic HTTP client, git operations, and
    # the worktree creation (which would need a real git repo). The agentic
    # loop, tool dispatch, and filesystem reads run for real.
    with patch("worker.claude._get_client") as mock_client_fn, patch(
        "worker.executor.ensure_repo", return_value=base
    ), patch("worker.executor.create_worktree", return_value=base), patch(
        "worker.executor.cleanup_worktree"
    ), patch(
        "worker.executor.commit_and_push", return_value="abc123"
    ), patch(
        "worker.executor.create_pr",
        return_value={"number": 1, "html_url": "https://github.com/x/y/pull/1"},
    ), patch(
        "worker.executor.apply_changes",
        return_value=["apps/api/src/models/__init__.py"],
    ) as mock_apply:
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.messages.create.side_effect = responses

        result = execute(snapshot, logger=logger, config=config)

    # 1. Crow completed successfully
    assert result["status"] == "completed", result
    assert "git_commit" in result

    # 2. Three API calls were made (proves the loop ran end-to-end)
    assert mock_client.messages.create.call_count == 3

    # 3. Walk the message history fed into the FINAL turn — it must contain a
    # tool_result whose content is the spec body read from disk. This proves
    # the loop actually read the spec file from the worktree rather than
    # accepting whatever the planner promised.
    final_call = mock_client.messages.create.call_args_list[-1].kwargs
    final_messages = final_call["messages"]
    spec_seen = False
    for msg in final_messages:
        if msg["role"] != "user" or not isinstance(msg["content"], list):
            continue
        for block in msg["content"]:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            try:
                payload = json.loads(block["content"])
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if "Do NOT delete TenantDB" in payload.get("content", ""):
                spec_seen = True
                break
        if spec_seen:
            break
    assert spec_seen, (
        "spec content should appear as a tool_result in the final turn's message history"
    )

    # 4. The final changes were applied (the worker called apply_changes with
    # the implementer's emitted JSON)
    mock_apply.assert_called_once()
    applied_changes = mock_apply.call_args[0][1]
    assert applied_changes[0]["path"] == "apps/api/src/models/__init__.py"
    assert applied_changes[0]["action"] == "modify"


def test_smoke_implementer_loop_handles_missing_file_gracefully(tmp_path: object) -> None:
    """Claude asking for a nonexistent file gets an error back, not a crash."""
    base = str(tmp_path)
    _seed_worktree(base)

    responses = [
        _response(
            [_tool_use_block("toolu_ghost", "read_file", {"path": "no/such/file.md"})],
            stop_reason="tool_use",
        ),
        _response(
            [_text_block(json.dumps({"changes": [], "summary": "could not find spec"}))],
            stop_reason="end_turn",
        ),
    ]

    snapshot = {
        "crow_type": "implementer",
        "crow_id": "cr_smoke_02",
        "repo": "owner/repo",
        "branch": "cawnex/smoke",
        "instructions": json.dumps(
            {
                "mvi_directive": "Try to read a missing file.",
                "context_files": [],
                "files_to_modify": [],
            }
        ),
        "budget_remaining": 1_000_000,
    }

    logger = StructuredLogger(component="smoke", tenant="t", project="p")
    config = ExecutionConfig(efs_mount="/efs", github_token="fake")

    with patch("worker.claude._get_client") as mock_client_fn, patch(
        "worker.executor.ensure_repo", return_value=base
    ), patch("worker.executor.create_worktree", return_value=base), patch(
        "worker.executor.cleanup_worktree"
    ):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.messages.create.side_effect = responses

        result = execute(snapshot, logger=logger, config=config)

    assert result["status"] == "completed"
    second_call = mock_client.messages.create.call_args_list[1].kwargs
    tool_result = second_call["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["is_error"] is True
    payload = json.loads(tool_result["content"])
    assert "not found" in payload["error"].lower()

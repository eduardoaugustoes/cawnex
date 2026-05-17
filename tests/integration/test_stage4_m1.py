"""Stage 4 M1 integration: Integrator dispatch + reactor end-to-end.

Exercises the conflict path: Murder reactor sees all MVIs ready_to_ship,
writes an integrator task; we simulate the Integrator writing IntegratorFindings
with a conflict; reactor flips affected MVIs back to executing for fixers.
"""

from __future__ import annotations

from typing import Any

from murder.blackboard import Blackboard
from murder.logging import StructuredLogger
from murder.reactor import _maybe_start_integrator, react_to_integration_complete


def test_m1_conflict_path_routes_wave_back_to_executing(ddb_table: Any) -> None:
    blackboard = Blackboard(ddb_table)
    logger = StructuredLogger("test-m1")

    ddb_table.put_item(
        Item={
            "PK": "P#p1",
            "SK": "S#w1",
            "level": "wave",
            "status": "review",
            "wave_id": "w1",
        }
    )
    ddb_table.put_item(
        Item={
            "PK": "P#p1",
            "SK": "S#w1#m_1",
            "level": "murder",
            "status": "ready_to_ship",
            "pr_number": 42,
            "mvi_id": "_1",
        }
    )
    ddb_table.put_item(
        Item={
            "PK": "P#p1",
            "SK": "S#w1#m_2",
            "level": "murder",
            "status": "ready_to_ship",
            "pr_number": 43,
            "mvi_id": "_2",
        }
    )
    ddb_table.put_item(
        Item={"PK": "P#p1", "SK": "META", "repo_path": "/mnt/repos/T/dev/repo"}
    )

    _maybe_start_integrator(
        blackboard=blackboard,
        pk="P#p1",
        wave_id="w1",
        logger=logger,
    )

    task = blackboard.read("P#p1", "S#w1/integrator-task")
    assert task is not None
    assert task["crow_kind"] == "integrator"
    assert task["pr_to_mvi"] == {"42": "_1", "43": "_2"}

    wave = blackboard.read("P#p1", "S#w1")
    assert wave is not None
    assert wave["status"] == "integrating"

    findings = {
        "PK": "P#p1",
        "SK": "INTEGRATION#w1",
        "wave_id": "w1",
        "overall": "needs_rework",
        "merge_status": "conflict",
        "rework_reasons": ["merge conflict between PR #42 and PR #43"],
        "merge_conflicts": [
            {
                "pr_a": 42,
                "pr_b": 43,
                "mvi_a": "_1",
                "mvi_b": "_2",
                "files": ["foo.py"],
                "hunks": [],
            }
        ],
    }
    blackboard.write_item(findings)
    react_to_integration_complete(blackboard=blackboard, findings=findings, logger=logger)

    mvi_1 = blackboard.read("P#p1", "S#w1#m_1")
    mvi_2 = blackboard.read("P#p1", "S#w1#m_2")
    assert mvi_1 is not None and mvi_1["status"] == "executing"
    assert mvi_2 is not None and mvi_2["status"] == "executing"

    wave_after = blackboard.read("P#p1", "S#w1")
    assert wave_after is not None
    assert wave_after["status"] == "executing"


def test_m1_ready_for_council_path_writes_pending_session(ddb_table: Any) -> None:
    """Happy path: integrator returns ready_for_council, reactor writes COUNCIL# pending."""
    blackboard = Blackboard(ddb_table)
    logger = StructuredLogger("test-m1")

    ddb_table.put_item(
        Item={
            "PK": "P#p1",
            "SK": "S#w2",
            "level": "wave",
            "status": "integrating",
            "wave_id": "w2",
        }
    )

    findings = {
        "PK": "P#p1",
        "SK": "INTEGRATION#w2",
        "wave_id": "w2",
        "overall": "ready_for_council",
        "merge_status": "ok",
        "rework_reasons": [],
    }
    react_to_integration_complete(blackboard=blackboard, findings=findings, logger=logger)

    wave = blackboard.read("P#p1", "S#w2")
    assert wave is not None
    assert wave["status"] == "under_council_review"

    sessions = blackboard.query("P#p1", "COUNCIL#")
    assert len(sessions) == 1
    assert sessions[0]["status"] == "pending"
    assert sessions[0]["integration_sk"] == "INTEGRATION#w2"

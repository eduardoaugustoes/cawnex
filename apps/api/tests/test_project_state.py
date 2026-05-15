"""Unit tests for project state computation."""

from typing import Any, Dict, List
from unittest.mock import Mock

import pytest

from src.db.project_state import compute_current_state


def _make_doc(doc_type: str, status: str) -> Dict[str, Any]:
    """Create a DOC# item."""
    return {
        "PK": "T#tenant#P#proj",
        "SK": f"DOC#{doc_type}",
        "doc_type": doc_type,
        "status": status,
    }


def _make_wave(wave_id: str, status: str) -> Dict[str, Any]:
    """Create a wave root item."""
    return {
        "PK": "T#tenant#P#proj",
        "SK": f"S#{wave_id}",
        "level": "wave",
        "status": status,
    }


def _make_mvi(wave_id: str, mvi_id: str, status: str) -> Dict[str, Any]:
    """Create an MVI (murder-level) item."""
    return {
        "PK": "T#tenant#P#proj",
        "SK": f"S#{wave_id}#m{mvi_id}",
        "level": "murder",
        "status": status,
    }


def _make_mock_db(items: List[Dict[str, Any]]) -> Mock:
    """Create a mock TenantDB that returns the given items."""
    db = Mock()

    def query_project(project_id: str, sk_prefix: str) -> List[Dict[str, Any]]:
        return [item for item in items if item["SK"].startswith(sk_prefix)]

    db.query_project.side_effect = query_project
    return db


def test_draft_when_no_docs() -> None:
    """Project with no DOC# items returns draft."""
    db = _make_mock_db([])
    assert compute_current_state("proj", db) == "draft"


def test_draft_when_partial_docs() -> None:
    """3 of 4 docs complete returns draft."""
    items = [
        _make_doc("vision", "complete"),
        _make_doc("architecture", "complete"),
        _make_doc("glossary", "complete"),
    ]
    db = _make_mock_db(items)
    assert compute_current_state("proj", db) == "draft"


def test_draft_when_incomplete_docs() -> None:
    """Some docs incomplete returns draft."""
    items = [
        _make_doc("vision", "complete"),
        _make_doc("architecture", "complete"),
        _make_doc("glossary", "in_progress"),
        _make_doc("design", "complete"),
    ]
    db = _make_mock_db(items)
    assert compute_current_state("proj", db) == "draft"


def test_active_when_docs_complete_no_waves() -> None:
    """All 4 docs complete, no S# items, returns active."""
    items = [
        _make_doc("vision", "complete"),
        _make_doc("architecture", "complete"),
        _make_doc("glossary", "complete"),
        _make_doc("design", "complete"),
    ]
    db = _make_mock_db(items)
    assert compute_current_state("proj", db) == "active"


def test_running_when_wave_executing() -> None:
    """Wave with status=executing returns running."""
    items = [
        _make_doc("vision", "complete"),
        _make_doc("architecture", "complete"),
        _make_doc("glossary", "complete"),
        _make_doc("design", "complete"),
        _make_wave("wave-1", "executing"),
    ]
    db = _make_mock_db(items)
    assert compute_current_state("proj", db) == "running"


def test_running_shadows_idle() -> None:
    """Multiple waves, one executing one delivered, returns running."""
    items = [
        _make_doc("vision", "complete"),
        _make_doc("architecture", "complete"),
        _make_doc("glossary", "complete"),
        _make_doc("design", "complete"),
        _make_wave("wave-1", "executing"),
        _make_wave("wave-2", "delivered"),
    ]
    db = _make_mock_db(items)
    assert compute_current_state("proj", db) == "running"


def test_idle_when_all_waves_delivered() -> None:
    """All waves delivered, no shipped MVIs, returns idle."""
    items = [
        _make_doc("vision", "complete"),
        _make_doc("architecture", "complete"),
        _make_doc("glossary", "complete"),
        _make_doc("design", "complete"),
        _make_wave("wave-1", "delivered"),
        _make_wave("wave-2", "delivered"),
    ]
    db = _make_mock_db(items)
    assert compute_current_state("proj", db) == "idle"


def test_idle_when_all_waves_cancelled() -> None:
    """All waves cancelled returns idle."""
    items = [
        _make_doc("vision", "complete"),
        _make_doc("architecture", "complete"),
        _make_doc("glossary", "complete"),
        _make_doc("design", "complete"),
        _make_wave("wave-1", "cancelled"),
    ]
    db = _make_mock_db(items)
    assert compute_current_state("proj", db) == "idle"


def test_idle_mixed_terminal_waves() -> None:
    """Mix of delivered and cancelled waves, no shipped MVIs, returns idle."""
    items = [
        _make_doc("vision", "complete"),
        _make_doc("architecture", "complete"),
        _make_doc("glossary", "complete"),
        _make_doc("design", "complete"),
        _make_wave("wave-1", "delivered"),
        _make_wave("wave-2", "cancelled"),
    ]
    db = _make_mock_db(items)
    assert compute_current_state("proj", db) == "idle"


def test_completed_when_shipped_and_terminal() -> None:
    """All waves terminal, at least one MVI shipped, returns completed."""
    items = [
        _make_doc("vision", "complete"),
        _make_doc("architecture", "complete"),
        _make_doc("glossary", "complete"),
        _make_doc("design", "complete"),
        _make_wave("wave-1", "delivered"),
        _make_mvi("wave-1", "1", "shipped"),
    ]
    db = _make_mock_db(items)
    assert compute_current_state("proj", db) == "completed"


def test_completed_requires_shipped() -> None:
    """All waves terminal but no MVIs shipped, returns idle (not completed)."""
    items = [
        _make_doc("vision", "complete"),
        _make_doc("architecture", "complete"),
        _make_doc("glossary", "complete"),
        _make_doc("design", "complete"),
        _make_wave("wave-1", "delivered"),
        _make_mvi("wave-1", "1", "ready_to_ship"),
    ]
    db = _make_mock_db(items)
    assert compute_current_state("proj", db) == "idle"


def test_completed_multiple_waves_with_shipped() -> None:
    """Multiple terminal waves with at least one shipped MVI returns completed."""
    items = [
        _make_doc("vision", "complete"),
        _make_doc("architecture", "complete"),
        _make_doc("glossary", "complete"),
        _make_doc("design", "complete"),
        _make_wave("wave-1", "delivered"),
        _make_wave("wave-2", "cancelled"),
        _make_mvi("wave-1", "1", "shipped"),
        _make_mvi("wave-2", "1", "cancelled"),
    ]
    db = _make_mock_db(items)
    assert compute_current_state("proj", db) == "completed"


def test_state_precedence_draft_wins() -> None:
    """Draft state takes precedence over running waves."""
    items = [
        _make_doc("vision", "in_progress"),
        _make_wave("wave-1", "executing"),
    ]
    db = _make_mock_db(items)
    assert compute_current_state("proj", db) == "draft"


def test_state_precedence_running_over_idle() -> None:
    """Running takes precedence over idle even with completed waves."""
    items = [
        _make_doc("vision", "complete"),
        _make_doc("architecture", "complete"),
        _make_doc("glossary", "complete"),
        _make_doc("design", "complete"),
        _make_wave("wave-1", "executing"),
        _make_wave("wave-2", "delivered"),
    ]
    db = _make_mock_db(items)
    assert compute_current_state("proj", db) == "running"


def test_empty_project() -> None:
    """Empty project with no data returns draft."""
    db = _make_mock_db([])
    assert compute_current_state("proj", db) == "draft"

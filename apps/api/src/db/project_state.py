"""Compute project's current_state from underlying entity truth."""

from typing import Any, Dict, List

from src.db.client import TenantDB

_DOC_TYPES = {"vision", "architecture", "glossary", "design"}
_TERMINAL_WAVE_STATUSES = {"delivered", "cancelled"}


def compute_current_state(project_id: str, db: TenantDB) -> str:
    """Return the project's computed current state. First match wins.

    Args:
        project_id: Project identifier
        db: TenantDB instance for querying project data

    Returns:
        One of: "draft", "active", "running", "idle", "completed"
    """
    if not _monarch_docs_complete(project_id, db):
        return "draft"
    if _has_executing_wave(project_id, db):
        return "running"
    waves = _list_waves(project_id, db)
    if not waves:
        return "active"
    if _all_terminal(waves) and _has_shipped(project_id, db):
        return "completed"
    return "idle"


def _monarch_docs_complete(project_id: str, db: TenantDB) -> bool:
    """All 4 setup documents exist and are status=complete.

    Args:
        project_id: Project identifier
        db: TenantDB instance

    Returns:
        True if all 4 required docs are complete, False otherwise
    """
    items = db.query_project(project_id=project_id, sk_prefix="DOC#")
    complete_types = {
        i.get("doc_type")
        for i in items
        if i.get("status") == "complete" and i.get("doc_type") is not None
    }
    return _DOC_TYPES.issubset(complete_types)


def _has_executing_wave(project_id: str, db: TenantDB) -> bool:
    """Any wave root with status=executing.

    Args:
        project_id: Project identifier
        db: TenantDB instance

    Returns:
        True if any wave is executing, False otherwise
    """
    return any(w.get("status") == "executing" for w in _list_waves(project_id, db))


def _list_waves(project_id: str, db: TenantDB) -> List[Dict[str, Any]]:
    """Root wave snapshots only (excludes nested MVI items).

    Args:
        project_id: Project identifier
        db: TenantDB instance

    Returns:
        List of wave root items (SK pattern S#{wave_id} with no # after)
    """
    items = db.query_project(project_id=project_id, sk_prefix="S#")
    return [i for i in items if _is_wave_root(i.get("SK", ""))]


def _is_wave_root(sk: str) -> bool:
    """SK pattern S#{wave_id} is a wave root; S#{wave_id}#m{mvi_id} is not.

    Args:
        sk: Sort key to check

    Returns:
        True if sk is a wave root, False otherwise
    """
    parts = sk.split("#")
    return len(parts) == 2 and parts[0] == "S" and parts[1] != ""


def _all_terminal(waves: List[Dict[str, Any]]) -> bool:
    """Every wave in a terminal status.

    Args:
        waves: List of wave items

    Returns:
        True if all waves are in terminal status, False otherwise
    """
    return all(w.get("status") in _TERMINAL_WAVE_STATUSES for w in waves)


def _has_shipped(project_id: str, db: TenantDB) -> bool:
    """Any MVI in shipped status anywhere on the project.

    Args:
        project_id: Project identifier
        db: TenantDB instance

    Returns:
        True if any MVI has shipped, False otherwise
    """
    items = db.query_project(project_id=project_id, sk_prefix="S#")
    for item in items:
        if item.get("level") == "murder" and item.get("status") == "shipped":
            return True
    return False

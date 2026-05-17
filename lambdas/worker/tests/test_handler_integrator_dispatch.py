"""Tests for worker handler dispatch routing crow_kind=integrator."""

from unittest.mock import MagicMock, patch

from worker.handler import dispatch_crow


def test_dispatch_crow_routes_integrator_to_run_integrator() -> None:
    with patch("worker.handler.run_integrator") as mock_run:
        task = {
            "crow_kind": "integrator",
            "wave_id": "w1",
            "project_id": "p1",
            "repo_path": "/mnt/repos/T/t/r",
            "pr_to_mvi": {"42": "m1", "43": "m2"},
        }
        dispatch_crow(task=task, blackboard=MagicMock())
        assert mock_run.called
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["wave_id"] == "w1"
        assert call_kwargs["pr_to_mvi"] == {42: "m1", 43: "m2"}


def test_dispatch_crow_raises_on_unknown_crow_kind() -> None:
    import pytest

    with pytest.raises(ValueError, match="does not handle crow_kind"):
        dispatch_crow(task={"crow_kind": "planner"}, blackboard=MagicMock())

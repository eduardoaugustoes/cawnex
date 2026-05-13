import pytest
from unittest.mock import Mock, MagicMock
from db.client import compute_current_state
from models import ProjectState


class TestComputeCurrentState:
    """Unit tests for compute_current_state function."""

    def test_compute_state_no_project(self):
        """Test state computation when project doesn't exist."""
        db = Mock()
        db.get_project.return_value = None
        
        state = compute_current_state("nonexistent", db)
        assert state is None

    def test_compute_state_planning_no_tasks(self):
        """Test state is PLANNING when project has no tasks."""
        db = Mock()
        project = Mock(id="proj1", name="Test Project")
        db.get_project.return_value = project
        db.get_project_tasks.return_value = []
        
        state = compute_current_state("proj1", db)
        assert state == ProjectState.PLANNING

    def test_compute_state_in_progress_with_started_tasks(self):
        """Test state is IN_PROGRESS when tasks are started."""
        db = Mock()
        project = Mock(id="proj1", name="Test Project")
        db.get_project.return_value = project
        
        task1 = Mock(status="in_progress")
        task2 = Mock(status="not_started")
        db.get_project_tasks.return_value = [task1, task2]
        
        state = compute_current_state("proj1", db)
        assert state == ProjectState.IN_PROGRESS

    def test_compute_state_in_progress_with_partial_completion(self):
        """Test state is IN_PROGRESS when some tasks are completed."""
        db = Mock()
        project = Mock(id="proj1", name="Test Project")
        db.get_project.return_value = project
        
        task1 = Mock(status="completed")
        task2 = Mock(status="not_started")
        db.get_project_tasks.return_value = [task1, task2]
        
        state = compute_current_state("proj1", db)
        assert state == ProjectState.IN_PROGRESS

    def test_compute_state_completed(self):
        """Test state is COMPLETED when all tasks are completed."""
        db = Mock()
        project = Mock(id="proj1", name="Test Project")
        db.get_project.return_value = project
        
        task1 = Mock(status="completed")
        task2 = Mock(status="completed")
        db.get_project_tasks.return_value = [task1, task2]
        
        state = compute_current_state("proj1", db)
        assert state == ProjectState.COMPLETED

    def test_compute_state_planning_all_not_started(self):
        """Test state is PLANNING when all tasks are not started."""
        db = Mock()
        project = Mock(id="proj1", name="Test Project")
        db.get_project.return_value = project
        
        task1 = Mock(status="not_started")
        task2 = Mock(status="not_started")
        db.get_project_tasks.return_value = [task1, task2]
        
        state = compute_current_state("proj1", db)
        assert state == ProjectState.PLANNING

    def test_compute_state_handles_missing_status_attribute(self):
        """Test state computation handles tasks without status attribute."""
        db = Mock()
        project = Mock(id="proj1", name="Test Project")
        db.get_project.return_value = project
        
        task1 = Mock(spec=[])  # No status attribute
        task2 = Mock(status="not_started")
        db.get_project_tasks.return_value = [task1, task2]
        
        state = compute_current_state("proj1", db)
        assert state == ProjectState.PLANNING

    def test_compute_state_handles_db_error(self):
        """Test state computation gracefully handles database errors."""
        db = Mock()
        db.get_project.side_effect = Exception("DB connection error")
        
        state = compute_current_state("proj1", db)
        assert state is None

    def test_compute_state_single_completed_task(self):
        """Test state COMPLETED with single task."""
        db = Mock()
        project = Mock(id="proj1", name="Test Project")
        db.get_project.return_value = project
        
        task = Mock(status="completed")
        db.get_project_tasks.return_value = [task]
        
        state = compute_current_state("proj1", db)
        assert state == ProjectState.COMPLETED

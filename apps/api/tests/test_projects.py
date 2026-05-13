import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
from models import ProjectReadResponse, ProjectState


class TestProjectEndpoints:
    """Integration tests for project endpoints."""

    def test_get_project_with_state_planning(self, client):
        """
        Test GET /projects/{id} returns project with PLANNING state.
        
        Given: A project exists with no started tasks
        When: GET /projects/{id} is called
        Then: Response includes state=planning
        """
        project_id = "test-proj-1"
        
        with patch('routes.projects.get_db_session') as mock_db_session:
            db = Mock()
            mock_db_session.return_value = db
            
            project = Mock(id=project_id, name="Test Project", description="A test project")
            db.get_project.return_value = project
            db.get_project_tasks.return_value = []
            
            with patch('routes.projects.compute_current_state') as mock_compute:
                mock_compute.return_value = ProjectState.PLANNING
                
                response = client.get(f"/projects/{project_id}")
                
                assert response.status_code == 200
                data = response.json()
                assert data["id"] == project_id
                assert data["state"] == "planning"

    def test_get_project_with_state_in_progress(self, client):
        """
        Test GET /projects/{id} returns project with IN_PROGRESS state.
        
        Given: A project exists with some started tasks
        When: GET /projects/{id} is called
        Then: Response includes state=in_progress
        """
        project_id = "test-proj-2"
        
        with patch('routes.projects.get_db_session') as mock_db_session:
            db = Mock()
            mock_db_session.return_value = db
            
            project = Mock(id=project_id, name="Active Project", description="In progress")
            db.get_project.return_value = project
            
            task1 = Mock(status="in_progress")
            task2 = Mock(status="not_started")
            db.get_project_tasks.return_value = [task1, task2]
            
            with patch('routes.projects.compute_current_state') as mock_compute:
                mock_compute.return_value = ProjectState.IN_PROGRESS
                
                response = client.get(f"/projects/{project_id}")
                
                assert response.status_code == 200
                data = response.json()
                assert data["state"] == "in_progress"

    def test_get_project_with_state_completed(self, client):
        """
        Test GET /projects/{id} returns project with COMPLETED state.
        
        Given: A project exists with all tasks completed
        When: GET /projects/{id} is called
        Then: Response includes state=completed
        """
        project_id = "test-proj-3"
        
        with patch('routes.projects.get_db_session') as mock_db_session:
            db = Mock()
            mock_db_session.return_value = db
            
            project = Mock(id=project_id, name="Done Project", description="Completed")
            db.get_project.return_value = project
            
            task1 = Mock(status="completed")
            task2 = Mock(status="completed")
            db.get_project_tasks.return_value = [task1, task2]
            
            with patch('routes.projects.compute_current_state') as mock_compute:
                mock_compute.return_value = ProjectState.COMPLETED
                
                response = client.get(f"/projects/{project_id}")
                
                assert response.status_code == 200
                data = response.json()
                assert data["state"] == "completed"

    def test_get_project_not_found(self, client):
        """
        Test GET /projects/{id} returns 404 when project doesn't exist.
        
        Given: A project_id that doesn't exist
        When: GET /projects/{id} is called
        Then: Response is 404 Not Found
        """
        project_id = "nonexistent-proj"
        
        with patch('routes.projects.get_db_session') as mock_db_session:
            db = Mock()
            mock_db_session.return_value = db
            db.get_project.return_value = None
            
            response = client.get(f"/projects/{project_id}")
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_get_project_state_field_optional(self, client):
        """
        Test that state field can be None/null in response.
        
        Given: A project exists but state computation returns None
        When: GET /projects/{id} is called
        Then: Response includes state=null
        """
        project_id = "test-proj-4"
        
        with patch('routes.projects.get_db_session') as mock_db_session:
            db = Mock()
            mock_db_session.return_value = db
            
            project = Mock(id=project_id, name="Project", description=None)
            db.get_project.return_value = project
            
            with patch('routes.projects.compute_current_state') as mock_compute:
                mock_compute.return_value = None
                
                response = client.get(f"/projects/{project_id}")
                
                assert response.status_code == 200
                data = response.json()
                assert data["state"] is None

    def test_get_project_response_schema(self, client):
        """
        Test ProjectReadResponse schema validation.
        
        Given: A project with all fields
        When: GET /projects/{id} is called
        Then: Response conforms to ProjectReadResponse schema
        """
        project_id = "test-proj-5"
        
        with patch('routes.projects.get_db_session') as mock_db_session:
            db = Mock()
            mock_db_session.return_value = db
            
            project = Mock(
                id=project_id,
                name="Complete Project",
                description="Full description"
            )
            db.get_project.return_value = project
            
            with patch('routes.projects.compute_current_state') as mock_compute:
                mock_compute.return_value = ProjectState.PLANNING
                
                response = client.get(f"/projects/{project_id}")
                
                assert response.status_code == 200
                data = response.json()
                
                # Validate required fields
                assert "id" in data
                assert "name" in data
                assert "state" in data
                
                # Validate types
                assert isinstance(data["id"], str)
                assert isinstance(data["name"], str)
                assert data["state"] in ["planning", "in_progress", "completed", "on_hold", None]

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from models import ProjectReadResponse, ProjectState
from db.client import compute_current_state

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/{project_id}", response_model=ProjectReadResponse)
async def get_project(project_id: str, db=Depends(get_db_session)):
    """
    Get a project by ID with computed current state.
    
    The response includes a `state` field that represents the current state of the project:
    - **planning**: Project has no started tasks
    - **in_progress**: Project has active or partially completed work
    - **completed**: All project tasks are completed
    - **on_hold**: Project is on hold or inactive
    
    Args:
        project_id: The ID of the project to retrieve
        db: Database session (injected)
        
    Returns:
        ProjectReadResponse with computed state
        
    Raises:
        HTTPException: 404 if project not found
    """
    # Fetch project from database
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found"
        )
    
    # Compute current state
    state = compute_current_state(project_id, db)
    
    # Build response with state
    response = ProjectReadResponse(
        id=project.id,
        name=project.name,
        description=getattr(project, 'description', None),
        state=state
    )
    
    return response


def get_db_session():
    """Dependency to get database session."""
    # Implementation depends on your DB setup
    pass

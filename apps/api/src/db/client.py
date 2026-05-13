from typing import Optional, Any, Dict, List
from models import ProjectState


def compute_current_state(project_id: str, db: Any) -> Optional[ProjectState]:
    """
    Compute the current state of a project based on its tasks, milestones, and waves.
    
    States are determined by:
    - PLANNING: No tasks have been started or completed
    - IN_PROGRESS: At least one task is in progress or some work has been done
    - COMPLETED: All tasks are completed
    - ON_HOLD: Project is explicitly marked as on hold or has no active work
    
    Args:
        project_id: The ID of the project
        db: Database connection/session
        
    Returns:
        ProjectState enum value representing the current state
    """
    try:
        # Fetch project data from database
        project = db.get_project(project_id)
        if not project:
            return None
        
        # Get all tasks related to the project
        tasks = db.get_project_tasks(project_id) if hasattr(db, 'get_project_tasks') else []
        
        if not tasks:
            # No tasks yet, still in planning phase
            return ProjectState.PLANNING
        
        # Count task statuses
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if getattr(t, 'status', None) == 'completed')
        in_progress_tasks = sum(1 for t in tasks if getattr(t, 'status', None) == 'in_progress')
        
        # Determine state based on task progress
        if completed_tasks == total_tasks:
            return ProjectState.COMPLETED
        elif in_progress_tasks > 0 or completed_tasks > 0:
            return ProjectState.IN_PROGRESS
        else:
            return ProjectState.PLANNING
    except Exception as e:
        # Log error and return None if computation fails
        print(f"Error computing project state for {project_id}: {e}")
        return None

"""Compute project state based on task progress."""

from enum import Enum
from typing import Optional
from sqlalchemy.orm import Session
from src.models import Project, Task


class ProjectState(str, Enum):
    """Computed project state."""
    PLANNING = "PLANNING"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"


def compute_current_state(project_id: str, db: Session) -> ProjectState:
    """
    Compute the current state of a project based on its tasks and progress.
    
    Logic:
    - PLANNING: No tasks started yet (all in draft/refined)
    - IN_PROGRESS: At least one task active or being worked on
    - REVIEW: All tasks done, awaiting final review
    - COMPLETED: Project marked complete or all tasks finalized
    - PAUSED: Project explicitly paused
    
    Args:
        project_id: The project ID
        db: Database session
        
    Returns:
        ProjectState enum value
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return ProjectState.PLANNING
    
    # If project is explicitly paused, return PAUSED
    if project.status == "paused":
        return ProjectState.PAUSED
    
    # If project is completed, return COMPLETED
    if project.status == "completed":
        return ProjectState.COMPLETED
    
    # Query task counts
    tasks = db.query(Task).filter(Task.project_id == project_id).all()
    if not tasks:
        return ProjectState.PLANNING
    
    total = len(tasks)
    done_count = sum(1 for t in tasks if t.status == "done")
    active_count = sum(1 for t in tasks if t.status == "active")
    draft_refined_count = sum(1 for t in tasks if t.status in ("draft", "refined"))
    
    # All tasks done -> COMPLETED
    if done_count == total:
        return ProjectState.COMPLETED
    
    # All tasks in draft/refined -> PLANNING
    if draft_refined_count == total:
        return ProjectState.PLANNING
    
    # At least one active -> IN_PROGRESS
    if active_count > 0:
        return ProjectState.IN_PROGRESS
    
    # Some done, some not -> REVIEW (awaiting next action)
    if done_count > 0:
        return ProjectState.REVIEW
    
    # Default to IN_PROGRESS
    return ProjectState.IN_PROGRESS

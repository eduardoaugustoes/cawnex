"""Project endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from src.db.project_state import compute_current_state, ProjectState
from src.models import Project, Murder
from src.database import get_db

router = APIRouter(prefix="/projects", tags=["projects"])


# DTOs
class CreateProjectRequestDTO(BaseModel):
    """Request DTO for creating a project."""
    name: str
    one_liner: str
    murders: List[str] = Field(default_factory=list)


class ProjectReadResponseDTO(BaseModel):
    """Response DTO for reading a single project.
    
    Includes the computed current_state field.
    """
    project_id: str
    name: str
    one_liner: str
    status: str
    current_state: str  # Computed from task progress
    murders: List[str]
    created_at: str


class CreateProjectResponseDTO(BaseModel):
    """Response DTO for creating a project.
    
    Includes the computed current_state field.
    """
    project_id: str
    name: str
    status: str
    current_state: str  # Computed from initial state
    murders: List[str]
    created_at: str


@router.post("/", response_model=CreateProjectResponseDTO, status_code=status.HTTP_201_CREATED)
def create_project(
    request: CreateProjectRequestDTO,
    db: Session = Depends(get_db)
) -> CreateProjectResponseDTO:
    """Create a new project."""
    project = Project(
        id=request.name.lower().replace(" ", "-"),  # Simple ID generation
        name=request.name,
        one_liner=request.one_liner,
        status="draft",
        created_at=datetime.utcnow()
    )
    db.add(project)
    
    # Add murders
    murder_objs = []
    for murder_type in request.murders:
        murder = Murder(
            id=f"{project.id}-{murder_type}",
            project_id=project.id,
            type=murder_type,
            created_at=datetime.utcnow()
        )
        murder_objs.append(murder)
        db.add(murder)
    
    db.commit()
    db.refresh(project)
    
    # Compute current state
    current_state = compute_current_state(project.id, db)
    
    return CreateProjectResponseDTO(
        project_id=project.id,
        name=project.name,
        status=project.status,
        current_state=current_state.value,
        murders=request.murders,
        created_at=project.created_at.isoformat()
    )


@router.get("/{project_id}", response_model=ProjectReadResponseDTO)
def get_project(
    project_id: str,
    db: Session = Depends(get_db)
) -> ProjectReadResponseDTO:
    """Get a project by ID.
    
    Enriches response with computed current_state.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get murder types
    murders = db.query(Murder).filter(Murder.project_id == project_id).all()
    murder_types = [m.type for m in murders]
    
    # Compute current state
    current_state = compute_current_state(project_id, db)
    
    return ProjectReadResponseDTO(
        project_id=project.id,
        name=project.name,
        one_liner=project.one_liner,
        status=project.status,
        current_state=current_state.value,
        murders=murder_types,
        created_at=project.created_at.isoformat()
    )


@router.get("", response_model=List[ProjectReadResponseDTO])
def list_projects(
    db: Session = Depends(get_db)
) -> List[ProjectReadResponseDTO]:
    """List all projects.
    
    Enriches each response with computed current_state.
    """
    projects = db.query(Project).all()
    result = []
    
    for project in projects:
        # Get murder types
        murders = db.query(Murder).filter(Murder.project_id == project.id).all()
        murder_types = [m.type for m in murders]
        
        # Compute current state
        current_state = compute_current_state(project.id, db)
        
        result.append(
            ProjectReadResponseDTO(
                project_id=project.id,
                name=project.name,
                one_liner=project.one_liner,
                status=project.status,
                current_state=current_state.value,
                murders=murder_types,
                created_at=project.created_at.isoformat()
            )
        )
    
    return result

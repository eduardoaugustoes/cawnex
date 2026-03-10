"""Project CRUD + repository linking."""

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cawnex_core.models import Tenant, Repository
from cawnex_core.models.project import Project, ProjectRepository, Vision
from cawnex_core.enums import ProjectStatus
from cawnex_core.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse,
    ProjectRepoCreate, ProjectRepositoryResponse,
)
from cawnex_api.deps import get_db, get_tenant

router = APIRouter(prefix="/projects", tags=["projects"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


def _project_to_response(project: Project) -> ProjectResponse:
    repos = []
    for pr in (project.project_repositories or []):
        repos.append(ProjectRepositoryResponse(
            id=pr.id,
            repository_id=pr.repository_id,
            github_full_name=pr.repository.github_full_name if pr.repository else "unknown",
            role=pr.role,
            added_at=pr.created_at,
        ))
    return ProjectResponse(
        id=project.id,
        name=project.name,
        slug=project.slug,
        status=ProjectStatus(project.status),
        config=project.config,
        repositories=repos,
        has_vision=project.vision is not None,
        milestone_count=len(project.milestones) if project.milestones else 0,
        task_count=len(project.tasks) if project.tasks else 0,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _project_load_options():
    return [
        selectinload(Project.project_repositories).selectinload(ProjectRepository.repository),
        selectinload(Project.vision),
        selectinload(Project.milestones),
        selectinload(Project.tasks),
    ]


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    slug = body.slug or _slugify(body.name)

    # Check uniqueness
    existing = (await db.execute(
        select(Project).where(Project.tenant_id == tenant.id, Project.slug == slug)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(409, f"Project with slug '{slug}' already exists")

    project = Project(
        tenant_id=tenant.id,
        name=body.name,
        slug=slug,
        status=ProjectStatus.DRAFT,
    )
    db.add(project)
    await db.flush()

    # Create empty vision
    vision = Vision(project_id=project.id, content="", version=0)
    db.add(vision)
    await db.flush()

    # Reload with relationships
    result = await db.execute(
        select(Project).where(Project.id == project.id).options(*_project_load_options())
    )
    project = result.scalar_one()
    return _project_to_response(project)


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    status: ProjectStatus | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    query = select(Project).where(Project.tenant_id == tenant.id)
    if status:
        query = query.where(Project.status == status)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    projects = (await db.execute(
        query.options(*_project_load_options())
        .order_by(Project.created_at.desc())
        .offset((page - 1) * limit).limit(limit)
    )).scalars().unique().all()

    return ProjectListResponse(
        items=[_project_to_response(p) for p in projects],
        total=total, page=page, limit=limit,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.tenant_id == tenant.id)
        .options(*_project_load_options())
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    return _project_to_response(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    body: ProjectUpdate,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id, Project.tenant_id == tenant.id)
        .options(*_project_load_options())
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")

    if body.name is not None:
        project.name = body.name
    if body.status is not None:
        project.status = body.status

    await db.flush()
    return _project_to_response(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: int,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.tenant_id == tenant.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    await db.delete(project)
    await db.flush()


# === Repository Linking ===

@router.post("/{project_id}/repos", response_model=ProjectRepositoryResponse, status_code=201)
async def add_repo_to_project(
    project_id: int,
    body: ProjectRepoCreate,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    # Verify project
    project = (await db.execute(
        select(Project).where(Project.id == project_id, Project.tenant_id == tenant.id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")

    # Find or create repo
    repo = (await db.execute(
        select(Repository).where(
            Repository.tenant_id == tenant.id,
            Repository.github_full_name == body.github_full_name,
        )
    )).scalar_one_or_none()

    if not repo:
        repo = Repository(
            tenant_id=tenant.id,
            github_full_name=body.github_full_name,
            clone_url=f"https://github.com/{body.github_full_name}.git",
        )
        db.add(repo)
        await db.flush()

    # Check not already linked
    existing = (await db.execute(
        select(ProjectRepository).where(
            ProjectRepository.project_id == project_id,
            ProjectRepository.repository_id == repo.id,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "Repository already linked to this project")

    pr = ProjectRepository(
        project_id=project_id,
        repository_id=repo.id,
        role=body.role,
    )
    db.add(pr)
    await db.flush()

    return ProjectRepositoryResponse(
        id=pr.id,
        repository_id=repo.id,
        github_full_name=repo.github_full_name,
        role=pr.role,
        added_at=pr.created_at,
    )


@router.delete("/{project_id}/repos/{repo_link_id}", status_code=204)
async def remove_repo_from_project(
    project_id: int,
    repo_link_id: int,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    # Verify project ownership
    project = (await db.execute(
        select(Project).where(Project.id == project_id, Project.tenant_id == tenant.id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")

    pr = (await db.execute(
        select(ProjectRepository).where(
            ProjectRepository.id == repo_link_id,
            ProjectRepository.project_id == project_id,
        )
    )).scalar_one_or_none()
    if not pr:
        raise HTTPException(404, "Repository link not found")

    await db.delete(pr)
    await db.flush()

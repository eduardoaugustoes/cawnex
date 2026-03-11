"""Repository management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cawnex_core.models import Tenant, Repository
from cawnex_api.deps import get_db, get_tenant
from cawnex_git_ops import GitHubAPI
from pydantic import BaseModel


class RepoConnect(BaseModel):
    github_full_name: str  # "owner/repo"
    github_token: str  # PAT — used once to fetch metadata, not stored


class RepoResponse(BaseModel):
    id: int
    github_full_name: str
    default_branch: str
    clone_url: str
    language: str | None
    framework: str | None
    is_active: bool

    model_config = {"from_attributes": True}


router = APIRouter(prefix="/repos", tags=["repositories"])


@router.post("", response_model=RepoResponse, status_code=201)
async def connect_repo(
    body: RepoConnect,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    # Check not already connected
    existing = await db.execute(
        select(Repository).where(
            Repository.tenant_id == tenant.id,
            Repository.github_full_name == body.github_full_name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Repository '{body.github_full_name}' already connected")

    # Fetch repo metadata from GitHub
    gh = GitHubAPI(body.github_token)
    try:
        repo_data = await gh.get_repo(body.github_full_name)
    except Exception:
        raise HTTPException(400, f"Cannot access '{body.github_full_name}'. Check token permissions.")
    finally:
        await gh.close()

    # Read CAWNEX.md if present
    cawnex_md = await gh.get_file_content(body.github_full_name, "CAWNEX.md") if False else None

    repo = Repository(
        tenant_id=tenant.id,
        github_full_name=body.github_full_name,
        default_branch=repo_data.get("default_branch", "main"),
        clone_url=repo_data.get("clone_url", f"https://github.com/{body.github_full_name}.git"),
        language=repo_data.get("language"),
        cawnex_md=cawnex_md,
    )
    db.add(repo)
    await db.flush()
    return repo


@router.get("", response_model=list[RepoResponse])
async def list_repos(
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Repository).where(Repository.tenant_id == tenant.id, Repository.is_active.is_(True))
    )
    return result.scalars().all()


@router.delete("/{repo_id}", status_code=204)
async def disconnect_repo(
    repo_id: int,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id, Repository.tenant_id == tenant.id)
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(404, "Repository not found")
    repo.is_active = False
    await db.flush()

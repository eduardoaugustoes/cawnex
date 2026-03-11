"""Webhook payload schemas."""

from typing import Optional

from pydantic import BaseModel


class GitHubIssuePayload(BaseModel):
    """Simplified GitHub issue webhook payload."""

    action: str  # opened, edited, labeled, etc.
    issue: "GitHubIssue"
    repository: "GitHubRepository"
    installation: Optional["GitHubInstallation"] = None


class GitHubIssue(BaseModel):
    number: int
    title: str
    body: Optional[str] = None
    html_url: str
    labels: list["GitHubLabel"] = []
    state: str


class GitHubRepository(BaseModel):
    full_name: str  # "owner/repo"
    clone_url: str
    default_branch: str


class GitHubInstallation(BaseModel):
    id: int


class GitHubLabel(BaseModel):
    name: str


# Rebuild for forward refs
GitHubIssuePayload.model_rebuild()

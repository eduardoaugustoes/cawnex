"""Git worktree management — isolated nests for each agent execution."""

from __future__ import annotations

import shutil
from pathlib import Path

from git import Repo


class WorktreeManager:
    """Manages git worktrees (nests) for agent isolation.

    Each agent gets its own worktree branched from the target branch.
    After execution, the worktree is cleaned up.

    Convention: branch = crow/{task_id}-{agent_slug}
                worktree = {base_dir}/nests/{branch_name}
    """

    def __init__(self, repo_path: str | Path, nests_dir: str | Path | None = None) -> None:
        self.repo_path = Path(repo_path)
        self.repo = Repo(self.repo_path)
        self.nests_dir = Path(nests_dir) if nests_dir else self.repo_path / "nests"
        self.nests_dir.mkdir(parents=True, exist_ok=True)

    def create_nest(
        self,
        task_id: int | str,
        agent_slug: str,
        base_branch: str = "main",
    ) -> Path:
        """Create an isolated worktree for an agent.

        Returns the worktree path.
        """
        branch_name = f"crow/{task_id}-{agent_slug}"
        worktree_path = self.nests_dir / branch_name.replace("/", "-")

        # Ensure base branch is up to date
        if "origin" in [r.name for r in self.repo.remotes]:
            self.repo.remotes.origin.fetch()

        # Create branch from base
        base_ref = f"origin/{base_branch}" if "origin" in [r.name for r in self.repo.remotes] else base_branch
        self.repo.git.worktree("add", "-b", branch_name, str(worktree_path), base_ref)

        return worktree_path

    def remove_nest(self, task_id: int | str, agent_slug: str, delete_branch: bool = False) -> None:
        """Remove a worktree and optionally its branch."""
        branch_name = f"crow/{task_id}-{agent_slug}"
        worktree_path = self.nests_dir / branch_name.replace("/", "-")

        if worktree_path.exists():
            self.repo.git.worktree("remove", str(worktree_path), "--force")

        if delete_branch:
            try:
                self.repo.git.branch("-D", branch_name)
            except Exception:
                pass  # Branch may not exist

    def list_nests(self) -> list[dict]:
        """List all active worktrees."""
        output = self.repo.git.worktree("list", "--porcelain")
        nests = []
        current: dict = {}

        for line in output.split("\n"):
            if line.startswith("worktree "):
                if current:
                    nests.append(current)
                current = {"path": line.split(" ", 1)[1]}
            elif line.startswith("branch "):
                current["branch"] = line.split(" ", 1)[1].replace("refs/heads/", "")
            elif line == "":
                if current:
                    nests.append(current)
                    current = {}

        if current:
            nests.append(current)

        # Filter to only crow/ branches
        return [n for n in nests if n.get("branch", "").startswith("crow/")]

    def cleanup_all(self) -> int:
        """Remove all agent worktrees. Returns count removed."""
        nests = self.list_nests()
        for nest in nests:
            path = Path(nest["path"])
            if path.exists():
                self.repo.git.worktree("remove", str(path), "--force")
            branch = nest.get("branch")
            if branch:
                try:
                    self.repo.git.branch("-D", branch)
                except Exception:
                    pass
        return len(nests)

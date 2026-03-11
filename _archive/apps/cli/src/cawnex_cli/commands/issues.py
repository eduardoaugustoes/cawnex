"""cawnex issues — list GitHub issues from connected repo."""

import asyncio
import subprocess
import json
import click
from rich.console import Console
from rich.table import Table

from cawnex_cli import config as cfg

console = Console()


@click.command()
@click.option("--repo", default=None, help="Repository (owner/repo).")
@click.option("--label", "-l", default=None, help="Filter by label.")
@click.option("--limit", "-n", default=20, help="Max issues to show.")
def issues(repo: str | None, label: str | None, limit: int):
    """📋 List open GitHub issues from the connected repo."""
    config = cfg.load_config()
    repo = repo or config.get("default_repo")

    if not repo:
        console.print("[red]No repo configured. Run: cawnex setup repo <owner/repo>[/]")
        return

    # Use gh CLI
    cmd = ["gh", "issue", "list", "--repo", repo, "--state", "open",
           "--limit", str(limit), "--json", "number,title,labels,createdAt,author"]
    if label:
        cmd.extend(["--label", label])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        console.print(f"[red]Failed to fetch issues: {result.stderr}[/]")
        return

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        console.print("[red]Invalid response from gh CLI[/]")
        return

    if not data:
        console.print(f"[dim]No open issues in {repo}[/]")
        return

    table = Table(title=f"📋 Open Issues — {repo}", show_header=True, border_style="dim")
    table.add_column("#", style="cyan", width=5)
    table.add_column("Title", ratio=4)
    table.add_column("Labels", ratio=2)
    table.add_column("Author", style="dim", width=15)

    for issue in data:
        labels = ", ".join(l["name"] for l in issue.get("labels", []))
        has_cawnex = any(l["name"] == "cawnex" for l in issue.get("labels", []))
        num_style = "[bold green]" if has_cawnex else "[cyan]"
        author = issue.get("author", {}).get("login", "")

        table.add_row(
            f"{num_style}{issue['number']}[/]",
            issue["title"],
            labels or "[dim]—[/]",
            author,
        )

    console.print(table)
    console.print()
    console.print("[dim]Run an issue:  cawnex issue <number>[/]")
    console.print("[dim]Issues with [bold green]cawnex[/] label are auto-triggered via webhook.[/]")

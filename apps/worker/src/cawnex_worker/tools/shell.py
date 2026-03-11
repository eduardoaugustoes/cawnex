"""Shell tool — sandboxed command execution in agent workspace."""

from __future__ import annotations

import asyncio
import subprocess

from anthropic.lib.tools import beta_tool


@beta_tool
def RunCommand(command: str, workspace: str = ".") -> str:
    """Run a shell command in the workspace directory. Use for: running tests, linting, building, etc.

    Args:
        command: Shell command to execute.
        workspace: Working directory.
    """
    # Safety: block destructive commands
    blocked = ["rm -rf /", "mkfs", "dd if=", ":(){ :|:& };:", "shutdown", "reboot"]
    for b in blocked:
        if b in command:
            return f"Error: Command blocked for safety: contains '{b}'"

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=120,  # 2 min max
        )

        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"

        # Truncate
        if len(output) > 50_000:
            output = output[:50_000] + f"\n\n... [truncated, {len(output)} chars total]"

        if result.returncode != 0:
            output += f"\n\n[exit code: {result.returncode}]"

        return output.strip() or "(no output)"

    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 120 seconds"
    except Exception as e:
        return f"Error: {e}"

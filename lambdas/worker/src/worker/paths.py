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

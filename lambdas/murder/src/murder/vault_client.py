"""Lightweight vault reader — checks secret availability via DynamoDB."""

from __future__ import annotations

import re
from typing import Any

from murder.blackboard import Blackboard

_SECRET_PATTERN = re.compile(r"\{\{secret:([a-zA-Z0-9_\-]+)\}\}")


def list_required_secrets(instructions: str) -> list[str]:
    """Scan instructions for {{secret:...}} patterns and return secret names."""
    return _SECRET_PATTERN.findall(instructions)


def has_secret(
    blackboard: Blackboard,
    tenant: str,
    project: str,
    name: str,
) -> bool:
    """Check if a secret exists in the vault partition."""
    vault_pk = f"T#{tenant}#VAULT"
    vault_sk = f"P#{project}#S#{name}"
    item = blackboard.read(vault_pk, vault_sk)
    return item is not None

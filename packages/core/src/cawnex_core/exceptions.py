"""Cawnex exceptions."""


class CawnexError(Exception):
    """Base exception for all Cawnex errors."""


class BudgetExceededError(CawnexError):
    """Monthly LLM budget limit reached."""


class GuardCancelError(CawnexError):
    """Execution cancelled by guard (hallucination, loop, timeout)."""


class ExecutionTimeoutError(CawnexError):
    """Execution exceeded max allowed time."""


class MergeConflictError(CawnexError):
    """Git merge conflict during synchronized merge."""


class SynchronizedMergeError(CawnexError):
    """One or more PRs failed during synchronized merge."""


class ProviderError(CawnexError):
    """LLM provider returned an error."""


class AuthError(CawnexError):
    """Authentication or authorization failure."""


class TenantNotFoundError(CawnexError):
    """Tenant not found for the given context."""


class RetryExhaustedError(CawnexError):
    """Max retry attempts reached."""

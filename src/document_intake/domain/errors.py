"""PII-safe domain errors."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for safe domain errors."""


class InvalidValueError(DomainError):
    """Raised when a value object or entity invariant is violated."""


class InvalidTransitionError(DomainError):
    """Raised when a documented transition is not allowed."""


class VerificationPolicyError(DomainError):
    """Raised when verification policy rejects an operation."""


class SnapshotInvariantError(DomainError):
    """Raised when snapshot creation or construction invariants fail."""

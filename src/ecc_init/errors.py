from __future__ import annotations


class EccInitError(Exception):
    """Base class for user-facing ecc-init errors."""


class ConfigError(EccInitError):
    """Configuration or manifest data is malformed."""


class EnvironmentError(EccInitError):
    """The local environment cannot satisfy the requested operation."""


class SourceError(EccInitError):
    """A source provider cannot resolve or fetch requested content."""


class IntegrityError(EccInitError):
    """Downloaded or projected content does not match expected integrity."""


class ConflictError(EccInitError):
    """A requested change conflicts with existing user-managed data."""


class TransactionError(EccInitError):
    """A transactional install, update, or rollback operation failed."""


class MigrationError(EccInitError):
    """Legacy state cannot be migrated safely."""

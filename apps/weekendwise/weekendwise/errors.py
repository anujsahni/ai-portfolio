"""Errors with safe, actionable messages.

`str(error)` never includes credentials, prompts, or raw API payloads, so it is
safe to show in logs and (for user-facing errors) in the UI.
"""


class WeekendWiseError(Exception):
    """Base class. `hint` tells the operator what to do next."""

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return f"{self.message} {self.hint}".strip()


class ConfigError(WeekendWiseError):
    """Missing or invalid configuration, or no usable credentials."""


class ModelAccessError(WeekendWiseError):
    """Permission denied, or the model isn't available in the configured location."""


class QuotaError(WeekendWiseError):
    """Quota or rate limit reached."""


class ModelTimeoutError(WeekendWiseError):
    """The model call took longer than the configured timeout."""


class ModelRequestError(WeekendWiseError):
    """The request was rejected as invalid (for example, input too large)."""


class ModelServiceError(WeekendWiseError):
    """A temporary error on Google's side (5xx)."""


class ModelResponseError(WeekendWiseError):
    """The model returned no usable text (blocked, empty, or cut off)."""


class EmbeddingDimensionError(WeekendWiseError):
    """An embedding didn't have the configured number of dimensions."""

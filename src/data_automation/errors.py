"""Exceptions raised deliberately by the toolkit.

Every expected, explainable failure derives from :class:`AutomationError`, so that the
CLI can report it cleanly and map it to a documented exit code.
"""

from __future__ import annotations


class AutomationError(Exception):
    """Base class for all expected toolkit errors."""


class WorkflowLoadError(AutomationError):
    """The workflow file cannot be read or is not well-formed YAML."""


class WorkflowValidationError(AutomationError):
    """The workflow file was read but its content is invalid.

    Attributes:
        issues: One human-readable message per problem, each prefixed with its location.
    """

    def __init__(self, issues: list[str]) -> None:
        self.issues = list(issues)
        super().__init__(f"{len(self.issues)} configuration problem(s):\n  - " + "\n  - ".join(self.issues))


class ParameterError(AutomationError):
    """A run parameter given on the command line is malformed."""

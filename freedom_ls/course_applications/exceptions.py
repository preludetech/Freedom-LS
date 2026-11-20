"""Errors raised by the functions that change an application's state."""

from __future__ import annotations


class ApplicationTransitionError(Exception):
    """A state change the application cannot make."""


class ApplicationStateError(ApplicationTransitionError):
    """The application is in a state the move does not start from."""

    def __init__(self, *, current_state: str) -> None:
        self.current_state = current_state
        super().__init__(f"Application is {current_state}.")


class UnclaimedApplicationError(ApplicationTransitionError):
    """The application has no account yet, so a decision on it has nobody to reach."""

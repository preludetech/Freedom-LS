"""Errors a panel raises to say why it cannot show its body."""

__all__ = ["PanelBodyTooLargeError"]


class PanelBodyTooLargeError(Exception):
    """A panel's body is too large to show. str() is the message the region shows."""

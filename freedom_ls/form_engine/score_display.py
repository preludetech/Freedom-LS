def format_score(earned: int, possible: int) -> str:
    """Render a score as ``earned / possible``, e.g. ``7 / 10``.

    Earned above possible is rendered as given, so a bonus score of 12 out of 10
    is ``12 / 10``. Raises ``ValueError`` if either value is negative.
    """
    if earned < 0:
        raise ValueError(f"earned must not be negative, got {earned}")
    if possible < 0:
        raise ValueError(f"possible must not be negative, got {possible}")
    return f"{earned} / {possible}"

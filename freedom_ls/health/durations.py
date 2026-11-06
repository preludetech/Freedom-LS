SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600


def format_duration(seconds: int) -> str:
    """Render whole seconds as hours and zero-padded minutes, e.g. ``1h 02m``.

    Remaining seconds are dropped, never rounded up, so 59 seconds is ``0h 00m``.
    Hours are not padded or capped. Raises ``ValueError`` for negative input.
    """
    if seconds < 0:
        raise ValueError(f"seconds must not be negative, got {seconds}")
    hours, remainder = divmod(seconds, SECONDS_PER_HOUR)
    minutes = remainder // SECONDS_PER_MINUTE
    return f"{hours}h {minutes:02d}m"

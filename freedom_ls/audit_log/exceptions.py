class AppendOnlyError(Exception):
    """An audit log entry was about to change or disappear."""

    def __init__(self, message: str = "Audit log entries are append-only.") -> None:
        super().__init__(message)

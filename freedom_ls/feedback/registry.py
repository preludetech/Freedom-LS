_registry: dict[str, str] = {}


def register_trigger_point(name: str, description: str) -> None:
    """Register a trigger point. Called by apps in their AppConfig.ready()."""
    _registry[name] = description


def get_trigger_points() -> dict[str, str]:
    """Return all registered trigger points."""
    return dict(_registry)


def is_valid_trigger_point(name: str) -> bool:
    return name in _registry

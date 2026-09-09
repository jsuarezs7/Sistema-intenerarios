def internal_url(value: str) -> str:
    """Render hostport references omit the scheme; Compose URLs already include it."""
    return value.rstrip("/") if "://" in value else "http://" + value.rstrip("/")

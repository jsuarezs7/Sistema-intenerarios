def internal_url(value: str) -> str:
    """Render hostport references omit the scheme; Compose URLs already include it.

    Only used for service-to-service calls inside the private network (Render private
    services / Compose network), which do not terminate TLS; public traffic uses HTTPS.
    """
    if "://" in value:
        return value.rstrip("/")
    return "http://" + value.rstrip("/")  # NOSONAR - private network without TLS (see docstring)

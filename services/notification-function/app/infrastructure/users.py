from sqlalchemy import text


class SqlUserContacts:
    def __init__(self, sessions):
        self.sessions = sessions

    async def phone_for(self, user_id: str) -> str | None:
        async with self.sessions() as session:
            result = await session.execute(
                text("SELECT phone FROM users WHERE username = :username"),
                {"username": user_id},
            )
            row = result.first()
            return None if row is None else row[0]


class ConsoleSmsSender:
    """Adapter: local SMS implementation that logs instead of calling a provider."""

    async def send(self, phone: str, message: str) -> None:
        import logging

        logging.getLogger(__name__).info(
            "sms_simulated", extra={"phone": phone, "sms_message": message}
        )

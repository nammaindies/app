from typing import Any, Protocol
from uuid import UUID


class AuthProvider(Protocol):
    """Seam for authentication methods (magic-link, OAuth, ...). Every
    provider resolves to an `observer_id` -- the session layer downstream
    knows nothing about how that observer authenticated."""

    async def resolve(self, conn: Any, **kwargs: Any) -> UUID: ...

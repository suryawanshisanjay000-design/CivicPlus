from collections.abc import Callable

from supabase import Client, create_client

from config import settings


def get_supabase_client() -> Client:
    """Get Supabase client with service role key for backend operations."""
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_supabase_anon_client() -> Client:
    """Get Supabase client with anon key for public operations."""
    return create_client(settings.supabase_url, settings.supabase_anon_key)


class _LazyClient:
    """Create the underlying client on first use so importing the app never requires live credentials."""

    def __init__(self, factory: Callable[[], Client]) -> None:
        self._factory = factory
        self._client: Client | None = None

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        if self._client is None:
            self._client = self._factory()
        return getattr(self._client, name)


# Global client instances (lazily initialized)
supabase: _LazyClient = _LazyClient(get_supabase_client)
supabase_anon: _LazyClient = _LazyClient(get_supabase_anon_client)

"""Pruebas de seleccion de llave backend para adaptadores Supabase."""

from app.core.settings import load_settings
from app.documents.supabase_repository import SupabaseDocumentRepository


def test_backend_repositories_prefer_service_role_key():
    calls = []
    settings = load_settings(
        environ={
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_KEY": "anon-key",
            "SUPABASE_SERVICE_ROLE_KEY": "service-role-key",
        }
    )

    class FakeClient:
        def table(self, _name):
            raise RuntimeError("table should not be used")

    repository = SupabaseDocumentRepository(
        settings=settings,
        client_factory=lambda url, key: calls.append((url, key)) or FakeClient(),
    )

    try:
        repository.get_document("doc")
    except RuntimeError:
        pass

    assert calls == [("https://example.supabase.co", "service-role-key")]

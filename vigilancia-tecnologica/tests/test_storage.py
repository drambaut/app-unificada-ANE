"""Pruebas del adaptador Supabase Storage sin red."""

from pathlib import Path

import pytest

from app.core.settings import load_settings
from app.storage.errors import (
    StorageConfigurationError,
    StorageError,
    StorageValidationError,
)
from app.storage.supabase_storage import SupabaseSourceDocumentStorage


class FakeBucket:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.upload_calls: list[dict] = []
        self.removed: list[list[str]] = []

    def upload(self, path: str, content: bytes, file_options: dict) -> None:
        self.upload_calls.append(
            {"path": path, "content": content, "file_options": file_options}
        )
        self.objects[path] = content

    def download(self, path: str) -> bytes:
        return self.objects[path]

    def remove(self, paths: list[str]) -> None:
        self.removed.append(paths)
        for path in paths:
            self.objects.pop(path, None)


class FakeStorage:
    def __init__(self, bucket: FakeBucket) -> None:
        self.bucket = bucket
        self.bucket_names: list[str] = []

    def from_(self, bucket_name: str) -> FakeBucket:
        self.bucket_names.append(bucket_name)
        return self.bucket


class FakeClient:
    def __init__(self, bucket: FakeBucket) -> None:
        self.storage = FakeStorage(bucket)


def settings(tmp_path: Path, **overrides):
    environ = {
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_KEY": "service-key",
    }
    environ.update(overrides)
    return load_settings(project_root=tmp_path, env_file=tmp_path / ".env", environ=environ)


def test_upload_uses_canonical_path_bucket_and_file_options(tmp_path: Path) -> None:
    bucket = FakeBucket()
    storage = SupabaseSourceDocumentStorage(
        settings=settings(tmp_path),
        client=FakeClient(bucket),
    )

    stored = storage.upload_source_document(
        source_type="institutional plan",
        document_id="doc 123",
        file_name="../PMGE Agenda.pdf",
        content=b"%PDF-1.4",
        content_type="application/pdf",
        upsert=True,
    )

    assert stored.bucket == "source-documents"
    assert stored.path == "institutional-plan/doc-123/PMGE-Agenda.pdf"
    assert stored.size_bytes == 8
    assert bucket.upload_calls == [
        {
            "path": stored.path,
            "content": b"%PDF-1.4",
            "file_options": {
                "content-type": "application/pdf",
                "upsert": "true",
            },
        }
    ]


def test_download_and_delete_use_same_bucket(tmp_path: Path) -> None:
    bucket = FakeBucket()
    bucket.objects["surveillance/doc-1/source.pdf"] = b"content"
    client = FakeClient(bucket)
    storage = SupabaseSourceDocumentStorage(
        settings=settings(tmp_path),
        client=client,
    )

    assert storage.download_source_document("surveillance/doc-1/source.pdf") == b"content"

    storage.delete_source_document("surveillance/doc-1/source.pdf")

    assert bucket.removed == [["surveillance/doc-1/source.pdf"]]
    assert client.storage.bucket_names == ["source-documents", "source-documents"]


def test_rejects_empty_files_disallowed_mime_and_oversized_files(tmp_path: Path) -> None:
    storage = SupabaseSourceDocumentStorage(
        settings=settings(tmp_path, SUPABASE_STORAGE_FILE_SIZE_LIMIT_BYTES="3"),
        client=FakeClient(FakeBucket()),
    )

    with pytest.raises(StorageValidationError, match="vacio"):
        storage.upload_source_document(
            source_type="surveillance",
            document_id="doc-1",
            file_name="a.pdf",
            content=b"",
            content_type="application/pdf",
        )
    with pytest.raises(StorageValidationError, match="no permitido"):
        storage.upload_source_document(
            source_type="surveillance",
            document_id="doc-1",
            file_name="a.txt",
            content=b"ok",
            content_type="text/plain",
        )
    with pytest.raises(StorageValidationError, match="limite"):
        storage.upload_source_document(
            source_type="surveillance",
            document_id="doc-1",
            file_name="a.pdf",
            content=b"1234",
            content_type="application/pdf",
        )


def test_missing_supabase_configuration_is_reported(tmp_path: Path) -> None:
    storage = SupabaseSourceDocumentStorage(
        settings=load_settings(
            project_root=tmp_path,
            env_file=tmp_path / ".env",
            environ={},
        ),
    )

    with pytest.raises(StorageConfigurationError, match="SUPABASE_URL"):
        storage.download_source_document("surveillance/doc-1/a.pdf")


def test_external_client_errors_are_wrapped(tmp_path: Path) -> None:
    class FailingBucket(FakeBucket):
        def upload(self, path: str, content: bytes, file_options: dict) -> None:
            raise RuntimeError("provider failed")

    storage = SupabaseSourceDocumentStorage(
        settings=settings(tmp_path),
        client=FakeClient(FailingBucket()),
    )

    with pytest.raises(StorageError, match="subir"):
        storage.upload_source_document(
            source_type="surveillance",
            document_id="doc-1",
            file_name="a.pdf",
            content=b"ok",
            content_type="application/pdf",
        )

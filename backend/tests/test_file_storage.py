from io import BytesIO

from fastapi import UploadFile

from backend.app.services.file_service import FileService
from backend.app.config import settings


def test_private_upload_uses_tenant_path(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "OBJECT_STORAGE_BUCKET", "")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    upload = UploadFile(filename="report.pdf", file=BytesIO(b"private file"))
    key = FileService.save_upload_file(upload, "documents", 17)
    assert key.startswith("tenant/17/documents/")
    assert FileService.get_absolute_path(key).read_bytes() == b"private file"
    assert FileService.file_size(key) == 12
    FileService.delete_file(key)
    assert not (tmp_path / key).exists()


def test_s3_upload_uses_private_tenant_key(monkeypatch):
    calls = []

    class FakeS3:
        def upload_fileobj(self, stream, bucket, key, ExtraArgs):
            calls.append((bucket, key, stream.read(), ExtraArgs))

    monkeypatch.setattr(settings, "OBJECT_STORAGE_BUCKET", "private-test-bucket")
    monkeypatch.setattr(FileService, "_s3", staticmethod(lambda: FakeS3()))
    upload = UploadFile(filename="receipt.pdf", file=BytesIO(b"receipt"))
    key = FileService.save_upload_file(upload, "documents", 8)
    assert calls == [("private-test-bucket", key, b"receipt", {"ContentType": "application/octet-stream"})]
    assert key.startswith("tenant/8/documents/")

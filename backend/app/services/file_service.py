"""Private file storage. The database record remains the authorization source."""

import os
from pathlib import Path
from tempfile import SpooledTemporaryFile
from urllib.parse import quote

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse

from backend.app.config import settings
from backend.app.utils.validators import generate_safe_filename, validate_file_upload


class FileService:
    @staticmethod
    def _s3():
        import boto3

        kwargs = {"region_name": settings.OBJECT_STORAGE_REGION}
        if settings.OBJECT_STORAGE_ENDPOINT:
            kwargs["endpoint_url"] = settings.OBJECT_STORAGE_ENDPOINT
        return boto3.client("s3", **kwargs)

    @staticmethod
    def ensure_upload_dirs():
        if settings.OBJECT_STORAGE_BUCKET:
            return
        base = Path(settings.UPLOAD_DIR)
        for sub in ("profiles", "avatars", "assignments", "study-materials", "documents", "reports"):
            (base / sub).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _key(tenant_id: int, subfolder: str, filename: str) -> str:
        if not isinstance(tenant_id, int) or tenant_id < 1:
            raise ValueError("A school context is required for file uploads")
        if subfolder not in {"profiles", "avatars", "assignments", "study-materials", "documents", "reports"}:
            raise ValueError("Invalid upload category")
        return f"tenant/{tenant_id}/{subfolder}/{filename}"

    @staticmethod
    def save_upload_file(file: UploadFile, subfolder: str = "documents", tenant_id: int = None) -> str:
        validate_file_upload(file)
        key = FileService._key(tenant_id, subfolder, generate_safe_filename(file.filename))
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        total = 0
        try:
            with SpooledTemporaryFile(max_size=2 * 1024 * 1024) as buffer:
                while chunk := file.file.read(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB")
                    buffer.write(chunk)
                buffer.seek(0)
                if settings.OBJECT_STORAGE_BUCKET:
                    FileService._s3().upload_fileobj(buffer, settings.OBJECT_STORAGE_BUCKET, key,
                                                     ExtraArgs={"ContentType": file.content_type or "application/octet-stream"})
                else:
                    destination = Path(settings.UPLOAD_DIR) / key
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with destination.open("wb") as output:
                        while chunk := buffer.read(1024 * 1024):
                            output.write(chunk)
        finally:
            file.file.close()
        return key

    @staticmethod
    def get_absolute_path(stored_path: str) -> Path:
        base = Path(settings.UPLOAD_DIR).resolve()
        target = (base / stored_path).resolve()
        if not target.is_relative_to(base):
            raise HTTPException(status_code=400, detail="Invalid file path")
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        return target

    @staticmethod
    def file_size(stored_path: str) -> int:
        if settings.OBJECT_STORAGE_BUCKET and stored_path.startswith("tenant/"):
            return FileService._s3().head_object(Bucket=settings.OBJECT_STORAGE_BUCKET, Key=stored_path)["ContentLength"]
        return os.path.getsize(FileService.get_absolute_path(stored_path))

    @staticmethod
    def download_response(stored_path: str):
        filename = Path(stored_path).name
        if settings.OBJECT_STORAGE_BUCKET and stored_path.startswith("tenant/"):
            try:
                result = FileService._s3().get_object(Bucket=settings.OBJECT_STORAGE_BUCKET, Key=stored_path)
            except Exception as exc:
                raise HTTPException(status_code=404, detail="File not found") from exc
            body = result["Body"]

            def chunks():
                try:
                    yield from body.iter_chunks(chunk_size=1024 * 1024)
                finally:
                    body.close()

            return StreamingResponse(chunks(), media_type=result.get("ContentType") or "application/octet-stream",
                                     headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})
        return FileResponse(path=FileService.get_absolute_path(stored_path), filename=filename,
                            media_type="application/octet-stream")

    @staticmethod
    def delete_file(stored_path: str):
        if settings.OBJECT_STORAGE_BUCKET and stored_path.startswith("tenant/"):
            FileService._s3().delete_object(Bucket=settings.OBJECT_STORAGE_BUCKET, Key=stored_path)
            return
        try:
            FileService.get_absolute_path(stored_path).unlink()
        except HTTPException:
            pass


file_service = FileService()

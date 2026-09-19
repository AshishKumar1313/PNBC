from pathlib import Path
import os

from fastapi import UploadFile

from app.config import get_settings

settings = get_settings()


def is_valid_pdf(file_bytes: bytes) -> bool:
    return file_bytes.startswith(b'%PDF')


def is_valid_image(file_bytes: bytes) -> bool:
    return file_bytes.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff'))


async def save_uploaded_file(file: UploadFile) -> tuple[str, str]:
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_data = await file.read()
    if not file_data:
        raise ValueError('Uploaded file is empty')

    if file.content_type in {'application/pdf'}:
        if not is_valid_pdf(file_data):
            raise ValueError('Invalid PDF file')
    elif file.content_type in {'image/png', 'image/jpeg', 'image/jpg'}:
        if not is_valid_image(file_data):
            raise ValueError('Invalid image file')
    else:
        raise ValueError('Unsupported file type')

    if len(file_data) > settings.max_upload_size:
        raise ValueError('File is too large')

    safe_name = file.filename or 'uploaded_file'
    file_path = upload_dir / safe_name
    with open(file_path, 'wb') as f:
        f.write(file_data)

    return str(file_path), safe_name

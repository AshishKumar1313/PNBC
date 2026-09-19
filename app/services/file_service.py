import hashlib
import os
import re
import uuid
from typing import Tuple

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings

settings = get_settings()

# Known magic bytes signatures
MAGIC_SIGNATURES = {
    'application/pdf': [b'%PDF'],
    'image/png': [b'\x89PNG\r\n\x1a\n'],
    'image/jpeg': [b'\xff\xd8\xff'],
    'image/jpg': [b'\xff\xd8\xff'],
}


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal or invalid characters."""
    base = os.path.basename(filename)
    clean = re.sub(r'[^a-zA-Z0-9_.-]', '_', base)
    return clean or 'unnamed_file'


def detect_mime_type_from_bytes(header: bytes) -> str | None:
    """Detect MIME type from header magic bytes."""
    for mime_type, signatures in MAGIC_SIGNATURES.items():
        for sig in signatures:
            if header.startswith(sig):
                return 'image/jpeg' if mime_type == 'image/jpg' else mime_type
    return None


async def validate_and_save_upload(file: UploadFile) -> Tuple[str, str, int, str, str]:
    """
    Validates the uploaded file:
    - Size within max limit
    - File extension in allowed list
    - Magic bytes verify real PDF/PNG/JPEG
    - Generates SHA256 hash
    - Saves to secure storage location

    Returns:
        (stored_relative_path, original_filename, file_size, mime_type, file_hash)
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Filename cannot be empty',
        )

    clean_filename = sanitize_filename(file.filename)
    _, ext = os.path.splitext(clean_filename.lower())

    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Allowed extensions: {settings.allowed_extensions}",
        )

    # Read content
    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Uploaded file is empty',
        )

    if file_size > settings.max_upload_size:
        max_mb = settings.max_upload_size // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'File size exceeds maximum allowed limit of {max_mb} MB',
        )

    # Check magic bytes
    header = content[:16]
    detected_mime = detect_mime_type_from_bytes(header)

    if not detected_mime:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid or corrupted file: file header signature does not match supported PDF or image formats',
        )

    # Extension vs mime check
    if ext == '.pdf' and detected_mime != 'application/pdf':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File extension '.pdf' does not match content format (not a valid PDF)",
        )
    if ext in ['.png'] and detected_mime != 'image/png':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File extension '.png' does not match content format (not a valid PNG)",
        )
    if ext in ['.jpg', '.jpeg'] and detected_mime != 'image/jpeg':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File extension does not match JPEG content format",
        )

    # Calculate SHA256
    file_hash = hashlib.sha256(content).hexdigest()

    # Ensure storage dir exists
    os.makedirs(settings.upload_dir, exist_ok=True)

    # Secure unique storage path
    unique_name = f"{uuid.uuid4().hex}_{clean_filename}"
    file_path = os.path.join(settings.upload_dir, unique_name)

    with open(file_path, 'wb') as f:
        f.write(content)

    return file_path, clean_filename, file_size, detected_mime, file_hash

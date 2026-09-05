"""Shared upload validation for user-submitted files.

Lecturers upload course notes and (potentially) video; students upload
avatars. Without checks an attacker can fill the disk with arbitrary files.
Every upload path should validate extension + size here.
"""
import os

# Accepted extension (lowercase, leading dot) -> human label.
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
DOC_EXTS = {'.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
            '.txt', '.md', '.csv', '.zip'}
VIDEO_EXTS = {'.mp4', '.webm', '.mkv', '.mov'}

MAX_IMAGE_BYTES = 2 * 1024 * 1024      # 2 MB
MAX_DOC_BYTES = 25 * 1024 * 1024       # 25 MB
MAX_VIDEO_BYTES = 200 * 1024 * 1024    # 200 MB


def _ext(name):
    return os.path.splitext((name or '').lower())[1]


def validate_image_upload(upload):
    """Validate an avatar/thumbnail ImageField upload. Raises ValueError."""
    ext = _ext(upload.name)
    if ext not in IMAGE_EXTS:
        raise ValueError('Image must be PNG, JPG, GIF or WEBP.')
    if upload.size and upload.size > MAX_IMAGE_BYTES:
        raise ValueError('Image is too large (max 2 MB).')


def validate_doc_upload(upload):
    """Validate a lecture notes / handout FileField upload. Raises ValueError."""
    ext = _ext(upload.name)
    if ext not in DOC_EXTS:
        raise ValueError(
            'Unsupported file type. Use PDF, Word, PowerPoint, Excel, '
            'text, Markdown, CSV or ZIP.')
    if upload.size and upload.size > MAX_DOC_BYTES:
        raise ValueError('File is too large (max 25 MB).')


def validate_video_upload(upload):
    """Validate a lecture video FileField upload. Raises ValueError."""
    ext = _ext(upload.name)
    if ext not in VIDEO_EXTS:
        raise ValueError('Video must be MP4, WebM, MKV or MOV.')
    if upload.size and upload.size > MAX_VIDEO_BYTES:
        raise ValueError('Video is too large (max 200 MB).')
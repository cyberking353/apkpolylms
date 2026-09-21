"""Shared upload validation for user-submitted files.

Lecturers upload course notes; students upload avatars. Without checks an
attacker can fill the disk with arbitrary files. Every upload path should
validate extension + size here.

Notes uploads are capped at 10 MB and PDFs are compressed (best-effort via
Ghostscript) down toward 5 MB before being stored.
"""
import io
import logging
import os
import shutil
import subprocess
import tempfile

logger = logging.getLogger(__name__)

# Accepted extension (lowercase, leading dot) -> human label.
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
DOC_EXTS = {'.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
            '.txt', '.md', '.csv', '.zip'}

MAX_IMAGE_BYTES = 2 * 1024 * 1024      # 2 MB
MAX_DOC_BYTES = 10 * 1024 * 1024       # 10 MB (all notes document types)
MAX_NOTES_PDF_TARGET_BYTES = 5 * 1024 * 1024  # 5 MB (soft target for PDFs)

_GS_SETTINGS = ('/ebook', '/screen')   # try highest quality first


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
        raise ValueError('File is too large (max 10 MB).')


def compress_pdf(upload, target=MAX_NOTES_PDF_TARGET_BYTES):
    """Best-effort PDF compression via Ghostscript.

    Runs gs with increasingly aggressive PDFSETTINGS until the output is at
    or below `target` bytes (or the smallest setting is used). Returns a new
    upload object with the original filename, ready to save into the FileField.

    Falls back to the unmodified upload when Ghostscript is not installed or
    processing fails, so uploads always succeed regardless of tooling.
    """
    if not shutil.which('gs'):
        logger.warning('Ghostscript not available; storing PDF uncompressed.')
        return upload
    try:
        with tempfile.TemporaryDirectory() as tmp:
            inp = os.path.join(tmp, 'in.pdf')
            out = os.path.join(tmp, 'out.pdf')
            with open(inp, 'wb') as fh:
                fh.write(upload.read())
            upload.seek(0)
            for setting in _GS_SETTINGS:
                cmd = [
                    'gs', '-q', '-dBATCH', '-dNOPAUSE', '-dSAFER',
                    '-sDEVICE=pdfwrite',
                    f'-dPDFSETTINGS={setting}',
                    '-sOutputFile=' + out, inp,
                ]
                try:
                    result = subprocess.run(
                        cmd, capture_output=True, timeout=120)
                except subprocess.TimeoutExpired:
                    logger.warning('Ghostscript timed out; storing original.')
                    return upload
                if result.returncode != 0:
                    logger.warning('Ghostscript failed (%s); storing original.',
                                   setting)
                    return upload
                with open(out, 'rb') as fh:
                    data = fh.read()
                if len(data) <= target:
                    break
            else:
                logger.warning('Best-effort compression: %s remains > target.',
                               upload.name)
        from django.core.files.uploadedfile import InMemoryUploadedFile
        return InMemoryUploadedFile(
            io.BytesIO(data), 'notes', upload.name, 'application/pdf',
            len(data), charset=None)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning('PDF compression failed: %s; storing original.', exc)
        return upload


def process_notes_upload(upload):
    """Validate a notes upload (max 10 MB), compress PDFs, return to store."""
    validate_doc_upload(upload)
    if _ext(upload.name) == '.pdf':
        upload = compress_pdf(upload)
    return upload
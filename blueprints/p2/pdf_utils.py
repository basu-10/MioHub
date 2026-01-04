from __future__ import annotations

"""Utility helpers for PDF storage and compression on disk.

This mirrors the image storage pattern: PDFs are hashed, deduplicated per-user,
compressed with PyPDF2, and written under ``static/uploads/pdfs``. Downstream
callers receive the stored filename plus metadata for quota accounting.
"""

from pathlib import Path
import os
import shutil
from typing import Optional, Tuple

from PyPDF2 import PdfReader, PdfWriter

from utilities_main import calculate_file_hash
from values_main import PDF_UPLOAD_FOLDER

PdfSaveResult = Tuple[str, int, int, Optional[int], str]
# (stored_filename, bytes_added, stored_size, page_count, file_hash)


def ensure_pdf_folder() -> Path:
    """Ensure the PDF upload folder exists and return its Path."""
    folder = Path(PDF_UPLOAD_FOLDER)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _compress_pdf(src_path: Path, dest_path: Path) -> int:
    """Write a compressed copy of the PDF and return page count.

    PyPDF2 offers gentle compression by rewriting streams; this preserves
    structure while trimming some overhead. Falls back to copy when a page
    cannot be processed.
    """
    reader = PdfReader(str(src_path))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    # Preserve metadata when available
    if reader.metadata:
        writer.add_metadata(reader.metadata)

    with dest_path.open('wb') as fp:
        writer.write(fp)

    return len(reader.pages)


def save_pdf_for_user(src_path: str | Path, user_id: int, original_filename: str | None = None) -> PdfSaveResult:
    """Compress, hash, and persist a PDF for the user.

    Returns a tuple: ``(stored_filename, bytes_added, stored_size, page_count, file_hash)``.
    ``bytes_added`` is zero when an identical hash already exists for the user.
    """
    folder = ensure_pdf_folder()
    src = Path(src_path)
    original_size = src.stat().st_size if src.exists() else 0

    file_hash = calculate_file_hash(str(src))
    stored_filename = f"{user_id}_{file_hash}.pdf"
    dest_path = folder / stored_filename

    # Deduplication: reuse existing file by hash
    if dest_path.exists():
        stored_size = dest_path.stat().st_size
        page_count = None
        try:
            page_count = len(PdfReader(str(dest_path)).pages)
        except Exception:
            page_count = None
        return stored_filename, 0, stored_size, page_count, file_hash

    page_count: Optional[int] = None
    try:
        page_count = _compress_pdf(src, dest_path)
    except Exception:
        # Fallback to raw copy if compression fails
        shutil.copy2(src, dest_path)
        try:
            page_count = len(PdfReader(str(dest_path)).pages)
        except Exception:
            page_count = None

    stored_size = dest_path.stat().st_size if dest_path.exists() else 0
    bytes_added = max(stored_size, 0)

    return stored_filename, bytes_added, stored_size, page_count, file_hash

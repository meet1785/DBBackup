"""Compression utilities for backup files."""

import gzip
import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger("db_backup")


def compress_file(file_path: str) -> str:
    """Compress a file using gzip.

    Args:
        file_path: Path to the file to compress.

    Returns:
        Path to the compressed .gz file.
    """
    gz_path = file_path + ".gz"
    logger.info("Compressing %s ...", os.path.basename(file_path))

    with open(file_path, "rb") as f_in, gzip.open(gz_path, "wb", compresslevel=6) as f_out:
        shutil.copyfileobj(f_in, f_out)

    original_size = os.path.getsize(file_path)
    compressed_size = os.path.getsize(gz_path)
    ratio = (1 - compressed_size / original_size) * 100 if original_size else 0
    logger.info(
        "Compression complete: %s -> %s (%.1f%% reduction)",
        _human_size(original_size),
        _human_size(compressed_size),
        ratio,
    )

    # Remove the uncompressed original
    os.remove(file_path)
    return gz_path


def decompress_file(gz_path: str, dest_path: str | None = None) -> str:
    """Decompress a gzip file.

    Args:
        gz_path: Path to the .gz file.
        dest_path: Optional destination path. Defaults to stripping .gz suffix.

    Returns:
        Path to the decompressed file.
    """
    if dest_path is None:
        if gz_path.endswith(".gz"):
            dest_path = gz_path[:-3]
        else:
            dest_path = gz_path + ".decompressed"

    logger.info("Decompressing %s ...", os.path.basename(gz_path))
    with gzip.open(gz_path, "rb") as f_in, open(dest_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

    logger.info("Decompressed to %s", dest_path)
    return dest_path


def _human_size(size_bytes: int) -> str:
    """Return a human-readable file size string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"

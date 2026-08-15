"""Minimal multipart/form-data parser for file uploads."""

from __future__ import annotations

import email
from pathlib import Path
from typing import List


def parse_multipart(raw: bytes, content_type: str, dest_dir: Path) -> List[Path]:
    """Parse a multipart body already read into memory. Returns saved file paths."""
    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n"
    msg = email.message_from_bytes(header.encode("ascii") + raw)
    saved: List[Path] = []
    dest_dir.mkdir(parents=True, exist_ok=True)
    for part in msg.walk():
        name = part.get_filename()
        if not name:
            continue
        safe = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        path = dest_dir / safe
        payload = part.get_payload(decode=True) or b""
        path.write_bytes(payload)
        saved.append(path)
    return saved
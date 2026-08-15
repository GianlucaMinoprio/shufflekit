"""Find a mounted iPod shuffle (3rd/4th gen) on this computer."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class ShuffleDevice:
    root: Path
    volume_name: str
    serial: str
    total_bytes: int
    free_bytes: int

    @property
    def control(self) -> Path:
        return self.root / "iPod_Control"

    @property
    def music_dir(self) -> Path:
        return self.control / "Music"

    @property
    def itunes_dir(self) -> Path:
        return self.control / "iTunes"

    @property
    def itunes_sd(self) -> Path:
        return self.itunes_dir / "iTunesSD"

    @property
    def speakable_tracks(self) -> Path:
        return self.control / "Speakable" / "Tracks"


def _volume_roots() -> List[Path]:
    roots: List[Path] = []
    for base in ("/Volumes", "/media", "/run/media", "/mnt"):
        p = Path(base)
        if not p.is_dir():
            continue
        try:
            for child in p.iterdir():
                if child.is_dir():
                    roots.append(child)
                    try:
                        for nested in child.iterdir():
                            if nested.is_dir():
                                roots.append(nested)
                    except OSError:
                        pass
        except OSError:
            continue
    # Windows drive letters
    if os.name == "nt":
        import string

        for letter in string.ascii_uppercase:
            d = Path(f"{letter}:/")
            if d.exists():
                roots.append(d)
    return roots


def find_shuffles() -> List[ShuffleDevice]:
    found: List[ShuffleDevice] = []
    seen = set()
    for root in _volume_roots():
        try:
            resolved = root.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        control = root / "iPod_Control"
        sd = control / "iTunes" / "iTunesSD"
        if not sd.is_file():
            continue
        seen.add(resolved)
        try:
            st = os.statvfs(root)
            total = st.f_frsize * st.f_blocks
            free = st.f_frsize * st.f_bavail
        except (OSError, AttributeError):
            total = free = 0
        serial = _usb_serial_guess()
        found.append(
            ShuffleDevice(
                root=root,
                volume_name=root.name,
                serial=serial,
                total_bytes=total,
                free_bytes=free,
            )
        )
    return found


def _usb_serial_guess() -> str:
    """Best-effort USB serial. Empty if we cannot read IOKit."""
    try:
        import subprocess
        import re

        out = subprocess.run(
            ["ioreg", "-p", "IOUSB", "-l", "-w", "0"],
            capture_output=True,
            text=True,
            timeout=8,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    # Prefer the 3rd-gen product id 0x1302 (4866) / 4th-gen 0x1303.
    block = ""
    chunks = out.split("+-o ")
    for chunk in chunks:
        if 'kUSBProductString" = "iPod"' not in chunk and "USB Product Name" not in chunk:
            if '"iPod"' not in chunk[:80] and not chunk.startswith("iPod@"):
                continue
        if "1302" in chunk or "1303" in chunk or "idProduct\" = 4866" in chunk or "idProduct\" = 4867" in chunk:
            block = chunk
            break
        if chunk.startswith("iPod@"):
            block = chunk
    if not block:
        return ""
    m = re.search(r'"USB Serial Number" = "([^"]+)"', block)
    return m.group(1) if m else ""

"""Copy tracks onto a shuffle and rebuild iTunesSD + VoiceOver."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Iterable, List, Optional

from .detect import ShuffleDevice, find_shuffles
from .itunes_sd import (
    TYPE_AAC,
    Track,
    file_type_for,
    guess_duration_ms,
    parse_itunes_sd,
    write_itunes_sd,
)
from .voiceover import write_track_voiceover


HASH_DIRS = ("F00", "F01", "F02", "F03", "F04")


class ShuffleLibrary:
    def __init__(self, device: ShuffleDevice):
        self.device = device
        self.device.music_dir.mkdir(parents=True, exist_ok=True)
        self.device.itunes_dir.mkdir(parents=True, exist_ok=True)
        self.device.speakable_tracks.mkdir(parents=True, exist_ok=True)

    @classmethod
    def open_default(cls) -> "ShuffleLibrary":
        found = find_shuffles()
        if not found:
            raise FileNotFoundError("no iPod shuffle mounted (looking for iPod_Control/iTunes/iTunesSD)")
        return cls(found[0])

    def tracks(self) -> List[Track]:
        p = self.device.itunes_sd
        if not p.is_file():
            return []
        return parse_itunes_sd(p.read_bytes())

    def list_rows(self) -> List[dict]:
        rows = []
        for i, tr in enumerate(self.tracks(), 1):
            full = self.device.root / tr.relpath.lstrip("/")
            rows.append(
                {
                    "n": i,
                    "path": tr.relpath,
                    "name": Path(tr.relpath).name,
                    "duration_ms": tr.duration_ms,
                    "type": tr.file_type,
                    "exists": full.is_file(),
                    "bytes": full.stat().st_size if full.is_file() else 0,
                    "voiceover": tr.voiceover_name,
                }
            )
        return rows

    def backup_db(self, dest: Optional[Path] = None) -> Path:
        dest = dest or (self.device.itunes_dir / "iTunesSD.bak")
        if self.device.itunes_sd.is_file():
            shutil.copy2(self.device.itunes_sd, dest)
        return dest

    def add_files(self, paths: Iterable[Path], voiceover: bool = True) -> List[Track]:
        current = self.tracks()
        added: List[Track] = []
        for src in paths:
            src = Path(src)
            if not src.is_file():
                raise FileNotFoundError(src)
            dest = self._hashed_dest(src)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            rel = "/" + str(dest.relative_to(self.device.root)).replace("\\", "/")
            tr = Track(
                path=rel,
                duration_ms=guess_duration_ms(str(dest)),
                file_type=file_type_for(str(dest)),
            )
            if voiceover:
                title = src.stem
                write_track_voiceover(self.device.speakable_tracks, tr.voiceover_id, title)
            current.append(tr)
            added.append(tr)
        self._write(current)
        return added

    def replace_with_files(self, paths: Iterable[Path], voiceover: bool = True) -> List[Track]:
        """Wipe the play database and hashed music, then add these files."""
        self._clear_hashed_music()
        self._write([])
        return self.add_files(paths, voiceover=voiceover)

    def rebuild_existing(self, include_orphans: bool = False, voiceover: bool = False) -> List[Track]:
        """Rewrite iTunesSD from files already on the device.

        Default: keep the current playable set (the hashed F00/F01/… tracks
        already listed). With include_orphans=True, also pick up dumped
        files sitting next to them (the old musique/ folder case).
        """
        listed = self.tracks()
        keep: List[Track] = []
        seen = set()
        for tr in listed:
            full = self.device.root / tr.relpath.lstrip("/")
            if full.is_file():
                keep.append(tr)
                seen.add(full.resolve())
        if include_orphans:
            for audio in _iter_audio(self.device.music_dir):
                if audio.resolve() in seen:
                    continue
                rel = "/" + str(audio.relative_to(self.device.root)).replace("\\", "/")
                tr = Track(
                    path=rel,
                    duration_ms=guess_duration_ms(str(audio)),
                    file_type=file_type_for(str(audio)),
                )
                if voiceover:
                    write_track_voiceover(self.device.speakable_tracks, tr.voiceover_id, audio.stem)
                keep.append(tr)
        if voiceover:
            for tr in keep:
                wav = self.device.speakable_tracks / f"{tr.voiceover_name}.wav"
                if not wav.is_file():
                    write_track_voiceover(
                        self.device.speakable_tracks,
                        tr.voiceover_id,
                        Path(tr.path).stem,
                    )
        self._write(keep)
        return keep

    def _write(self, tracks: List[Track]) -> None:
        data = write_itunes_sd(tracks)
        tmp = self.device.itunes_sd.with_suffix(".SD.tmp")
        tmp.write_bytes(data)
        tmp.replace(self.device.itunes_sd)

    def _hashed_dest(self, src: Path) -> Path:
        # 4-letter uppercase name, like iTunes. Avoid collisions.
        stem = "".join(ch for ch in src.stem.upper() if ch.isalnum())[:4] or "TRAK"
        folder = HASH_DIRS[sum(src.stat().st_size % 5 for _ in [0]) % 5]
        # better spread: hash of name+size
        folder = HASH_DIRS[(sum(bytearray(src.name.encode("utf-8", "replace"))) + src.stat().st_size) % 5]
        dest_dir = self.device.music_dir / folder
        dest_dir.mkdir(parents=True, exist_ok=True)
        name = stem[:4]
        candidate = dest_dir / f"{name}{src.suffix.lower()}"
        n = 0
        while candidate.exists():
            n += 1
            candidate = dest_dir / f"{name[:3]}{n}{src.suffix.lower()}"
        return candidate

    def _clear_hashed_music(self) -> None:
        for folder in HASH_DIRS:
            d = self.device.music_dir / folder
            if not d.is_dir():
                continue
            for child in d.iterdir():
                if child.is_file() and not child.name.startswith("._"):
                    child.unlink()


def _iter_audio(root: Path):
    exts = {".mp3", ".m4a", ".m4b", ".aac", ".wav"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if name.startswith("._") or name.startswith("."):
                continue
            p = Path(dirpath) / name
            if p.suffix.lower() in exts:
                yield p

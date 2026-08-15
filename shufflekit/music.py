"""Read Music.app playlists. Only file-backed tracks can go on a shuffle."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


@dataclass
class PlaylistInfo:
    name: str
    tracks: int
    file_tracks: int = 0
    stream_tracks: int = 0


@dataclass
class PlaylistFile:
    path: Path
    title: str
    artist: str = ""


@dataclass
class PlaylistEntry:
    """A single track in a playlist, either file-backed or a DRM stream."""
    title: str
    artist: str
    path: Path          # valid if file-backed
    is_stream: bool     # True if Apple Music DRM (.m4p)


def music_available() -> bool:
    try:
        r = subprocess.run(
            ["osascript", "-e", 'application "Music" is running'],
            capture_output=True, text=True, timeout=8,
        )
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def list_playlists() -> List[PlaylistInfo]:
    script = """
tell application "Music"
  set out to ""
  repeat with p in user playlists
    set fileCount to 0
    set streamCount to 0
    repeat with t in tracks of p
      set loc to ""
      try
        set loc to POSIX path of (location of t)
      end try
      if loc is not "" then
        set fileCount to fileCount + 1
      else
        set streamCount to streamCount + 1
      end if
    end repeat
    set out to out & name of p & tab & (count of tracks of p) & tab & fileCount & tab & streamCount & linefeed
  end repeat
  return out
end tell
"""
    text = _osascript(script, timeout=180)
    rows: List[PlaylistInfo] = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        name, total, fc, sc = parts[0], parts[1], parts[2], parts[3]
        try:
            rows.append(PlaylistInfo(
                name=name, tracks=int(total),
                file_tracks=int(fc), stream_tracks=int(sc),
            ))
        except ValueError:
            continue
    return rows


def playlist_entries(name: str) -> List[PlaylistEntry]:
    """Return all entries from a Music.app playlist.

    File-backed tracks have a valid path. Apple Music streams have
    is_stream=True and no path.
    """
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
tell application "Music"
  set p to user playlist "{escaped}"
  set out to ""
  repeat with t in tracks of p
    set loc to ""
    try
      set loc to POSIX path of (location of t)
    end try
    set artistName to ""
    try
      set artistName to artist of t
    end try
    set out to out & name of t & tab & artistName & tab & loc & linefeed
  end repeat
  return out
end tell
'''
    text = _osascript(script, timeout=180)
    entries: List[PlaylistEntry] = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        title, artist, loc = parts[0], parts[1], parts[2]
        if loc:
            p = Path(loc)
            if p.is_file():
                entries.append(PlaylistEntry(title=title, artist=artist, path=p, is_stream=False))
                continue
        # No file location = Apple Music stream
        entries.append(PlaylistEntry(title=title, artist=artist, path=Path(""), is_stream=True))
    return entries


def _osascript(script: str, timeout: int = 60) -> str:
    r = subprocess.run(
        ["osascript"], input=script,
        capture_output=True, text=True, timeout=timeout,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "osascript failed").strip()
        raise RuntimeError(err)
    return r.stdout or ""
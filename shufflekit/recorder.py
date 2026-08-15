"""Record Apple Music DRM streams to WAV via BlackHole virtual audio.

Music.app plays the DRM track through BlackHole (a virtual audio cable).
We capture from the BlackHole device with ffmpeg, then convert to AAC
for the shuffle. This is real-time: a 3-minute song takes 3 minutes.

Requirements:
  - BlackHole 2ch installed (brew install --cask blackhole-2ch)
  - Multi-Output Device or Aggregate Device set up in Audio MIDI Setup
  - ffmpeg on PATH
"""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Optional

from .music import PlaylistEntry


def blackhole_available() -> bool:
    """Check if BlackHole 2ch is installed and listable by ffmpeg."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
            capture_output=True, text=True, timeout=10,
        )
        return "BlackHole" in (r.stderr or "")
    except (OSError, subprocess.SubprocessError):
        return False


def record_track(
    entry: PlaylistEntry,
    output_dir: Path,
    device: str = "BlackHole 2ch",
    timeout_s: int = 720,
) -> Optional[Path]:
    """Play one track in Music.app and record it from BlackHole.

    Returns the path to the recorded WAV, or None on failure.
    """
    if entry.is_stream:
        # Play the track in Music.app via AppleScript
        _play_stream_track(entry)
    else:
        _play_file_track(entry)

    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c for c in entry.title if c.isalnum() or c in " -_").strip() or "track"
    wav_path = output_dir / f"{safe_name}.wav"

    # Record from BlackHole via ffmpeg AVFoundation
    # ffmpeg -f avfoundation -i ":BlackHole 2ch" -t DURATION output.wav
    # We don't know exact duration, so we record until the track ends
    # and stop ffmpeg when playback stops.
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "avfoundation",
        "-i", f":{device}",
        "-t", str(timeout_s),
        str(wav_path),
    ]
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    # Wait for playback to finish
    _wait_for_track_end(timeout_s)

    # Stop ffmpeg
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    if wav_path.exists() and wav_path.stat().st_size > 1000:
        # Trim trailing silence / cut to actual track length
        return wav_path
    return None


def convert_to_m4a(wav_path: Path, output_dir: Path) -> Optional[Path]:
    """Convert WAV to AAC/m4a for the shuffle."""
    output_dir.mkdir(parents=True, exist_ok=True)
    m4a_path = output_dir / (wav_path.stem + ".m4a")
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(wav_path),
        "-c:a", "aac", "-b:a", "256k",
        "-vn",
        str(m4a_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode == 0 and m4a_path.exists():
        return m4a_path
    return None


def _play_stream_track(entry: PlaylistEntry) -> None:
    """Play a DRM stream track in Music.app by searching for it."""
    escaped = entry.title.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
tell application "Music"
  -- Search for the track in the library
  set foundTracks to (every track whose name is "{escaped}")
  if (count of foundTracks) > 0 then
    play item 1 of foundTracks
  end if
end tell
'''
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)


def _play_file_track(entry: PlaylistEntry) -> None:
    """Play a file-backed track in Music.app."""
    if not entry.path or not entry.path.exists():
        return
    escaped = entry.title.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
tell application "Music"
  set foundTracks to (every track whose name is "{escaped}")
  if (count of foundTracks) > 0 then
    play item 1 of foundTracks
  end if
end tell
'''
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)


def _wait_for_track_end(timeout_s: int = 720) -> None:
    """Poll Music.app until playback stops or timeout."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = subprocess.run(
            ["osascript", "-e", 'tell application "Music" to player state'],
            capture_output=True, text=True, timeout=5,
        )
        state = (r.stdout or "").strip().lower()
        if state == "stopped" or state == "paused":
            # Give it a small grace period in case it's between tracks
            time.sleep(0.5)
            r2 = subprocess.run(
                ["osascript", "-e", 'tell application "Music" to player state'],
                capture_output=True, text=True, timeout=5,
            )
            state2 = (r2.stdout or "").strip().lower()
            if state2 != "playing":
                break
        time.sleep(1)


def _stop_playback() -> None:
    subprocess.run(
        ["osascript", "-e", 'tell application "Music" to stop'],
        capture_output=True, text=True, timeout=5,
    )
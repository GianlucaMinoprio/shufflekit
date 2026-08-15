"""VoiceOver clips for 3rd-gen shuffle (no screen). 22.05 kHz mono 16-bit WAV."""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path


def write_track_voiceover(tracks_dir: Path, voiceover_id: bytes, text: str) -> Path:
    tracks_dir.mkdir(parents=True, exist_ok=True)
    name = voiceover_id[::-1].hex().upper() + ".wav"
    dest = tracks_dir / name
    dest.write_bytes(synthesize_wav(text))
    return dest


def synthesize_wav(text: str) -> bytes:
    spoken = (text or "track").strip()[:80] or "track"
    if shutil.which("say") and shutil.which("afconvert"):
        return _macos_say(spoken)
    if shutil.which("espeak") or shutil.which("espeak-ng"):
        return _espeak(spoken)
    return _silence_wav(0.4)


def _macos_say(text: str) -> bytes:
    with tempfile.TemporaryDirectory() as td:
        aiff = Path(td) / "v.aiff"
        wav = Path(td) / "v.wav"
        subprocess.run(
            ["say", "-o", str(aiff), text],
            check=True,
            timeout=30,
        )
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16@22050", "-c", "1", str(aiff), str(wav)],
            check=True,
            timeout=30,
        )
        return wav.read_bytes()


def _espeak(text: str) -> bytes:
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "v.wav"
        subprocess.run(
            [exe, "-w", str(wav), "-s", "140", text],
            check=True,
            timeout=30,
        )
        # resample if needed — leave as-is if already 22050
        return wav.read_bytes()


def _silence_wav(seconds: float) -> bytes:
    rate = 22050
    n = int(rate * seconds)
    data = b"\x00\x00" * n
    return _pcm16_wav(data, rate=rate, channels=1)


def _pcm16_wav(pcm: bytes, rate: int = 22050, channels: int = 1) -> bytes:
    byte_rate = rate * channels * 2
    block = channels * 2
    hdr = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVE"
    hdr += b"fmt " + struct.pack("<IHHIIHH", 16, 1, channels, rate, byte_rate, block, 16)
    hdr += b"data" + struct.pack("<I", len(pcm))
    return hdr + pcm

"""iPod shuffle 3rd/4th gen iTunesSD (bdhs v3) reader/writer.

Layout was taken from a live 3rd-gen 2 GB shuffle (USB 05ac:1302),
then checked against the public shuffle3db notes. We write the same
bytes Apple Music wrote in March 2026.

  bdhs header   64 bytes
  hths          20 + 4*N          track offset table
  rths * N      372 each          one file each
  hphs          24                playlist directory
  lphs          48 + 4*N          master playlist (1-based indices)
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

BDHS = b"bdhs"
HTHS = b"hths"
RTHS = b"rths"
HPHS = b"hphs"
LPHS = b"lphs"

HEADER_SIZE = 64
RTHS_SIZE = 372
PATH_OFF = 24
PATH_LEN = 256
VOX_OFF = 328
TYPE_MP3 = 1
TYPE_AAC = 2
TYPE_WAV = 4


def _u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def _pack_u32(n: int) -> bytes:
    return struct.pack("<I", n & 0xFFFFFFFF)


@dataclass
class Track:
    path: str
    duration_ms: int = 0
    file_type: int = TYPE_AAC
    voiceover_id: bytes = field(default_factory=lambda: os.urandom(8))
    playable: int = 1
    extra_a: int = 36
    extra_b: int = 0x00010006

    @property
    def voiceover_name(self) -> str:
        return self.voiceover_id[::-1].hex().upper()

    @property
    def relpath(self) -> str:
        p = self.path.replace("\\", "/")
        if not p.startswith("/"):
            p = "/" + p
        return p


def parse_itunes_sd(data: bytes) -> List[Track]:
    if len(data) < HEADER_SIZE or data[:4] != BDHS:
        raise ValueError("not an iPod shuffle iTunesSD (missing bdhs)")
    n = _u32(data, 0x0C)
    hths = HEADER_SIZE
    if data[hths : hths + 4] != HTHS:
        raise ValueError("iTunesSD missing hths table")
    tracks: List[Track] = []
    for i in range(n):
        off = _u32(data, hths + 20 + i * 4)
        rec = data[off : off + RTHS_SIZE]
        if len(rec) < RTHS_SIZE or rec[:4] != RTHS:
            raise ValueError(f"bad rths at {off}")
        raw_path = rec[PATH_OFF : PATH_OFF + PATH_LEN].split(b"\x00", 1)[0]
        path = raw_path.decode("ascii", "replace")
        duration_ms = _u32(rec, 12)
        file_type = _u32(rec, 20)
        playable = _u32(rec, 284)
        extra_a = _u32(rec, 312)
        extra_b = _u32(rec, 316)
        vox = rec[VOX_OFF : VOX_OFF + 8]
        tracks.append(
            Track(
                path=path,
                duration_ms=duration_ms,
                file_type=file_type,
                voiceover_id=bytes(vox),
                playable=playable,
                extra_a=extra_a,
                extra_b=extra_b,
            )
        )
    return tracks


def write_itunes_sd(tracks: Iterable[Track]) -> bytes:
    tracks = list(tracks)
    n = len(tracks)
    hths_size = 20 + 4 * n
    rths_start = HEADER_SIZE + hths_size
    playlist_off = rths_start + n * RTHS_SIZE

    out = bytearray()

    header = bytearray(HEADER_SIZE)
    header[0:4] = BDHS
    header[4:8] = _pack_u32(0x02000003)
    header[8:12] = _pack_u32(HEADER_SIZE)
    header[12:16] = _pack_u32(n)
    header[16:20] = _pack_u32(1)  # one master playlist
    header[28:32] = _pack_u32(256)
    header[32:36] = _pack_u32(n)
    header[36:40] = _pack_u32(HEADER_SIZE)
    header[40:44] = _pack_u32(playlist_off)
    out += header

    hths = bytearray(hths_size)
    hths[0:4] = HTHS
    hths[4:8] = _pack_u32(hths_size)
    hths[8:12] = _pack_u32(n)
    for i in range(n):
        struct.pack_into("<I", hths, 20 + i * 4, rths_start + i * RTHS_SIZE)
    out += hths

    for tr in tracks:
        rec = bytearray(RTHS_SIZE)
        rec[0:4] = RTHS
        rec[4:8] = _pack_u32(RTHS_SIZE)
        rec[12:16] = _pack_u32(max(0, int(tr.duration_ms)))
        rec[20:24] = _pack_u32(tr.file_type)
        path = tr.relpath.encode("ascii", "replace")[: PATH_LEN - 1]
        rec[PATH_OFF : PATH_OFF + len(path)] = path
        rec[284:288] = _pack_u32(tr.playable)
        rec[312:316] = _pack_u32(tr.extra_a)
        rec[316:320] = _pack_u32(tr.extra_b)
        vox = (tr.voiceover_id or b"\x00" * 8)[:8]
        rec[VOX_OFF : VOX_OFF + 8] = vox.ljust(8, b"\x00")
        out += rec

    # hphs: one playlist, points at lphs immediately after
    lphs_off = playlist_off + 24
    lphs_size = 48 + 4 * n
    hphs = bytearray(24)
    hphs[0:4] = HPHS
    hphs[4:8] = _pack_u32(24)
    hphs[8:12] = _pack_u32(1)
    hphs[12:16] = b"\xff\xff\xff\xff"
    hphs[16:18] = b"\xff\xff"
    hphs[20:24] = _pack_u32(lphs_off)
    out += hphs

    lphs = bytearray(lphs_size)
    lphs[0:4] = LPHS
    lphs[4:8] = _pack_u32(lphs_size)
    lphs[8:12] = _pack_u32(n)
    lphs[12:16] = _pack_u32(n)
    lphs[24:28] = _pack_u32(1)  # master "all songs"
    for i in range(n):
        struct.pack_into("<I", lphs, 48 + i * 4, i + 1)
    out += lphs
    return bytes(out)


def file_type_for(path: str) -> int:
    ext = os.path.splitext(path)[1].lower()
    if ext in {".m4a", ".m4b", ".aac", ".mp4"}:
        return TYPE_AAC
    if ext in {".wav", ".wave"}:
        return TYPE_WAV
    return TYPE_MP3


def guess_duration_ms(path: str) -> int:
    """Best-effort duration. Prefers afinfo, then light header parse."""
    try:
        import subprocess

        r = subprocess.run(
            ["afinfo", path],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                if "estimated duration" in line.lower():
                    sec = float(line.split(":")[-1].split()[0])
                    return int(sec * 1000)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    try:
        return _duration_from_headers(path)
    except Exception:
        # last resort: ~128 kbps
        try:
            return int(os.path.getsize(path) / 16)
        except OSError:
            return 180_000


def _duration_from_headers(path: str) -> int:
    data = open(path, "rb").read(65536)
    if data[4:8] == b"ftyp" or data[4:8] == b"ftyp":
        return _m4a_duration_ms(path)
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xfa", b"\xff\xf3", b"\xff\xf2"):
        return _mp3_duration_ms(path)
    raise ValueError("unknown audio header")


def _m4a_duration_ms(path: str) -> int:
    with open(path, "rb") as f:
        def read_box(off: int, size: int) -> Optional[int]:
            f.seek(off)
            end = off + size if size else os.path.getsize(path)
            while f.tell() + 8 <= end:
                hdr = f.read(8)
                if len(hdr) < 8:
                    return None
                box_size, typ = struct.unpack(">I4s", hdr)
                if box_size == 1:
                    more = f.read(8)
                    box_size = struct.unpack(">Q", more)[0]
                    hdr_len = 16
                elif box_size == 0:
                    box_size = end - (f.tell() - 8)
                    hdr_len = 8
                else:
                    hdr_len = 8
                if box_size < hdr_len:
                    return None
                payload = box_size - hdr_len
                here = f.tell()
                if typ in (b"moov", b"trak", b"mdia"):
                    got = read_box(here, payload)
                    if got is not None:
                        return got
                elif typ == b"mvhd":
                    ver = f.read(1)[0]
                    f.read(3)
                    if ver == 1:
                        f.read(16)
                        timescale = struct.unpack(">I", f.read(4))[0]
                        duration = struct.unpack(">Q", f.read(8))[0]
                    else:
                        f.read(8)
                        timescale = struct.unpack(">I", f.read(4))[0]
                        duration = struct.unpack(">I", f.read(4))[0]
                    if timescale:
                        return int(duration * 1000 / timescale)
                f.seek(here + payload)
            return None

        got = read_box(0, os.path.getsize(path))
        if got is None:
            raise ValueError("no mvhd")
        return got


def _mp3_duration_ms(path: str) -> int:
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(10)
        off = 0
        if head[:3] == b"ID3":
            off = 10 + (head[6] << 21 | head[7] << 14 | head[8] << 7 | head[9])
        f.seek(off)
        # Xing/VBRI if present after first frame is more work; estimate from bitrate.
        frame = f.read(4)
        if len(frame) < 4 or frame[0] != 0xFF:
            return int(size / 16)
        bitrate_idx = (frame[2] >> 4) & 0x0F
        bitrates = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
        br = bitrates[bitrate_idx] * 1000
        if br == 0:
            return int(size / 16)
        audio_bytes = max(0, size - off)
        return int(audio_bytes * 8 * 1000 / br)

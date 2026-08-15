#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shufflekit.detect import ShuffleDevice
from shufflekit.library import ShuffleLibrary
from shufflekit.itunes_sd import write_itunes_sd, Track
from shufflekit.voiceover import _silence_wav, write_track_voiceover


def _fake_device(tmp: Path) -> ShuffleDevice:
    root = tmp / "IPOD"
    (root / "iPod_Control" / "iTunes").mkdir(parents=True)
    (root / "iPod_Control" / "Music" / "F00").mkdir(parents=True)
    (root / "iPod_Control" / "Speakable" / "Tracks").mkdir(parents=True)
    sd = root / "iPod_Control" / "iTunes" / "iTunesSD"
    sd.write_bytes(write_itunes_sd([]))
    return ShuffleDevice(root=root, volume_name="IPOD", serial="TEST", total_bytes=2_000_000_000, free_bytes=1_000_000_000)


class LibraryTests(unittest.TestCase):
    def test_add_and_list(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            dev = _fake_device(tmp)
            lib = ShuffleLibrary(dev)
            src = tmp / "hello.mp3"
            src.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" + b"\x00" * 2000)
            added = lib.add_files([src], voiceover=False)
            self.assertEqual(len(added), 1)
            rows = lib.list_rows()
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]["exists"])
            self.assertTrue(rows[0]["path"].startswith("/iPod_Control/Music/"))

    def test_orphans(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            dev = _fake_device(tmp)
            dumped = dev.music_dir / "musique"
            dumped.mkdir()
            song = dumped / "lost.mp3"
            song.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" + b"\x00" * 2000)
            lib = ShuffleLibrary(dev)
            tracks = lib.rebuild_existing(include_orphans=True, voiceover=False)
            self.assertEqual(len(tracks), 1)
            self.assertIn("lost.mp3", tracks[0].path)

    def test_voiceover_name(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            vid = bytes.fromhex("8df6ffce19beef00")
            p = write_track_voiceover(d, vid, "Hello")
            self.assertEqual(p.name, "00EFBE19CEFFF68D.wav")
            self.assertGreater(p.stat().st_size, 40)
            self.assertTrue(_silence_wav(0.2).startswith(b"RIFF"))


if __name__ == "__main__":
    unittest.main()

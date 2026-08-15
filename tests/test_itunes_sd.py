#!/usr/bin/env python3
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shufflekit.itunes_sd import (
    Track,
    file_type_for,
    parse_itunes_sd,
    write_itunes_sd,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "live_itunes_sd.bin"


class LiveRoundtrip(unittest.TestCase):
    def test_fixture_exists(self):
        self.assertTrue(FIXTURE.is_file(), "copy live iTunesSD into tests/fixtures")
        self.assertGreater(FIXTURE.stat().st_size, 1000)

    def test_parse_live_30_tracks(self):
        tracks = parse_itunes_sd(FIXTURE.read_bytes())
        self.assertEqual(len(tracks), 30)
        paths = [t.path for t in tracks]
        self.assertTrue(any(p.endswith("ASOJ.m4a") for p in paths))
        self.assertTrue(all(p.startswith("/iPod_Control/Music/") for p in paths))
        self.assertTrue(all(t.file_type == 2 for t in tracks))
        self.assertGreater(tracks[0].duration_ms, 10_000)
        self.assertEqual(len(tracks[0].voiceover_id), 8)
        self.assertEqual(tracks[0].voiceover_name, "00EFBE19CEFFF68D")

    def test_write_parse_preserves_tracks(self):
        original = parse_itunes_sd(FIXTURE.read_bytes())
        rebuilt = write_itunes_sd(original)
        again = parse_itunes_sd(rebuilt)
        self.assertEqual([t.path for t in original], [t.path for t in again])
        self.assertEqual([t.duration_ms for t in original], [t.duration_ms for t in again])
        self.assertEqual([t.voiceover_name for t in original], [t.voiceover_name for t in again])
        self.assertTrue(rebuilt.startswith(b"bdhs"))
        self.assertIn(b"hths", rebuilt)
        self.assertIn(b"rths", rebuilt)
        self.assertIn(b"hphs", rebuilt)
        self.assertIn(b"lphs", rebuilt)


class Writer(unittest.TestCase):
    def test_empty(self):
        data = write_itunes_sd([])
        self.assertEqual(parse_itunes_sd(data), [])

    def test_one_mp3(self):
        tr = Track(path="/iPod_Control/Music/F00/ABCD.mp3", duration_ms=12345, file_type=1)
        data = write_itunes_sd([tr])
        got = parse_itunes_sd(data)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].path, "/iPod_Control/Music/F00/ABCD.mp3")
        self.assertEqual(got[0].duration_ms, 12345)
        self.assertEqual(got[0].file_type, 1)
        self.assertEqual(got[0].voiceover_name, tr.voiceover_name)

    def test_file_type(self):
        self.assertEqual(file_type_for("a.m4a"), 2)
        self.assertEqual(file_type_for("a.mp3"), 1)
        self.assertEqual(file_type_for("a.wav"), 4)


if __name__ == "__main__":
    unittest.main()

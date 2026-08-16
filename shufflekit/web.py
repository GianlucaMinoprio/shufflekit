"""Local web UI for detecting a shuffle and flashing music."""

from __future__ import annotations

import json
import posixpath
import shutil
import tempfile
import threading
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import __version__
from .detect import find_shuffles
from .library import ShuffleLibrary

STATIC = Path(__file__).resolve().parent / "static"

# Global progress for recording
_record_progress = {"active": False, "done": 0, "total": 0, "status": ""}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def log_message(self, fmt, *args):
        import sys
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            return self._json(self._status())
        if parsed.path == "/api/tracks":
            return self._json(self._tracks())
        if parsed.path == "/api/playlists":
            return self._json(self._playlists())
        if parsed.path == "/api/record-progress":
            return self._json(dict(_record_progress))
        if parsed.path == "/api/blackhole-status":
            from .recorder import blackhole_available
            return self._json({"ok": True, "installed": blackhole_available()})
        if parsed.path == "/api/blackhole-setup":
            from .recorder import setup_blackhole_multi_output
            return self._json({"ok": True, **setup_blackhole_multi_output()})
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            if parsed.path == "/api/rebuild":
                body = json.loads(raw.decode("utf-8") or "{}")
                return self._json(self._rebuild(body))
            if parsed.path == "/api/add":
                return self._json(self._add_multipart(raw, self.headers.get("Content-Type", "")))
            if parsed.path == "/api/record-playlist":
                body = json.loads(raw.decode("utf-8") or "{}")
                return self._json(self._record_playlist(body))
            if parsed.path == "/api/blackhole-install":
                from .recorder import install_blackhole
                return self._json({"ok": True, **install_blackhole()})
        except Exception as exc:
            return self._json({"ok": False, "error": str(exc), "trace": traceback.format_exc()}, 400)
        self.send_error(404)

    def _status(self):
        found = find_shuffles()
        if not found:
            return {"ok": True, "connected": False, "version": __version__}
        d = found[0]
        lib = ShuffleLibrary(d)
        return {
            "ok": True,
            "connected": True,
            "version": __version__,
            "root": str(d.root),
            "volume": d.volume_name,
            "serial": d.serial,
            "total_bytes": d.total_bytes,
            "free_bytes": d.free_bytes,
            "tracks": len(lib.tracks()),
        }

    def _tracks(self):
        found = find_shuffles()
        if not found:
            return {"ok": True, "tracks": []}
        return {"ok": True, "tracks": ShuffleLibrary(found[0]).list_rows()}

    def _playlists(self):
        from .music import list_playlists, music_available
        if not music_available():
            return {"ok": True, "playlists": [], "error": "Music.app is not running"}
        try:
            pls = list_playlists()
            return {
                "ok": True,
                "playlists": [
                    {"name": p.name, "tracks": p.tracks,
                     "file_tracks": p.file_tracks, "stream_tracks": p.stream_tracks}
                    for p in pls
                ],
            }
        except Exception as exc:
            return {"ok": True, "playlists": [], "error": str(exc)}

    def _rebuild(self, body):
        lib = ShuffleLibrary.open_default()
        lib.backup_db()
        tracks = lib.rebuild_existing(
            include_orphans=bool(body.get("orphans")),
            voiceover=bool(body.get("voiceover")),
        )
        return {"ok": True, "tracks": len(tracks)}

    def _add_multipart(self, raw: bytes, content_type: str):
        from ._multipart import parse_multipart
        tmp = Path(tempfile.mkdtemp(prefix="shufflekit-"))
        files = parse_multipart(raw, content_type, tmp)
        if not files:
            return {"ok": False, "error": "no files in upload"}
        lib = ShuffleLibrary.open_default()
        lib.backup_db()
        added = lib.add_files(files, voiceover=True)
        shutil.rmtree(tmp, ignore_errors=True)
        return {"ok": True, "added": len(added), "tracks": len(lib.tracks())}

    def _record_playlist(self, body):
        name = body.get("playlist", "")
        if not name:
            return {"ok": False, "error": "no playlist name"}
        # Start recording in background thread
        _record_progress.update(active=True, done=0, total=0, status="starting")
        t = threading.Thread(target=_do_record, args=(name,), daemon=True)
        t.start()
        return {"ok": True, "status": "recording started", "playlist": name}

    def _json(self, obj, status=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def _do_record(playlist_name: str):
    """Background thread: record playlist tracks and add to shuffle."""
    from .music import playlist_entries
    from .recorder import record_track, convert_to_m4a, blackhole_available, _stop_playback

    try:
        entries = playlist_entries(playlist_name)
        _record_progress.update(total=len(entries), done=0, status="recording")

        if not blackhole_available():
            _record_progress.update(
                status="error: BlackHole not installed. Run: brew install --cask blackhole-2ch and reboot.")
            return

        lib = ShuffleLibrary.open_default()
        lib.backup_db()

        added = 0
        for i, entry in enumerate(entries):
            _record_progress.update(
                status=f"recording {i+1}/{len(entries)}: {entry.title}")

            if not entry.is_stream:
                # File-backed: copy directly
                lib.add_files([entry.path], voiceover=True)
                added += 1
            else:
                # DRM stream: record via BlackHole
                tmp_dir = Path(tempfile.mkdtemp(prefix="shufflekit-rec-"))
                wav = record_track(entry, tmp_dir)
                if wav:
                    m4a = convert_to_m4a(wav, tmp_dir)
                    if m4a:
                        lib.add_files([m4a], voiceover=True)
                        added += 1
                shutil.rmtree(tmp_dir, ignore_errors=True)

            _record_progress.update(done=i + 1)

        _stop_playback()
        _record_progress.update(
            active=False,
            status=f"done: {added} tracks added, {len(lib.tracks())} total playable",
        )
    except Exception as exc:
        _stop_playback()
        _record_progress.update(active=False, status=f"error: {exc}")


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"shufflekit {__version__}  {url}")
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
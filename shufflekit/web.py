"""Local web UI for detecting a shuffle and flashing music."""

from __future__ import annotations

import json
import posixpath
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import __version__
from .detect import find_shuffles
from .library import ShuffleLibrary

STATIC = Path(__file__).resolve().parent / "static"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def log_message(self, fmt, *args):
        sys_stdout = __import__("sys").stderr
        sys_stdout.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            return self._json(self._status())
        if parsed.path == "/api/tracks":
            return self._json(self._tracks())
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
                return self._json(self._add_multipart())
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

    def _rebuild(self, body):
        lib = ShuffleLibrary.open_default()
        lib.backup_db()
        tracks = lib.rebuild_existing(
            include_orphans=bool(body.get("orphans")),
            voiceover=bool(body.get("voiceover")),
        )
        return {"ok": True, "tracks": len(tracks)}

    def _add_multipart(self):
        # Browser sends files as multipart. We stash them in a temp dir then add.
        import email
        import tempfile

        ctype = self.headers.get("Content-Type", "")
        length = int(self.headers.get("Content-Length") or 0)
        # We already consumed the body in do_POST. Reconstruct a message.
        # Re-read is not possible. do_POST should pass raw. Use a different path.
        raise RuntimeError("use /api/add-files via the JS FormData helper")

    def _json(self, obj, status=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def _save_uploads(raw: bytes, content_type: str, dest_dir: Path):
    """Parse a multipart body already read into memory."""
    import email

    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n"
    msg = email.message_from_bytes(header.encode("ascii") + raw)
    saved = []
    dest_dir.mkdir(parents=True, exist_ok=True)
    for part in msg.walk():
        name = part.get_filename()
        if not name:
            continue
        safe = posixpath.basename(name)
        path = dest_dir / safe
        payload = part.get_payload(decode=True) or b""
        path.write_bytes(payload)
        saved.append(path)
    return saved


class UploadHandler(Handler):
    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            if parsed.path == "/api/rebuild":
                body = json.loads(raw.decode("utf-8") or "{}")
                return self._json(self._rebuild(body))
            if parsed.path == "/api/add":
                import tempfile
                from pathlib import Path as P

                tmp = P(tempfile.mkdtemp(prefix="shufflekit-"))
                files = _save_uploads(raw, self.headers.get("Content-Type", ""), tmp)
                if not files:
                    return self._json({"ok": False, "error": "no files in upload"}, 400)
                lib = ShuffleLibrary.open_default()
                lib.backup_db()
                added = lib.add_files(files, voiceover=True)
                return self._json({"ok": True, "added": len(added), "tracks": len(lib.tracks())})
        except Exception as exc:
            return self._json({"ok": False, "error": str(exc), "trace": traceback.format_exc()}, 400)
        self.send_error(404)


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = ThreadingHTTPServer((host, port), UploadHandler)
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

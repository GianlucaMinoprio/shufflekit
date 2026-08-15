"""CLI: shufflekit detect | list | add | rebuild | serve."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .detect import find_shuffles
from .library import ShuffleLibrary


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="shufflekit",
        description="Flash music onto an iPod shuffle 3rd/4th gen without iTunes.",
    )
    p.add_argument("--version", action="version", version=f"shufflekit {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("detect", help="find a mounted shuffle")
    sub.add_parser("list", help="list playable tracks")

    add = sub.add_parser("add", help="copy files onto the shuffle and rebuild the play database")
    add.add_argument("files", nargs="+", type=Path)
    add.add_argument("--no-voiceover", action="store_true")

    reb = sub.add_parser("rebuild", help="rewrite iTunesSD from files already on the device")
    reb.add_argument("--orphans", action="store_true", help="also include dumped folders like musique/")
    reb.add_argument("--voiceover", action="store_true")

    srv = sub.add_parser("serve", help="open the local web UI")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8765)

    args = p.parse_args(argv)
    if args.cmd == "detect":
        return _detect()
    if args.cmd == "list":
        return _list()
    if args.cmd == "add":
        lib = ShuffleLibrary.open_default()
        lib.backup_db()
        added = lib.add_files(args.files, voiceover=not args.no_voiceover)
        print(f"added {len(added)} · playable {len(lib.tracks())}")
        return 0
    if args.cmd == "rebuild":
        lib = ShuffleLibrary.open_default()
        lib.backup_db()
        tracks = lib.rebuild_existing(include_orphans=args.orphans, voiceover=args.voiceover)
        print(f"playable {len(tracks)}")
        return 0
    if args.cmd == "serve":
        from .web import serve

        serve(args.host, args.port)
        return 0
    return 2


def _detect() -> int:
    found = find_shuffles()
    if not found:
        print("no shuffle mounted")
        return 1
    for d in found:
        print(
            json.dumps(
                {
                    "root": str(d.root),
                    "volume": d.volume_name,
                    "serial": d.serial,
                    "total_bytes": d.total_bytes,
                    "free_bytes": d.free_bytes,
                }
            )
        )
    return 0


def _list() -> int:
    lib = ShuffleLibrary.open_default()
    rows = lib.list_rows()
    print(f"{len(rows)} playable tracks on {lib.device.root}")
    for row in rows:
        miss = "" if row["exists"] else " MISSING"
        sec = row["duration_ms"] / 1000
        print(f"{row['n']:3d}  {sec:6.0f}s  {row['name']}{miss}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Command-line interface for ``suuid``.

    suuid mint --class Data --name "Messung 2026.csv"
    suuid mint --class Doc --name spec.pdf --mode content --content-file spec.pdf
    suuid mint --class Run --name nightly --mode random
    suuid parse --sname "Data__messung_2026_csv__9e51..."
    suuid parse --token "<base64 compact token>"
"""

from __future__ import annotations

import argparse
import json
import sys

from suuid.core import SUUID


def _read_content(args: argparse.Namespace) -> bytes:
    if args.content_file:
        with open(args.content_file, "rb") as fh:
            return fh.read()
    if args.content_str is not None:
        return args.content_str.encode("utf-8")
    raise SystemExit("mode=content requires --content-file or --content-str")


def _mint(args: argparse.Namespace) -> SUUID:
    if args.mode == "name":
        return SUUID.from_name(args.class_name, args.name)
    if args.mode == "content":
        return SUUID.from_content(args.class_name, args.name, _read_content(args))
    if args.mode == "random":
        return SUUID.random(args.class_name, args.name)
    raise SystemExit(f"unknown mode: {args.mode!r}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="suuid", description="Semantic, filename-safe UUIDs")
    sub = p.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("mint", help="mint a SUUID")
    m.add_argument("--class", dest="class_name", required=True)
    m.add_argument("--name", default="", help="human label (will be normalised)")
    m.add_argument("--mode", choices=["name", "content", "random"], default="name")
    m.add_argument("--content-file")
    m.add_argument("--content-str")
    m.add_argument("--json", action="store_true", help="print the full to_dict() as JSON")

    pa = sub.add_parser("parse", help="parse an sname or compact token back")
    pa.add_argument("--sname")
    pa.add_argument("--token")

    args = p.parse_args(argv)

    if args.cmd == "mint":
        sid = _mint(args)
        print(json.dumps(sid.to_dict(), indent=2) if args.json else sid.sname)
        return 0

    if args.cmd == "parse":
        if args.sname:
            sid = SUUID.from_sname(args.sname)
        elif args.token:
            sid = SUUID.from_compact_token(args.token)
        else:
            raise SystemExit("parse requires --sname or --token")
        print(json.dumps(sid.to_dict(), indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())

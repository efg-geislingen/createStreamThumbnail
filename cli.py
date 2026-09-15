#!/usr/bin/env python3
"""Thin CLI wrapper around GIMP's own batch interface.

Parses arguments and shells out to `gimp-console` to invoke the
`python-fu-stream-thumbnail-batch` PDB procedure (registered in
createStreamThumbnail.py). Contains no selection/title/export logic of its
own — that all lives in core/ and runs inside GIMP, exactly as it does for
the GUI. See AGENT/plans/refactoring.md §5.

This script does not need `gi`/GIMP itself and runs under a plain system
Python.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

DEFAULT_GIMP_CONSOLE = r"C:\Program Files\GIMP 3\bin\gimp-console-3.2.exe"
BATCH_PROCEDURE = "python-fu-stream-thumbnail-batch"


def _scheme_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_batch_command(args: argparse.Namespace) -> str:
    # Named (#:key value) arguments, not positional — Script-Fu warns that
    # calling plug-in PDB procedures with an ordered list is deprecated.
    call_args = [
        f"#:template {_scheme_string(args.template)}",
        f"#:title {_scheme_string(args.title)}",
        f"#:title-json {_scheme_string(args.title_json)}",
        f"#:theme {_scheme_string(args.theme)}",
        f"#:name {_scheme_string(args.name)}",
        f"#:date {_scheme_string(args.date)}",
        f"#:output {_scheme_string(args.output)}",
    ]
    return f"({BATCH_PROCEDURE} {' '.join(call_args)})"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a stream thumbnail without opening the GIMP GUI."
    )
    parser.add_argument("--template", required=True, help="Path to the .xcf template")
    parser.add_argument("--title", default="", help=r"Plain title text; use \n for line breaks")
    parser.add_argument(
        "--title-json", default="",
        help="Structured rich-text title: inline JSON or a path to a .json file (overrides --title)",
    )
    parser.add_argument("--theme", required=True, help="Requested Predigt-Reihe")
    parser.add_argument("--name", required=True, help="Requested Prediger")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD, used for the export filename")
    parser.add_argument(
        "--output", default="",
        help="Optional: full file path or directory, overriding the default output/ "
             "subfolder next to the template",
    )
    parser.add_argument(
        "--gimp-console", default=DEFAULT_GIMP_CONSOLE,
        help=f"Path to gimp-console(.exe) (default: {DEFAULT_GIMP_CONSOLE})",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print the batch command before running it"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    command = [
        args.gimp_console, "-i",
        "--batch-interpreter=plug-in-script-fu-eval",
        "-b", build_batch_command(args),
        "-b", "(gimp-quit 0)",
    ]

    if args.verbose:
        print("Running:", subprocess.list2cmdline(command))

    result = subprocess.run(command)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())

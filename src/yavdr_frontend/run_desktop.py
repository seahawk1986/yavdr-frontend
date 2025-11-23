#!/usr/bin/python3
# Based on a script by Eduardo Leggiero - https://www.leggiero.uk
# https://www.leggiero.uk/post/running-desktop-files-from-command-line/

import logging
import sys
from argparse import ArgumentParser
from pathlib import Path

from yavdr_frontend.tools import get_DesktopAppInfo


HOME = Path.home()
log = logging.getLogger("run_desktop")


def run_desktop(desktop_entry: str, uris: list[str]) -> bool:
    app = get_DesktopAppInfo(desktop_entry=desktop_entry)
    if app.launch_uris(uris=uris):
        return True
    else:
        raise ValueError(f"could not start {app.get_name} with {uris=}")


def main():
    parser = ArgumentParser(description="start .desktop files programmatically")
    parser.add_argument(
        "desktop_file", type=str, help="name of full path of a .desktop file"
    )
    parser.add_argument(
        "uris",
        type=list,
        nargs="*",
        help="optional paths/URIs passed to the .desktop file",
    )
    args = parser.parse_args()
    logging.debug(f"run_desktop({args.desktop_file}, {args.uris}")
    try:
        result = run_desktop(args.desktop_file, args.uris)
        if not result:
            sys.exit(f"could not start {args.desktop_file}")
    except ValueError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()

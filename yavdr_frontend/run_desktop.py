#!/usr/bin/python3
# Based on a script by Eduardo Leggiero - https://www.leggiero.uk
# https://www.leggiero.uk/post/running-desktop-files-from-command-line/

import logging
import os
import sys
from argparse import ArgumentParser
from pathlib import Path

from gi.repository import Gio  # pyright: ignore[reportMissingModuleSource]


HOME = Path.home()


def run_desktop(desktop_file: str, uris: list[str]):
    log = logging.getLogger("run_desktop")

    desktop_file = (
        f"{desktop_file}.desktop"
        if not desktop_file.endswith(".desktop")
        else desktop_file
    )

    xdg_dirs: list[Path] = []
    if xdg_data_home := os.getenv("XDG_DATA_HOME"):
        xdg_dirs.append(Path(xdg_data_home) / "applications")
    else:
        xdg_dirs.append(HOME / ".local/share/applications")
    xdg_dirs.extend(
        Path(p) / "applications" for p in os.getenv("XDG_DATA_DIRS", "").split(":") if p
    )

    for path in xdg_dirs:
        d_path = path / desktop_file
        if d_path.is_file():
            try:
                if launcher := Gio.DesktopAppInfo.new_from_filename(f"{d_path}"):
                    launcher.launch_uris(uris, None)
            except Exception as e:
                log.exception(e)
            else:
                sys.exit()
        else:
            log.debug(f"No starter found for {desktop_file} at {d_path}")
    sys.exit(1)

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
    run_desktop(args.desktop_file, args.uris)


if __name__ == "__main__":
    main()

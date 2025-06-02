#!/usr/bin/python3
# Based on a script by Eduardo Leggiero - https://www.leggiero.uk
# https://www.leggiero.uk/post/running-desktop-files-from-command-line/

import logging
from gi.repository import Gio
import sys
import os


def run_desktop(desktop_file: str, *uris: str):
    log = logging.getLogger("run_desktop")
    if not desktop_file.endswith(".desktop"):
        desktop_file = desktop_file + ".desktop"

    xdg_dirs = []
    if xdg_data_home := os.getenv("XDG_DATA_HOME"):
        xdg_dirs.append(os.path.join(xdg_data_home, "applications"))
    elif home := os.getenv("HOME"):
        xdg_dirs.append(os.path.join(home, ".local/share/applications"))
    xdg_dirs.extend(
        os.path.join(p, "applications") for p in os.getenv("XDG_DATA_DIRS").split(":")
    )

    for path in xdg_dirs:
        d_path = os.path.join(path, desktop_file)
        if os.path.isfile(d_path):
            try:
                launcher = Gio.DesktopAppInfo.new_from_filename(d_path)
                launcher.launch_uris(*uris, None)
            except Exception as e:
                log.exception(e)
            else:
                sys.exit()
        else:
            log.debug(f"No starter found for {desktop_file} at {d_path}")
    sys.exit(1)


if __name__ == "__main__":
    run_desktop(*sys.argv[1:])

#!/usr/bin/env python3
import asyncio
import sdbus

from yavdr_frontend.args import StartArgumentParser
from yavdr_frontend.config import load_yaml
from yavdr_frontend.tools import get_bus
from yavdr_frontend.interfaces.yavdr_frontend_interface import (
    yaVDRFrontendInterface,
    YAVDR_FRONTEND_BUS_NAME,
)

# TODO: find better filename

# This scripts forwards the absolute path, desktop_id or name of a .desktop file
# to the DBus interface of yavdr-frontend.
#
# The desktop_id is an escaped version of the subfolder and filename in
# the user directory, the XDG_DATA_DIRS etc.
# Slashes of the paths in the subfolders are replaced by dashes - e.g. `/usr/share/applications/foo/bar.desktop` has the id `foo-bar.desktop`


async def start_desktop(desktop_entry: str, args: list[str], bus: sdbus.SdBus) -> None:
    fe = yaVDRFrontendInterface.new_proxy(
        YAVDR_FRONTEND_BUS_NAME, "/Controller", bus=bus
    )
    await fe.switchto(desktop_entry)


def main():
    StartArgumentParser.description = "start .desktop files programmatically"
    StartArgumentParser.add_argument(
        "desktop_file",
        type=str,
        help="full path, desktop_id or name of a .desktop file",
    )
    StartArgumentParser.add_argument(
        "uris", type=list, nargs="*", help="files/URIs passed to the .desktop file"
    )
    args = StartArgumentParser.parse_args()
    config = load_yaml(args.config)
    asyncio.run(
        start_desktop(
            args.desktop_file, args.uris, bus=get_bus(config.main.interface_bus)
        )
    )


if __name__ == "__main__":
    main()

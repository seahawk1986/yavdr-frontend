#!/usr/bin/env python3
from argparse import ArgumentParser
import asyncio
import os.path
from .tools import strtobool
from yavdr_frontend.interfaces.yavdr_frontend_interface import (
    yaVDRFrontendInterface,
    YAVDR_FRONTEND_BUS_NAME,
)

# TODO: find better filename, add a description what this does

import sdbus


def get_bus(args: list[str] | None):
    if args:
        try:
            sessionbus = strtobool(args[0])
        except Exception as e:
            print(e)
        else:
            if sessionbus:
                print("use SessionBus")
                return sdbus.sd_bus_open_user()
    return sdbus.sd_bus_open_system()


async def start_desktop(path: str, args: list[str]):
    bus = get_bus(args)
    fe = yaVDRFrontendInterface.new_proxy(
        YAVDR_FRONTEND_BUS_NAME, "/Controller", bus=bus
    )
    path = os.path.splitext(os.path.basename(path))[0]
    await fe.switchto(path)


def main():
    parser = ArgumentParser(description="start .desktop files programmatically")
    parser.add_argument(
        "desktop_file", type=str, help="name of full path of a .desktop file"
    )
    parser.add_argument(
        "uris", type=list, nargs="*", help="files/URIs passed to the .desktop file"
    )
    args = parser.parse_args()
    asyncio.run(start_desktop(args.desktop_file, args.uris))


if __name__ == "__main__":
    main()

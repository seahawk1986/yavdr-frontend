#!/usr/bin/env python3
import asyncio
import os.path
import sys
from .tools import strtobool
from yavdr_frontend.interfaces.yavdr_frontend_interface import (
    yaVDRFrontendInterface,
    YAVDR_FRONTEND_INTERFACE_NAME,
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
    fe = yaVDRFrontendInterface.new_proxy(YAVDR_FRONTEND_INTERFACE_NAME, "/", bus=bus)
    path = os.path.splitext(os.path.basename(path))[0]
    await fe.switchto(path)


if __name__ == "__main__":
    path, *args = sys.argv[1:]
    asyncio.run(start_desktop(path, args))

#!/usr/bin/env python3
import os.path
import sys
from .tools import strtobool
from yavdr_frontend.yavdr_frontend import yaVDRFrontend, INTERFACE_NAME

# TODO: find better filename, add a description what this does

import sdbus


def start_desktop():
    path, *args = sys.argv[1:]
    if args:
        try:
            sessionbus = strtobool(args[0])
        except Exception as e:
            print(e)
        else:
            if sessionbus:
                bus = sdbus.sd_bus_open_user()
                print("use SessionBus")
            else:
                bus = sdbus.sd_bus_open_system()
    else:
        bus = sdbus.sd_bus_open_system()
        print("use_systembus")
    fe = yaVDRFrontend.new_proxy(INTERFACE_NAME, "/", bus=bus)
    path = os.path.splitext(os.path.basename(path))[0]
    fe.switchto(path)


if __name__ == "__main__":
    start_desktop()

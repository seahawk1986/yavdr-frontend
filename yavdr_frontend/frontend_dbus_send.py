# TODO: use argparse
# import argparse
import asyncio
import sys
from yavdr_frontend.config import load_yaml
from yavdr_frontend.tools import get_bus
from yavdr_frontend.interfaces.yavdr_frontend_interface import (
    yaVDRFrontendInterface,
    YAVDR_FRONTEND_BUS_NAME,
)

async def dbus_send():
    config = load_yaml()
    bus = get_bus(config.main.interface_bus)
    fe = yaVDRFrontendInterface.new_proxy(
        YAVDR_FRONTEND_BUS_NAME, "/Controller", bus=bus
    )
    if len(sys.argv) > 1:
        cmd = getattr(fe, sys.argv[1])
        return await cmd(*sys.argv[2:])
    else:
        print("usage: {} COMMAND [ARGS]...".format(sys.argv[0]))
        print("you can call the following methods:")
        print(await fe.dbus_introspect())

def main():
    # parser = argparse.ArgumentParser()
    # parser.add_argument('cmd')
    asyncio.run(dbus_send())


if __name__ == "__main__":
    main()
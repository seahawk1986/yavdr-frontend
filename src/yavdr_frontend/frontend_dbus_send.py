# TODO: use argparse
import argparse
import asyncio
import sys
import xml.etree.ElementTree as ET
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
    if len(sys.argv) == 1:
        # print(await fe.properties_get_all_dict())
        root = ET.fromstring(await fe.dbus_introspect())
        for child in root.findall(
            f'.//method/..[@name="{YAVDR_FRONTEND_BUS_NAME}.Controller"]'
        ):
            # print(ET.tostring(child).decode())
            for method in child.findall("./method"):
                method_args = [
                    arg.attrib["type"]
                    for arg in method.findall("./arg[@direction='in']")
                ]
                result = [
                    arg.attrib["type"]
                    for arg in method.findall("./arg[@direction='out']")
                ]
                print(
                    method.get("name"),
                    "arguments:",
                    method_args,
                    "-> response:",
                    result,
                )
        return

    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", help="command")
    parser.add_argument(
        "arguments", metavar="ARG", nargs="*", type=str, help="arguments"
    )
    args = parser.parse_args()
    cmd = getattr(fe, args.cmd)
    arguments = args.arguments
    try:
        return await cmd(*arguments)
    except Exception as e:
        exit(f"{e}")


def main():
    asyncio.run(dbus_send())


if __name__ == "__main__":
    main()

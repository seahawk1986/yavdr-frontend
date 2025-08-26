import asyncio
import logging

from yavdr_frontend.args import StartArgumentParser
from yavdr_frontend.config import load_yaml
from yavdr_frontend.controller import Controller

FORMAT = "[ %(filename)s:%(lineno)s: %(name)s.%(funcName)s() ] %(message)s"


def on_keypress(cmd: str): ...


# async def create_and_publish_controller(config: Config) -> Controller:
#     # create the the Controller, which also publishes the DBus Interface
#     async with asyncio.TaskGroup():
#         controller = await Controller(config)  # type: ignore # noqa: F841  # this unused variable is needed to keep the object alive
#         return controller

async def parse_args_and_run() -> Controller:
    args = StartArgumentParser.parse_args()
    logging.basicConfig(level=args.loglevel, format=FORMAT)
    config = load_yaml(args.config)
    return await Controller(config)  # this variable is needed to keep the object alive


def main():
    loop = asyncio.new_event_loop()
    controller = loop.run_until_complete(parse_args_and_run())
    logging.info("Startup complete. Press STRG + C to cancel ...")
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logging.info("stopping ...")
    finally:
        logging.info("stop active frontend")
        loop.run_until_complete(controller.stop())
        logging.info("stopped active frontend")


if __name__ == "__main__":
    main()

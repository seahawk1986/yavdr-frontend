import asyncio
import logging

from yavdr_frontend.args import StartArgumentParser
from yavdr_frontend.config import Config, load_yaml
from yavdr_frontend.controller import Controller

FORMAT = "[ %(filename)s:%(lineno)s: %(name)s.%(funcName)s() ] %(message)s"


def on_keypress(cmd: str): ...


async def create_and_publish_controller(config: Config):
    # create the the Controller, which also publishes the DBus Interface

    async with asyncio.TaskGroup():
        try:
            controller = await Controller(config)  # type: ignore # noqa: F841  # this unused variable is needed to keep the object alive
        finally:
            await controller.quit()

async def parse_args_and_run():
    args = StartArgumentParser.parse_args()
    logging.basicConfig(level=args.loglevel, format=FORMAT)
    config = load_yaml(args.config)
    await create_and_publish_controller(config)


def main():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(parse_args_and_run())
    logging.info("Startup complete. Press STRG + C to cancel ...")
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

import asyncio
import logging

from yavdr_frontend.args import StartArgumentParser
from yavdr_frontend.config import load_yaml
from yavdr_frontend.controller import Controller

FORMAT = "%(filename)s:%(lineno)s:%(levelname)s:%(name)s.%(funcName)s(): %(message)s"


async def parse_args_and_run() -> Controller:
    args = StartArgumentParser.parse_args()
    logging.basicConfig(level=args.loglevel, format=FORMAT)
    try:
        config = load_yaml(args.config)
    except IOError:
        exit("could not find a valid config file")
    logging.basicConfig(
        level=config.main.log_level, format=config.main.log_format, force=True
    )
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
        loop.run_until_complete(controller.quit())
        logging.info("stopped active frontend")


if __name__ == "__main__":
    main()

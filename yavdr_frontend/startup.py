import argparse
import logging

from yavdr_frontend.config import load_yaml
from yavdr_frontend.yavdr_frontend import export_frontend


async def main():
    parser = argparse.ArgumentParser(
        description="a script to manage vdr and other frontends"
    )
    parser.add_argument(
        "-l",
        "--loglevel",
        dest="loglevel",
        default="DEBUG",
        help="set the log level to [DEBUG|INFO|WARN|ERROR] (default: DEBUG)",
    )
    parser.add_argument(
        "-c",
        "--config",
        dest="config",
        default="config.yml",
        help="set path for configuration file",
    )

    args = parser.parse_args()
    log_level = getattr(logging, args.loglevel, logging.DEBUG)
    logging.basicConfig(level=log_level)
    config = load_yaml(args.config)
    try:
        await export_frontend(config)
    except KeyboardInterrupt:
        pass

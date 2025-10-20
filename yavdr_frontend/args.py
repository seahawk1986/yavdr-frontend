import argparse
from pathlib import Path

from yavdr_frontend.config import LoggingEnum

StartArgumentParser = argparse.ArgumentParser(
    description="a script to manage vdr and other frontends"
)
StartArgumentParser.add_argument(
    "-l",
    "--loglevel",
    dest="loglevel",
    default="DEBUG",
    type=lambda x: LoggingEnum[x],
    help="set the log level to [DEBUG|INFO|WARN|ERROR] (default: DEBUG)",
)
StartArgumentParser.add_argument(
    "-c",
    "--config",
    dest="config",
    default="config.yml",
    type=Path,
    help="set path for configuration file",
)

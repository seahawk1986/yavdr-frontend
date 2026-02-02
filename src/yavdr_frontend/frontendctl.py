import json
import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path
from collections.abc import Mapping
import sys
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from yavdr_frontend.config import Config


CONFIG_PATH = Path("/etc/yavdr-frontend/config.yml")


def parse_args() -> Namespace:
    parser = ArgumentParser()
    parser.add_argument("key", type=str, help="value to change")
    parser.add_argument("value", nargs="?", default=None, help="new value to set")
    parser.add_argument("--json", "-j", action="store_true", help="value to change")
    return parser.parse_args()


def load_config(config: Path, yaml):
    # Load YAML - TODO: string interpolation
    try:
        with open(config) as f:
            data = yaml.load(f)

            # Validate what’s there (missing fields become None)
            model = Config(**data)
    except Exception:
        logging.exception("invalid config file")
        exit(1)

    # pprint(data, indent=2)
    return data


def get_value(data: Mapping[str, Any], key: str):
    keys = key.split(".")
    current = data

    for key in keys:
        if key not in current:
            print(f"{current=}")
            return ""
        current = current[key]
    return current


def set_value(data: Mapping[str, Any], key: str, value: Any) -> Mapping[str, Any]:
    keys = key.split(".")
    current = data
    for key in keys[:-1]:
        if key not in current:
            current[key] = CommentedMap()
        current = current[key]

    print(f"update {current=} with {value}", file=sys.stderr)
    current[keys[-1]] = value

    return data


def main():
    args = parse_args()
    yaml = YAML()
    yaml.preserve_quotes = True
    data: Mapping[str, Any] = load_config(CONFIG_PATH, yaml)
    if args.json:
        args.value = json.loads(args.value)
    if args.value is None:
        print(f"{args.key}: {get_value(data, args.key)}")
    else:
        data = set_value(data, args.key, args.value)

        try:
            Config(**data)
        except Exception:
            logging.exception("invalid data")
        else:
            with open(CONFIG_PATH, "wb") as f:
                yaml.dump(data, f)


if __name__ == "__main__":
    main()

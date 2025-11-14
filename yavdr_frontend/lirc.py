import asyncio
from collections.abc import Awaitable
from functools import partial
import logging
import time
from typing import NoReturn
from collections.abc import Callable
from yavdr_frontend.loghandler import create_log_handler
from yavdr_frontend.config import (
    Config,
    LircConfig,
    load_yaml,
)


class LircProtocol(asyncio.Protocol):
    def __init__(
        self, config: LircConfig, on_keypress: Callable[[str], Awaitable[None]]
    ):
        self.on_con_lost = asyncio.get_running_loop().create_future()
        self.buffer = b""
        self.last_key = "KEY_COFFEE"
        self.last_ts = time.monotonic_ns()
        self.min_delta = config.min_delay * 10e6  # factor needed for nanoseconds
        self.keymap = config.keymap
        self.socket = config.socket
        self.on_keypress = on_keypress
        self.log = create_log_handler("LircProtocol", config.log_level)

    def connection_made(self, transport: asyncio.BaseTransport):
        self.log.debug(f"connected to {self.socket=}")
        return super().connection_made(transport)

    def data_received(self, data: bytes):
        for line in data.decode().split("\n"):
            # TODO: do we need to care about incomplete lines?
            if not line:  # skip empty lines
                continue
            # logging.debug(f"got line from lirc socket: {line}")
            try:
                code, repeats, key_name, source = line.split(maxsplit=3)
            except ValueError as err:
                self.log.exception(f"could not parse {line=}:\n{err}")
                return
            timestamp = self.last_ts
            previous_key = self.last_key
            self.last_ts = time.monotonic_ns()
            self.last_key = key_name
            self.log.debug(
                f"got key event: {code=}, {repeats=}, {key_name=}, {source=}"
            )
            if repeats != "0":
                self.log.debug(
                    f"ignoring {repeats} times repeated keypress for {key_name}"
                )
                return
            self.log.debug(
                f"{self.last_ts - timestamp=} <  {self.min_delta=} ? {(timestamp - self.last_ts) < self.min_delta}"
            )
            if (
                self.last_key == previous_key
                and (timestamp - self.last_ts) < self.min_delta
            ):
                self.log.debug(f"ignoring keypress within min_delta for {key_name}")
                return
            # TODO: do something with the keypress
            asyncio.ensure_future(
                self.on_keypress(key_name)
            )  # https://groups.google.com/g/python-tulip/c/z-IVH5RoDzo/m/SpZc0zTuPJsJ

    def error_received(self, exc: Exception):
        self.log.exception(f"Error received: {exc}")

    def connection_lost(self, exc: Exception | None):
        self.log.info(f"Connection closed: {exc}")
        self.on_con_lost.set_result(True)
        raise ConnectionAbortedError("lircd socket vanished")


async def handle_lirc_connection(
    on_keypress: Callable[[str], Awaitable[None]], config: Config
) -> NoReturn:
    LircProtocolWithArgs = partial(
        LircProtocol,
        config=config.lirc,
        on_keypress=on_keypress,
    )
    loop = asyncio.get_running_loop()
    while True:
        try:
            _transport, protocol = await loop.create_unix_connection(
                LircProtocolWithArgs,
                config.lirc.socket.__str__(),
            )
            await protocol.on_con_lost
        except (ConnectionAbortedError, IOError) as err:
            logging.debug(
                f"{__name__}: could not establish connection to lircd socket: {err}"
            )
            await asyncio.sleep(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    config = load_yaml()

    async def on_key_callback(cmd: str):
        print(f"pressed {cmd}")

    asyncio.run(handle_lirc_connection(on_key_callback, config))

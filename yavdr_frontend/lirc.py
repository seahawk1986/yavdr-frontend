import asyncio
from functools import partial
import logging
import time
from yavdr_frontend.loghandler import LoggingHandler
from yavdr_frontend.config import Config, LircConfig, load_yaml


class LircProtocol(asyncio.Protocol, LoggingHandler):
    def __init__(self, config: LircConfig, on_keypress: callable):
        self.on_con_lost = asyncio.get_running_loop().create_future()
        self.buffer = b""
        self.last_key = "KEY_COFFEE"
        self.last_ts = time.monotonic_ns()
        self.min_delta = config.min_delay * 10e6  # factor needed for nanoseconds
        self.keymap = config.keymap
        self.socket = config.socket
        self.on_keypress = on_keypress
        super().__init__(loglevel=config.loglevel)

    def connection_made(self, transport):
        self.log.debug(f"connected to {self.socket=}")
        return super().connection_made(transport)

    def data_received(self, data):
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
            print(
                f"{self.last_ts - timestamp=} <  {self.min_delta=} ? {(timestamp - self.last_ts) < self.min_delta}"
            )
            if (
                self.last_key == previous_key
                and (timestamp - self.last_ts) < self.min_delta
            ):
                self.log.debug(f"ignoring keypress within min_delta for {key_name}")
                return
            # TODO: do something with the keypress
            self.log.debug(f"execute key action for {key_name}")
            self.log.debug(f"{self.keymap.get(key_name)=}")
            self.last_key = key_name
            if action := self.keymap.get(key_name):
                self.on_keypress(action)

    def error_received(self, exc):
        print(f"Error received: {exc}")

    def connection_lost(self, exc):
        print(f"Connection closed: {exc}")
        self.on_con_lost.set_result(True)
        raise ConnectionAbortedError("lircd socket vanished")


async def handle_lirc_connection(on_keypress: callable, config: Config):
    lirc_config = LircConfig(
        socket="/run/lirc/lircd",
        keymap={"KEY_OK": {"action": "ok_action"}},
        loglevel="DEBUG",
    )
    LircProtocolWithArgs = partial(
        LircProtocol,
        config=config.lirc,
        on_keypress=on_keypress,
    )
    loop = asyncio.get_running_loop()
    while True:
        try:
            transport, protocol = await loop.create_unix_connection(
                LircProtocolWithArgs,
                lirc_config.socket,
            )
            await protocol.on_con_lost
        except (ConnectionAbortedError, IOError) as err:
            print(f"could not establish connection to lircd socket: {err}")
            await asyncio.sleep(0.5)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    config = load_yaml()

    def on_key_callback(cmd: str):
        print(f"pressed {cmd}")

    asyncio.run(handle_lirc_connection(on_key_callback, config))

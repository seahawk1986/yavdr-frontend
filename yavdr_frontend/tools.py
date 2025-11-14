import asyncio
import importlib
import logging
import os
from pathlib import Path
import re
import subprocess
import time
from collections.abc import Callable, Mapping, Coroutine
from typing import Any, cast

import sdbus
import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio  # pyright: ignore[reportMissingModuleSource] # noqa: E402

from yavdr_frontend.config import DBusEnum, VDRConfig  # noqa: E402
from yavdr_frontend.protocols.frontend_protocols import SystemFrontendProtocol  # noqa: E402


DISPLAY_RE = re.compile(r"(?P<host>\w+)?(?P<display>:\d)(?P<screen>\.\d)?")


def get_2nd_screen(display: str):
    """return the second screen's DISPLAY variable"""
    d = DISPLAY_RE.match(display)
    if not d:
        raise ValueError("invalid DISPLAY string")
    host = d.group("host") if d.group("host") is not None else ""
    display = d.group("display")
    screen = d.group("screen")
    if screen and screen != ".0":
        screen = ".0"
    else:
        screen = ".1"
    return "".join((host, display, screen))


def get_bus(bus: DBusEnum) -> sdbus.SdBus:
    if bus == DBusEnum.SessionBus:
        from yavdr_frontend.session_bus import session_bus

        return session_bus
    elif bus == DBusEnum.SystemBus:
        from yavdr_frontend.system_bus import system_bus

        return system_bus
    raise ValueError("invalid bus type requested:", bus)


def get_object_from_module(
    module: str, object_name: str | None = None
) -> type[SystemFrontendProtocol]:
    """
    This function tries to load a module and return an object
    from it if found.
    Default object_name is module.capitalize(), this can be overridden by
    passing a object_name argument which is not None.
    Raises an ImportError if no matching module or an AttributeError
    if no matching object ist found.
    """
    if not object_name:
        object_name = module.capitalize()
    try:
        _module = importlib.import_module(module)
    except ImportError as e:
        logging.debug("could not find a matching Module for %s", module)
        logging.exception(e)
        raise (e)
    else:
        return cast(type[SystemFrontendProtocol], getattr(_module, object_name))


def pasuspend():
    """call yavdr-pasuspend to suspend pulseaudio output"""
    try:
        subprocess.call(["yavdr-pasuspend", "-s"])
    except Exception as e:
        logging.warning("could not suspend pulseaudio output")
        logging.exception(e)
        return False
    else:
        logging.debug("successfully called yavdr-pasuspend -s")
        time.sleep(0.1)
        return True


async def paresume():
    """call yavdr-pasuspend to resume pulseaudio output"""
    # try to wait until vdr has released all sound devices
    # if wait-for-vdr-snd-release can't be executed successfully
    # sleep for timeout specified

    # TODO: make timeout configurable in configuration file
    timeout = 3
    try:
        subprocess.run(["wait-for-vdr-snd-release"], check=True)
    except Exception as e:
        logging.exception(e)
        logging.debug("waiting for %d seconds", timeout)
        await asyncio.sleep(timeout)

    try:
        subprocess.run(["yavdr-pasuspend", "-r"], check=True)
    except Exception as e:
        logging.warning("could not resume pulseaudio output")
        logging.exception(e)
        return False
    else:
        logging.debug("successfully called yavdr-pasuspend -r")
        await asyncio.sleep(0.1)
        return True


def feh_set_background(
    path: str | Path,
    fill: bool = False,
    env: dict[str, str] | Mapping[str, str] | None = None,
) -> None:
    """fill the background with the given image"""
    bg_fill = "--bg-fill" if fill else "--bg-center"
    try:
        subprocess.run(["feh", bg_fill, str(path)], check=True, env=env)
    except subprocess.CalledProcessError as e:
        logging.exception(f"could not set background to {path}: {e}")
    except Exception as e:
        logging.exception(f"unexpected error when setting background to {path}: {e}")


_MAP = {
    "y": True,
    "yes": True,
    "t": True,
    "true": True,
    "on": True,
    "1": True,
    "n": False,
    "no": False,
    "f": False,
    "false": False,
    "off": False,
    "0": False,
}


def strtobool(value: str) -> bool:
    try:
        return _MAP[str(value).lower()]
    except KeyError:
        raise ValueError('"{}" is not a valid bool value'.format(value))


def noop(*args: tuple[Any, ...], **kwargs: dict[str, Any]) -> None:
    pass


def get_vdr_service_name(config: VDRConfig) -> str:
    # returns the vdr service name for dbus2vdr depending on the instance id of the vdr
    return "de.tvdr.vdr" if config.id == 0 else f"de.tvdr.vdr{config.id}"


class DelayedRepeatableTask:
    def __init__(
        self,
        interval: float,
        callback: Callable[[], Coroutine[Any, Any, bool]],
    ):
        """
        interval: delay (in seconds) between each call, including before the first
        callback: sync or async function that returns a bool.
                  Return True to keep repeating, False to stop.
        """
        self.interval = interval
        self.callback = callback
        self._task = None
        self._stopped = asyncio.Event()

    async def _runner(self):
        try:
            while not self._stopped.is_set():
                try:
                    # Wait for either stop signal or timeout
                    await asyncio.wait_for(self._stopped.wait(), timeout=self.interval)
                    break  # If we got here, stop was signaled
                except asyncio.TimeoutError:
                    pass  # Timeout expired as expected

                result = self.callback()
                if asyncio.iscoroutine(result):
                    result = await result
                if result is False:
                    break
        except asyncio.CancelledError:
            pass
        finally:
            self._stopped.set()

    def start(self):
        if not self._task or self._task.done():
            self._stopped.clear()
            self._task = asyncio.create_task(self._runner())

    def stop(self):
        self._stopped.set()
        if self._task:
            self._task.cancel()

    def is_running(self):
        return self._task and not self._task.done()

_xdg_dirs: list[Path] = []
if _xdg_data_home := os.getenv("XDG_DATA_HOME"):
    _xdg_dirs.append(Path(_xdg_data_home) / "applications")
else:
    _xdg_dirs.append(Path.home() / ".local/share/applications")
_xdg_dirs.extend(
    Path(p) / "applications" for p in os.getenv("XDG_DATA_DIRS", "").split(":") if p
)


def get_DesktopAppInfo(desktop_entry: str) -> Gio.DesktopAppInfo:
    # get the GIO representation of the desktop file
    # we have to cover 3 cases:
    # - we get a full path to a desktop file (has to be in the expected folders)
    # - we get the id
    # - we get the filename - here the first match wins
    # if there is no match, a ValueError is raised

    try:
        if (p := Path(desktop_entry)).is_absolute() and p.name.endswith(".desktop"):
            if app := Gio.DesktopAppInfo.new_from_filename(filename=desktop_entry):
                return app
            else:
                logging.warning(f"could not find app info for {desktop_entry}")

        raise TypeError("invalid .desktop file path")
    except (TypeError, ValueError):
        try:
            if app := Gio.DesktopAppInfo.new(desktop_id=desktop_entry):
                return app
            else:
                raise TypeError("invalid desktop_id")
        except TypeError:
            print("looking for file in XDG_DIRS")
            desktop_file = (
                f"{desktop_entry}.desktop"
                if not desktop_entry.endswith(".desktop")
                else desktop_entry
            )
            for path in _xdg_dirs:
                for f in path.rglob(desktop_file):
                    if f.is_file():
                        print(f"{f=}")
                        try:
                            return Gio.DesktopAppInfo(filename=f"{f}")
                        except TypeError:
                            continue

        raise ValueError("no matching .desktop file")
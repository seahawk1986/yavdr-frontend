import importlib
import logging
import re
import subprocess
import time

import sdbus

DISPLAY_RE = re.compile(r"(?P<host>\w+)?(?P<display>:\d)(?P<screen>\.\d)?")


def get_2nd_screen(display):
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


def get_bus(config, section, key, default):
    """return a DBus Bus object by section and key in the configuration file"""
    busname = default
    try:
        busname = config[section].get(key, default)
    except KeyError as e:
        logging.warning("no key %s in section %s", e, section)
    except Exception as e:
        logging.exception(e)
    finally:
        if busname.lower() == "systembus":
            return sdbus.sd_bus_open_system()
        if busname.lower() == "sessionbus":
            return sdbus.sd_bus_open_user()


def get_object_from_module(module, object_name=None):
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
        return getattr(_module, object_name)


def pasuspend():
    """call yavdr-pasuspend to suspend pulseaudio output"""
    try:
        subprocess.call(["yavdr-pasuspend", "-s"])
    except Exception as e:
        logging.warn("could not suspend pulseaudio output")
        logging.exception(e)
        return False
    else:
        logging.debug("successfully called yavdr-pasuspend -s")
        time.sleep(0.1)
        return True


def paresume():
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
        time.sleep(timeout)

    try:
        subprocess.call(["yavdr-pasuspend", "-r"])
    except Exception as e:
        logging.warn("could not resume pulseaudio output")
        logging.exception(e)
        return False
    else:
        logging.debug("successfully called yavdr-pasuspend -r")
        time.sleep(0.1)
        return True


def feh_set_background(path, fill=False, env=None):
    """fill the background with the given image"""
    if fill:
        bg_fill = "--bg-fill"
    else:
        bg_fill = "--bg-center"
    try:
        subprocess.run(["feh", bg_fill, path], check=True, env=env)
    except subprocess.CalledProcessError as e:
        logging.info("could not set background to %s: %s", path, e)
    except Exception as e:
        logging.exception("unexpected error when setting background to %s: %s", path, e)


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


def strtobool(value):
    try:
        return _MAP[str(value).lower()]
    except KeyError:
        raise ValueError('"{}" is not a valid bool value'.format(value))

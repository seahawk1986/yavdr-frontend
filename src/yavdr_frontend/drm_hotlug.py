import asyncio
import json
import subprocess
import sys

from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field

from yavdr_frontend.config import LoggingEnum
from yavdr_frontend.loghandler import create_log_handler

DRM_BASE_PATH = Path("/sys/class/drm/")


class Connector(BaseModel):
    drm_connector: str
    edid: str
    xrandr_connector: str


def falsy_to_none(x: Any) -> Any:
    return x or None

log = create_log_handler("DRM_Hotplug", LoggingEnum.DEBUG)

OptionalConnector = Annotated[Connector | None, BeforeValidator(falsy_to_none)]


class DRMData(BaseModel):
    ignored_outputs: list[str] = Field(default_factory=list)
    primary: OptionalConnector = None
    secondary: OptionalConnector = None


class DRMModel(BaseModel):
    drm: DRMData


def load_facts() -> dict[str, Any]:
    try:
        with open("/etc/ansible/facts.d/drm.fact") as json_fact:
            data: dict[str, Any] = json.load(json_fact)
    except Exception as err:
        log.exception(f"could not load '/etc/ansible/facts.d/drm.fact': {err}")
    else:
        return data
    raise ValueError("Could not load data")

def check_configured_display(display: str) -> bool:
    try:
        r = subprocess.run(
            ["xrandr", "-d", display, "--listactivemonitors"],
            check=True,
            capture_output=True,
            text=True,
        )

        if "*" in r.stdout:
            return True
    except Exception as err:
        log.exception(f"could not read xrandr output: {err}")
    return False


async def set_display_config(connector: str, display: str) -> bool:
    cmd = [
        "xrandr",
        "-d",
        display,
        "--output",
        connector,
        "--auto",
        "--primary",
    ]
    log.debug(f"calling xrandr with '{' '.join(cmd)}'")
    try:
        r = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.SubprocessError as err:
        print(err, file=sys.stderr)
        await asyncio.sleep(1)
        return False
    return True


async def drm_hotplug(drm_data: DRMData) -> None:
    await asyncio.sleep(5)  # give the kernel time to update the state
    for n, connector in enumerate((drm_data.primary, drm_data.secondary)):
        if connector:
            for e in DRM_BASE_PATH.glob(f"card*{connector.drm_connector}/status"):
                if e.read_text().startswith("connected"):
                    # check if the edid is available
                    edid_path = e.parent / "edid"
                    log.info(f"{edid_path=}")
                    while True:
                        edid = edid_path.read_bytes()
                        if edid.strip():
                            log.debug("got edid data")
                            if not await set_display_config(
                                connector.xrandr_connector.replace("-", ""), f":0.{n}"
                            ):
                                continue

                            if check_configured_display(f":0.{n}"):
                                log.debug("found active mode")
                                break

                            log.debug("no active mode found, wait and retry...")
                            await asyncio.sleep(1)

                        log.debug(
                            "waiting for edid info to show up in drm connector..."
                        )
                        await asyncio.sleep(1)
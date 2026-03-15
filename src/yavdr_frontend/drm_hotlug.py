import asyncio
import subprocess
import sys

from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field
import yaml

from yavdr_frontend.config import LoggingEnum
from yavdr_frontend.loghandler import create_log_handler

DRM_BASE_PATH = Path("/sys/class/drm/")

DISPLAY_OUTPUTS_PATH = Path("/etc/ansible/facts.d/display_outputs.fact")
DISPLAY_CONFIG_PATH = Path("/etc/yavdr/display_config.yml")
DISPLAY_CONFIG_DEFAULT_PATH = Path("/etc/ansible/facts.d/display_config.fact")


class DisplayConfigConnector(BaseModel):
    connector: str
    resolution: str
    refreshrate: int


class OutputConnector(BaseModel):
    drm_name: str
    edid: str
    xrandr_name: str


def falsy_to_none(x: Any) -> Any:
    return x or None


log = create_log_handler("DRM_Hotplug", LoggingEnum.DEBUG)

OptionalConnector = Annotated[
    DisplayConfigConnector | None, BeforeValidator(falsy_to_none)
]


class DisplayConfig(BaseModel):
    # ignored_outputs: list[str] = Field(default_factory=list)
    primary: OptionalConnector = None
    secondary: OptionalConnector = None


class DisplayOutputData(BaseModel):
    connectors: dict[str, OutputConnector]


def load_facts() -> tuple[OutputConnector | None, OutputConnector | None]:
    try:
        display_outputs = DisplayOutputData.model_validate_json(
            DISPLAY_OUTPUTS_PATH.read_text()
        )
        try:
            display_config = DisplayConfig.model_validate(
                yaml.safe_load(DISPLAY_CONFIG_PATH.read_text())
            )
        except Exception as err:
            log.debug(err)
            display_config = DisplayConfig.model_validate_json(
                DISPLAY_CONFIG_DEFAULT_PATH.read_text()
            )

    except Exception as err:
        log.exception(f"could not load display facts and config: {err}")
    else:
        if not display_config.primary:
            raise ValueError("no primary display")
        primary_display: OutputConnector = getattr(
            display_outputs.connectors, display_config.primary.connector
        )
        if display_config.secondary:
            secondary_display: OutputConnector | None = getattr(
                display_outputs.connectors, display_config.secondary.connector
            )
        else:
            secondary_display = None
        return primary_display, secondary_display
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


async def drm_hotplug(
    primary_display: OutputConnector | None,
    secondary_display: OutputConnector | None,
) -> None:
    await asyncio.sleep(5)  # give the kernel time to update the state
    for n, connector in enumerate(filter(None, (primary_display, secondary_display))):
        if connector:
            for e in DRM_BASE_PATH.glob(f"card*{connector.drm_name}/status"):
                if e.read_text().startswith("connected"):
                    # check if the edid is available
                    edid_path = e.parent / "edid"
                    log.info(f"{edid_path=}")
                    while True:
                        edid = edid_path.read_bytes()
                        if edid.strip():
                            log.debug("got edid data")
                            if not await set_display_config(
                                connector.xrandr_name.replace("-", ""), f":0.{n}"
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

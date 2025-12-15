import json
import subprocess
import sys

from pathlib import Path
from typing import Annotated, Any
from pydantic import BaseModel, BeforeValidator, Field

DRM_BASE_PATH = Path("/sys/class/drm/")


class Connector(BaseModel):
    drm_connector: str
    edid: str
    xrandr_connector: str


def falsy_to_none(x: Any) -> Any:
    return x or None


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
        sys.exit(f"could not load '/etc/ansible/facts.d/drm.fact': {err}")
    else:
        return data


def drm_hotplug(drm_data: DRMData) -> None:
    for n, connector in enumerate((drm_data.primary, drm_data.secondary)):
        if connector:
            for e in DRM_BASE_PATH.glob(f"card*{connector.drm_connector}/status"):
                if e.read_text().startswith("connected"):
                    subprocess.run(
                        [
                            "xrandr",
                            "-d",
                            f":0.{n}",
                            "--output",
                            connector.xrandr_connector,
                            "--auto",
                            "--primary",
                        ]
                    )

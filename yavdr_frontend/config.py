import enum
import logging
import os
from pathlib import Path
from pydantic import (
    BaseModel,
    FilePath,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    field_validator,
)

from ruamel.yaml import YAML


LoglevelEnum = enum.IntEnum("LoglevelEnum", logging.getLevelNamesMapping())


class DBusEnum(enum.StrEnum):
    SessionBus = "SessionBus"
    SystemBus = "SystemBus"


class MainConfig(BaseModel):
    primary_frontend: str
    secondary_frontend: str
    systemd_bus: DBusEnum = Field(default="SessionBus")
    interface_bus: DBusEnum = Field(default="SystemBus")


class BackgroundConfig(BaseModel):
    path: FilePath
    fill: bool


class BackgroundsConfig(BaseModel):
    detached: BackgroundConfig
    normal: BackgroundConfig
    prepare_shutdown: BackgroundConfig
    shutdown: BackgroundConfig


class NamedFrontend(BaseModel):
    class_name: str
    use_pasuspend: bool = Field(default=False)


class DesktopAppFrontendConfig(BaseModel):
    app_name: str
    use_pasuspend: bool = Field(default=False)


class UnitFrontendConfig(BaseModel):
    unit_name: str
    use_pasuspend: bool = Field(default=False)


class ModuleFrontendConfig(BaseModel):
    module_name: str
    class_name: str
    use_pasuspend: bool = Field(default=False)


FrontendConfig = ModuleFrontendConfig | UnitFrontendConfig | DesktopAppFrontendConfig


class ApplicationsConfig(BaseModel):
    vdr: FrontendConfig


class StartupEnum(enum.StrEnum):
    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"


class VDRConfig(BaseModel):
    id: NonNegativeInt
    dbus2vdr_bus: DBusEnum
    attach_on_startup: StartupEnum
    wakeup_ts_file: Path
    frontends: dict[str, FrontendConfig]


class KeymapConfig(BaseModel):
    action: str  # TODO: make this an enum for the methods in yavdr_frontend
    args: list = Field(default_factory=list)


class LircConfig(BaseModel):
    socket: Path  # NOTE: to avoid cupling, this must not be a SocketPath type
    keymap: dict[str, KeymapConfig]
    min_delay: NonNegativeFloat = Field(default=0.3)
    loglevel: LoglevelEnum = Field(default=logging.INFO)

    @field_validator("loglevel", mode="before")
    @classmethod
    def transform(cls, raw: str) -> int:
        return logging.getLevelNamesMapping()[raw]


class Config(BaseModel):
    main: MainConfig
    backgrounds: BackgroundsConfig
    applications: ApplicationsConfig
    vdr: VDRConfig
    lirc: LircConfig


def load_yaml(configfile="config.yml"):
    yaml = YAML()
    for cfgfile in (
        configfile,
        os.path.expanduser("~/.config/yavdr-frontend/config.yml"),
        "/etc/yavdr-frontend/config.yml",
    ):
        try:
            with open(cfgfile) as f:
                config = Config.model_validate(yaml.load(f))
        except FileNotFoundError:
            # print(f"could not find {Path(cfgfile).absolute()}", file=sys.stderr)
            pass
        except Exception as e:
            logging.exception(e)
        else:
            return config
    raise IOError


if __name__ == "__main__":
    load_yaml()

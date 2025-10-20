import enum
import logging
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

class LoggingEnum(enum.IntEnum):
    WARNING = logging.WARNING
    CRITICAL = logging.CRITICAL
    FATAL = logging.CRITICAL
    ERROR = logging.ERROR
    INFO = logging.INFO
    DEBUG = logging.DEBUG
    NOTSET = logging.NOTSET



class DBusEnum(enum.StrEnum):
    SessionBus = "SessionBus"
    SystemBus = "SystemBus"

class ShutdownEnum(enum.StrEnum):
    VDR = "vdr"

class MainConfig(BaseModel):
    primary_frontend: str = Field(default="dummy")
    secondary_frontend: str = Field(default="dummy")
    systemd_bus: DBusEnum = Field(default=DBusEnum.SessionBus)
    interface_bus: DBusEnum = Field(default=DBusEnum.SystemBus)
    # TODO: how to signal, which busses are available?
    shutdown_manager: ShutdownEnum = Field(default=ShutdownEnum.VDR)


class BackgroundConfig(BaseModel):
    path: FilePath
    fill: bool

class BackgroundType(enum.StrEnum):
    DETACHED = "detached"
    NORMAL = "normal"
    PREPARE_SHUTDOWN = "prepare_shutdown"
    SHUTDOWN = "shutdown"

class NamedFrontend(BaseModel):
    name: str
    use_pasuspend: bool = Field(default=False)
    bus: DBusEnum = Field(default=DBusEnum.SessionBus)

class DesktopAppFrontendConfig(BaseModel):
    app_name: str
    use_pasuspend: bool = Field(default=False)
    bus: DBusEnum = Field(default=DBusEnum.SessionBus)


class UnitFrontendConfig(BaseModel):
    unit_name: str
    use_pasuspend: bool = Field(default=False)
    bus: DBusEnum = Field(default=DBusEnum.SessionBus)


class ModuleFrontendConfig(BaseModel):
    module_name: str
    class_name: str
    use_pasuspend: bool = Field(default=False)
    bus: DBusEnum = Field(default=DBusEnum.SessionBus)


FrontendConfig = (
    NamedFrontend | ModuleFrontendConfig | UnitFrontendConfig | DesktopAppFrontendConfig
)


class StartupEnum(enum.StrEnum):
    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"


class VDRStatusEnum(enum.StrEnum):
    DBUS2VDR = "dbus2vdr"
    SYSTEMD = "systemd"


class VDRConfig(BaseModel):
    id: NonNegativeInt
    dbus2vdr_bus: DBusEnum
    vdr_systemd_unit: str = Field(default="vdr.service")
    vdr_status: VDRStatusEnum = Field(default=VDRStatusEnum.DBUS2VDR)
    attach_on_startup: StartupEnum
    wakeup_ts_file: Path
    wakeup_delta_seconds: int = Field(default=10 * 60)  # ten minutes by default
    frontends: dict[str, FrontendConfig]


class KeymapConfig(BaseModel):
    action: str  # TODO: make this an enum for the methods in yavdr_frontend
    args: list[str] = Field(default_factory=list)


class LircConfig(BaseModel):
    socket: Path  # NOTE: to avoid cupling, this must not be a SocketPath type
    keymap: dict[str, KeymapConfig]
    min_delay: NonNegativeFloat = Field(default=0.3)
    loglevel: LoggingEnum = Field(default=LoggingEnum.INFO)

    @field_validator("loglevel", mode="before")
    @classmethod
    def transform(cls, raw: str) -> LoggingEnum:
        return LoggingEnum[raw]


class Config(BaseModel):
    main: MainConfig
    backgrounds: dict[BackgroundType, BackgroundConfig]
    applications: dict[str, FrontendConfig]
    vdr: VDRConfig
    lirc: LircConfig


def load_yaml(configfile: Path = Path("config.yml")):
    yaml = YAML()
    for cfgfile in (
        configfile,
        Path.home() / "/.config/yavdr-frontend/config.yml",
        Path("/etc/yavdr-frontend/config.yml"),
    ):
        try:
            print(f"try to read {cfgfile.absolute()}")
            config = Config.model_validate(yaml.load(Path(cfgfile)))  # type: ignore
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

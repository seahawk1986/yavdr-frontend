from abc import abstractmethod
from collections.abc import Generator
import enum
from typing import TYPE_CHECKING, Protocol, Self


if TYPE_CHECKING:
    from yavdr_frontend.controller import Controller
    from yavdr_frontend.vdr_controller import VDRController


class FrontendStatusEnum(enum.Enum):
    ACTIVE = enum.auto()
    INACTIVE = enum.auto()


class StartupStateEnum(enum.Enum):
    PREPARE = enum.auto()
    REGULAR = enum.auto()


class HasController(Protocol):
    controller: "Controller | VDRController"


class HasVDRController(Protocol):
    vdr_controller: "VDRController"


class FrontendProtocol(Protocol):
    name: str
    fe_type: str
    # is_running: bool
    stop_on_shutdown: bool
    prepare_shutdown_timeout: float = 0.0
    instant_shutdown_timeout: float = 0.0
    attempt_shutdown_timeout: float = 10.0
    _startup_state = StartupStateEnum.PREPARE

    @abstractmethod
    def __init__(self, controller: "Controller | VDRController | None" = None): ...

    @abstractmethod
    async def __async_init__(self) -> Self:
        # initialize all async things here
        ...

    def __await__(self) -> Generator[None, None, Self]:
        return (
            self.__async_init__().__await__()
        )  # see https://stackoverflow.com/a/58976768

    def __repr__(self) -> str:
        return f"{self.__class__}<{self.name}({self.fe_type})"

    @abstractmethod
    async def frontend_is_running(self) -> bool: ...

    # TODO: do we need a boolean return value?
    @abstractmethod
    async def start(self) -> bool | None: ...

    @abstractmethod
    async def started(self): ...

    @abstractmethod
    async def stop(self) -> bool | None: ...

    @abstractmethod
    async def stopped(self): ...

    @abstractmethod
    async def status_message(self, status: str) -> None: ...

    async def reset(self):
        self._startup_state = StartupStateEnum.PREPARE


class SystemFrontendProtocol(FrontendProtocol, HasController): ...


class VDRFrontendProtocol(FrontendProtocol, HasVDRController, HasController): ...

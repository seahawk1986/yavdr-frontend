import enum
from typing import Self, TYPE_CHECKING

if TYPE_CHECKING:
    from yavdr_frontend.controller import Controller
from yavdr_frontend.loghandler import create_log_handler
from yavdr_frontend.protocols.frontend_protocols import (
    FrontendProtocol,
)

class FrontendState(enum.Enum):
    RESTART = enum.auto()
    STOP = enum.auto()
    SWITCH = enum.auto()
    PREPARE_SHUTDOWN = enum.auto()
    QUIT = enum.auto()

class BasicFrontend(FrontendProtocol):
    name = "DummyFrontend"
    fe_type = "DummyFrontend"
    _is_running: bool = False
    stop_on_shutdown = True
    # Timeouts for yaVDRFrontend's shutdown methods
    # these can be customized by each Frontend
    instant_shutdown_timeout = 0  # Delay after poweroff is called with instant=True
    prepare_shutdown_timeout = 0  # Delay after poweroff is called with instant=False
    attempt_shutdown_timeout = (
        10  # Delay after prepare_shutdown is called to call attempt_shutdown
    )

    def __init__(
        self,
        controller: "Controller",
        name: str | None = None,
        fe_type: str | None = None,
    ):
        if name:
            self.name = name
        self.log = create_log_handler(self.name)
        if fe_type:
            self.fe_type = fe_type
        self.controller = controller

    async def __async_init__(self) -> Self:
        return self

    async def frontend_is_running(self) -> bool:
        return self._is_running

    async def status_message(self, status: str):
        self.log.info(f"{status}, {self.name}, {self.fe_type}")

    async def start(self):
        await self.status_message("starting")
        await self.started()

    async def started(self):
        self._is_running = True

    async def stop(self):
        await self.status_message("stopping")
        # signal stopped() if there is no callback possible (e.g. softhddevice)
        await self.stopped()

    async def stopped(self):
        self._is_running = False
        await self.status_message("stopped")
        await self.controller.on_stopped(self)

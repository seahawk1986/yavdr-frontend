import asyncio
from collections.abc import Generator
from typing import Any, Protocol, Self, TYPE_CHECKING
from sdbus import SdBus

from yavdr_frontend.config import (
    LoggingEnum,
    UnitFrontendConfig,
)
from yavdr_frontend.basicfrontend import FrontendProtocol

if TYPE_CHECKING:
    from yavdr_frontend.controller import Controller
    from yavdr_frontend.vdr_controller import VDRController
from yavdr_frontend.loghandler import create_log_handler
from yavdr_frontend.protocols.frontend_protocols import (
    HasController,
)
from yavdr_frontend.tools import get_bus
from yavdr_frontend.interfaces.systemd_unit_interface import (
    OrgFreedesktopSystemd1UnitInterface,
)
from yavdr_frontend.interfaces.systemd_dbus_interface import (
    OrgFreedesktopSystemd1ManagerInterface,
    create_systemd_manager_proxy,
    SYSTEMD_DBUS_INTERFACE,
)

# basic idea:
# ehen starting a unit, systemd uses a job to keep track of the start process
# when the job ends, we know, if it succeeded
# when the unit is stopped, there is also a job created for this
# Also we track the UnitRemoved Signal on the SystemdManager interface to know when a Unit was stopped (either via Systemd or via User interaction)
# Systemd PropertiesChanged signals are unreliable and event UnitRemoved Signals might occure more than once.


class SystemdUnit:
    def __init__(
        self,
        unit_name: str,
        systemd_dbus: SdBus,
        frontend: "SystemdUnitFrontend",
    ):
        self.log = create_log_handler(f"SystemdUnit<{unit_name}>", LoggingEnum.DEBUG)
        self.unit_name = unit_name
        self.systemd_dbus = systemd_dbus
        self.systemd_manager_proxy = create_systemd_manager_proxy(
            bus=self.systemd_dbus,
        )
        self.frontend = frontend
        self.unit_stop_tracker: None | asyncio.Task[None] = None

    async def __async_init__(self) -> Self:
        # await self.systemd_manager_proxy.subscribe()
        self.unit_object_path = await self.systemd_manager_proxy.load_unit(
            self.unit_name
        )
        self.unit_proxy = OrgFreedesktopSystemd1UnitInterface.new_proxy(
            SYSTEMD_DBUS_INTERFACE, self.unit_object_path, bus=self.systemd_dbus
        )
        # INFO: we need to call the Subscribe() method for the org.freedesktop.systemd1.Manager interface on the /org/freedesktop/systemd1 object once.
        # this happens in the SystemdUnitFrontend class, so we don't have to do it here
        self._is_running: bool = await self.get_status()
        return self

    def __await__(self) -> Generator[Any, None, Self]:
        return (
            self.__async_init__().__await__()
        )  # see https://stackoverflow.com/a/58976768

    async def track_job(self, current_job_path: str):
        async for (
            job_id,
            job_path,
            unit_name,
            result,
        ) in self.systemd_manager_proxy.job_removed:
            if current_job_path == job_path:
                self.log.debug(f"job {job_path} ended: {result}")
                if result != "done":
                    self.log.error(
                        f"job {job_path} with id: {job_id} for {unit_name} ended: {result}"
                    )
                else:
                    if self.unit_stop_tracker is None:
                        print(f"adding tracker for {self.unit_name}")
                        self.unit_stop_tracker = asyncio.create_task(
                            self.on_unit_removed()
                        )
                return result == "done"  # only in this case the job was successful

    async def start(self):
        current_job_path = await self.systemd_manager_proxy.start_unit(
            self.unit_name, "replace"
        )
        return await self.track_job(current_job_path=current_job_path)

    async def stop(self):
        current_job_path = await self.systemd_manager_proxy.stop_unit(
            self.unit_name, "replace"
        )
        return await self.track_job(current_job_path=current_job_path)

    async def on_unit_removed(self):
        async for unit_name, unit_path in self.systemd_manager_proxy.unit_removed:
            if self.unit_object_path == unit_path:
                self.log.debug(f"{unit_path} ({unit_name}) removed, done")
                self.unit_stop_tracker = None
                await (
                    self.frontend.stopped()
                )  # this signals the controller that the unit was stopped
                return

    async def check_state(self, active_state: str, sub_state: str) -> bool:
        self.log.debug(f"{active_state=}, {sub_state=}")
        if active_state == "active" and sub_state in ("active", "running"):
            self._is_running = True

        elif active_state in ("inactive", "dead", "failed") and sub_state in (
            "dead, failed"
        ):
            self._is_running = False
        return self._is_running

    async def is_running(self) -> bool:
        active_state = await self.unit_proxy.active_state
        sub_state = await self.unit_proxy.active_state
        return await self.check_state(active_state, sub_state)

    async def get_status(self):
        return (
            True
            if (
                await self.unit_proxy.active_state == "active"
                and await self.unit_proxy.active_state == "running"
            )
            else False
        )


# TODO: create extra classes depending on if this is a foo.service or a app@foo.service


class SystemdUnitProtocol(Protocol):
    name: str
    unit_name: str
    fe_type: str
    systemd_bus = SdBus
    systemd_manager_proxy: OrgFreedesktopSystemd1ManagerInterface


class SystemdUnitFrontend(
    FrontendProtocol,
    HasController,
    SystemdUnitProtocol,
):
    def __init__(
        self,
        config: UnitFrontendConfig,
        controller: "Controller | VDRController",
        fe_type: str = "",  # TODO: this should be an enum
    ):
        self._is_running: bool = False
        self.stop_on_shutdown: bool = False
        self.name = config.unit_name
        self.log = create_log_handler(name=self.name, logLevel=LoggingEnum.DEBUG)
        self.unit_name = (
            config.unit_name
            if config.unit_name.endswith(".service")
            else f"{config.unit_name}.service"
        )
        self.fe_type = fe_type
        self.controller = controller
        self.systemd_bus = get_bus(config.bus)
        self.systemd_manager_proxy = create_systemd_manager_proxy(
            bus=self.systemd_bus,
        )

        self.last_status_signal = ("", "")
        self.is_active = False
        self._was_started = False

        # TODO: We might need to add rules to handle systemd-units for the system: https://wiki.archlinux.org/title/Polkit#Allow_management_of_individual_systemd_units_by_regular_users

    async def __async_init__(self) -> Self:
        # await self.systemd_manager_proxy.subscribe()
        self.unit = await SystemdUnit(
            unit_name=self.unit_name, systemd_dbus=self.systemd_bus, frontend=self
        )
        return self

    def __await__(self) -> Generator[Any, None, Self]:
        return (
            self.__async_init__().__await__()
        )  # see https://stackoverflow.com/a/58976768

    async def frontend_is_running(self) -> bool:
        return await self.unit.is_running()


    async def start(self):
        self.is_active = True
        self.log.debug(f"starting {self.unit_name}")
        _success = await self.unit.start()

    async def started(self): ...

    async def stop(self):
        self.is_active = False
        self.log.debug(f"stopping {self.unit_name}")
        _success = await self.unit.stop()

    async def stopped(self):
        # TODO: we need to switch frontends if the systemd unit exited normally
        #       And avoid restarting it instead
        self.log.debug(f"stopped {self.name}")
        await self.controller.on_stopped(self)
        self.is_active = (
            False  # TODO: is this correct or can a unit be restarted in this case?
        )

    async def status_message(self, status: str) -> None:
        raise NotImplementedError()
import asyncio
from collections.abc import Generator
from typing import Any, Protocol, Self, TYPE_CHECKING
from sdbus import SdBus
from sdbus.utils.parse import parse_properties_changed

from yavdr_frontend.config import (
    DesktopAppFrontendConfig,
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


class SystemdUnit:
    def __init__(self, unit_name: str, systemd_dbus: SdBus):
        self.log = create_log_handler(f"SystemdUnit<{unit_name}>")
        self.unit_name = unit_name
        self.systemd_dbus = systemd_dbus
        self.systemd_manager_proxy = create_systemd_manager_proxy(
            bus=self.systemd_dbus,
        )

    async def __async_init__(self) -> Self:
        self.unit_object_path = await self.systemd_manager_proxy.load_unit(
            self.unit_name
        )
        self.unit_proxy = OrgFreedesktopSystemd1UnitInterface.new_proxy(
            SYSTEMD_DBUS_INTERFACE, self.unit_object_path, bus=self.systemd_dbus
        )
        self._is_running: bool = (
            True
            if (
                await self.unit_proxy.active_state == "active"
                and await self.unit_proxy.active_state == "running"
            )
            else False
        )
        self.status_monitor = asyncio.create_task(self.on_unit_change())
        return self

    def __await__(self) -> Generator[Any, None, Self]:
        return (
            self.__async_init__().__await__()
        )  # see https://stackoverflow.com/a/58976768

    async def on_unit_change(self):
        async for s in self.unit_proxy.properties_changed:
            p = parse_properties_changed(
                OrgFreedesktopSystemd1UnitInterface, s, "ignore"
            )
            self.log.info(p)
            self.check_state(p.get("active_state", ""), p.get("sub_state", ""))

    def check_state(self, active_state: str, sub_state: str):
        match (active_state, sub_state):
            case ("active", "running") | ("active", "active"):
                self._is_running = True
                self.log.debug(f"{self.unit_name} is running")
            case ("inactive", "dead") | ("failed", "dead"):
                self._is_running = False
                self.log.debug(f"{self.unit_name} is stopped")
            case _:
                self.log.warning(f"unhandled state: {active_state}, {sub_state}")
        return self._is_running

    async def is_running(self) -> bool:
        active_state = await self.unit_proxy.active_state
        sub_state = await self.unit_proxy.active_state
        return self.check_state(active_state, sub_state)


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
        self.systemd_dbus = get_bus(config.bus)
        self.systemd_manager_proxy = create_systemd_manager_proxy(
            bus=self.systemd_dbus,
        )
        # TODO: We might need to add rules to handle systemd-units for the system: https://wiki.archlinux.org/title/Polkit#Allow_management_of_individual_systemd_units_by_regular_users

    async def __async_init__(self) -> Self:
        self.log.debug(
            f"Systemd Units: {await self.systemd_manager_proxy.list_units()}"
        )
        self.unit = await SystemdUnit(self.unit_name, self.systemd_dbus)
        self.unit_object_path = await self.systemd_manager_proxy.load_unit(
            self.unit_name
        )
        self.log.debug(f"got Unit path: {self.unit_object_path}")
        self.status_monitor = asyncio.create_task(self.on_unit_change())
        return self

    def __await__(self) -> Generator[Any, None, Self]:
        return (
            self.__async_init__().__await__()
        )  # see https://stackoverflow.com/a/58976768

    async def frontend_is_running(self) -> bool:
        return await self.unit.is_running()

    async def on_unit_change(self):
        async for s in self.unit.unit_proxy.properties_changed:
            p = parse_properties_changed(
                OrgFreedesktopSystemd1UnitInterface, s, "ignore"
            )
            self.log.info(p)
            self.unit.check_state(p.get("active_state", ""), p.get("sub_state", ""))

            # if (
            #     p.get("active_state") == active_state
            #     and p.get("sub_state") == sub_state
            # ):
            # return

    async def start(self):
        self.log.debug(f"starting {self.unit_name}")
        job = await self.systemd_manager_proxy.start_unit(self.unit_name, "replace")
        self.log.debug(f"start result for {self.name}: {job}")

    async def started(self): ...

    async def stop(self):
        self.log.debug(f"stopping {self.unit_name}")
        job = await self.systemd_manager_proxy.stop_unit(self.unit_name, "replace")
        self.log.debug(f"{job=}")
        await self.stopped()

    async def stopped(self):
        self.log.debug(f"stopped {self.name}")
        await self.controller.on_stopped(self)

    async def status_message(self, status: str): ...


class SystemdAppUnitFrontend(FrontendProtocol, SystemdUnitProtocol):
    config: DesktopAppFrontendConfig

    def __init__(
        self,
        config: DesktopAppFrontendConfig,
        controller: "Controller | None" = None,
        fe_type: str = "",  # TODO: this should be an enum
    ):
        self._is_running = False
        self.stop_on_shutdown: bool = False
        self.name = config.app_name
        self.unit_name = config.app_name
        self.log = create_log_handler(self.unit_name)
        self.fe_type = fe_type
        self.systemd_dbus = get_bus(config.bus)
        self.systemd_manager_proxy = create_systemd_manager_proxy(
            bus=self.systemd_dbus,
        )
        # TODO: We might need to add rules to handle systemd-units for the system: https://wiki.archlinux.org/title/Polkit#Allow_management_of_individual_systemd_units_by_regular_users


# class SystemdUnitFrontend(FrontendProtocol):
#     def __init__(
#         self, controller: Controller, name: str = "SystemdUnit", fe_type: str = "unit"
#     ):
#         self.name = name
#         self.log = create_log_handler(self.name)
#         self.fe_type = fe_type
#         self.controller = controller
#         self.log.debug("init SystemdUnit with name: %s and fe_type: %s", name, fe_type)
#         self.systemd = controller.systemd_manager

#     async def __async_init__(self) -> Self:
#         try:
#             await self.set_unit_name()
#         except ValueError:
#             raise
#         except Exception as e:
#             self.log.exception(e, exc_info=True)
#         return self

#     async def set_unit_name(self):
#         if self.fe_type == "app":
#             self.unit_name = subprocess.check_output(
#                 ["systemd-escape", "--template=app@.service", self.name],
#                 universal_newlines=True,
#             ).rstrip()
#         else:
#             if not self.name.endswith(".service"):
#                 self.unit_name = self.name + ".service"
#             else:
#                 self.unit_name = self.name
#             if (
#                 os.path.splitext(self.unit_name)[0]
#                 not in await self.controller.get_systemd_unit_names()
#             ):
#                 raise ValueError(
#                     (f"unknown unit name {self.unit_name}, check your config!")
#                 )
#         self.log.debug(f"set_unit_name: {self.unit_name}")

#     async def start(self):
#         self.log.debug(f"starting {self.name}")
#         self.add_signal_callback(self.on_signal)
#         try:
#             await self.systemd.start_unit(self.unit_name, "fail")
#         except Exception as e:
#             self.log.exception(e)

#     async def stop(self):
#         self.log.debug(f"stopping {self.name}")
#         try:
#             await self.systemd.stop_unit(self.unit_name, "fail")
#         except Exception as e:
#             self.log.exception(e)

#     async def stopped(self):
#         self.log.debug(f"stopped {self.name}")
#         self.remove_signal_callback()
#         await super().stopped()

#     def add_signal_callback(self, callback):
#         self.log.debug(f"enable PropertiesChanged callback for {self.name}")
#         self.unit_proxy = self.controller.bus.get(
#             ".systemd1", self.systemd.LoadUnit(self.unit_name)
#         )
#         self.pchanged_con = self.unit_proxy.PropertiesChanged.connect(callback)

#     def remove_signal_callback(self):
#         self.log.debug(f"disable PropertiesChanged callback for {self.name}")
#         self.pchanged_con.disconnect()

#     def on_signal(self, *args):
#         """
#         Callback executed on PropertiesChanged Signal.

#         Since systemd's signal data in Ubuntu 20.04 (systemd-244) are not representing
#         the actual property values (e.g. wrongly reporting that a unit is dead if starting up):

#         ActiveState Signal: inactive
#         SubState Signal: dead
#         vs.
#         ActiveState Property: activating
#         SubState Property: start-pre

#         we can ignore them completely and rely on the actual property values.
#         """

#         self.log.debug(f"got PropertiesChanged signal: {args}", args)

#         active_state = self.unit_proxy.active_state
#         sub_state = self.unit_proxy.sub_state
#         if active_state == "active" and sub_state == "running":
#             self.log.debug("unit is running")
#             await self.started()
#         elif (active_state, sub_state) in (("inactive", "dead"), ("failed", "dead")):
#             self.log.debug(f"unit {self.unit_name} stopped")
#             await self.stopped()

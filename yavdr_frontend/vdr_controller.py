from abc import abstractmethod
import asyncio
from collections.abc import Generator
import enum
import os
import time
from typing import Any, NamedTuple, Protocol, Self, cast, TYPE_CHECKING

from sdbus.utils.parse import parse_properties_changed


# from pydbus2vdr import DBus2VDR
from yavdr_frontend.interfaces.org_freedesktop_dbus import OrgFreedesktopDBusInterface
from yavdr_frontend.interfaces.vdr_devices import DeTvdrVdrDeviceInterface
from yavdr_frontend.protocols.frontend_protocols import (
    FrontendProtocol,
    FrontendStatusEnum,
    StartupStateEnum,
)
from yavdr_frontend.config import BackgroundType, FrontendConfig, LoggingEnum, VDRConfig

if TYPE_CHECKING:
    from yavdr_frontend.controller import Controller
from yavdr_frontend.frontend_manager import system_frontend_factory
from yavdr_frontend.interfaces.systemd_dbus_interface import (
    create_systemd_manager_proxy,
)
from yavdr_frontend.interfaces.systemd_unit_interface import (
    OrgFreedesktopSystemd1UnitInterface,
)
from yavdr_frontend.interfaces.vdr_plugins import (
    DeTvdrVdrPluginInterface,
    DeTvdrVdrPluginmanagerInterface,
)
from yavdr_frontend.interfaces.vdr_remote import DeTvdrVdrRemoteInterface
from yavdr_frontend.interfaces.vdr_setup import DeTvdrVdrSetupInterface
from yavdr_frontend.interfaces.vdr_shutdown import DeTvdrVdrShutdownInterface
from yavdr_frontend.interfaces.vdr_status import (
    DeTvdrVdrStatusInterface,
    DeTvdrVdrVdrInterface,
)
from yavdr_frontend.loghandler import create_log_handler
from yavdr_frontend.tools import get_bus, get_vdr_service_name


class StartType(enum.Enum):
    MANUAL = enum.auto()
    VDR_WAKEUP = enum.auto()
    OTHER_WAKEUP = enum.auto()
    UNKNOWN = enum.auto()


class VDRDevice(NamedTuple):
    idx: int
    number: int
    has_decoder: int
    is_primary: bool
    name: str


class DBus2VDR:
    def __init__(self, vdr_config: VDRConfig):
        self.vdr_bus = get_bus(vdr_config.dbus2vdr_bus)
        vdr_service_name = get_vdr_service_name(vdr_config)

        self.vdr_device = DeTvdrVdrDeviceInterface.new_proxy(
            vdr_service_name, "/Devices", bus=self.vdr_bus
        )
        self.vdr_status = DeTvdrVdrStatusInterface.new_proxy(
            vdr_service_name, "/Status", bus=self.vdr_bus
        )
        self.vdr_plugin_manager = DeTvdrVdrPluginmanagerInterface.new_proxy(
            vdr_service_name, "/Plugins", bus=self.vdr_bus
        )
        self.vdr_vdrstatus = DeTvdrVdrVdrInterface.new_proxy(
            vdr_service_name, "/vdr", bus=self.vdr_bus
        )
        self.vdr_setup = DeTvdrVdrSetupInterface.new_proxy(
            vdr_service_name, "/Setup", bus=self.vdr_bus
        )

        self.vdr_remote = DeTvdrVdrRemoteInterface.new_proxy(
            vdr_service_name, "/Remote", bus=self.vdr_bus
        )

        self.vdr_shutdown = DeTvdrVdrShutdownInterface.new_proxy(
            vdr_service_name, "/Shutdown", bus=self.vdr_bus
        )

    async def request_primary_by_name(self, name: str):
        devices = [VDRDevice(*d) for d in await self.vdr_device.list()]
        for device in devices:
            if device.name == name:
                return await self.vdr_device.request_primary(device.idx)

    async def svdrpcommand(
        self, plugin_name: str, cmd: str, option: str = ""
    ) -> tuple[int, str]:
        plugin_interface = DeTvdrVdrPluginInterface.new_proxy(
            "de.tvdr.vdr", f"/Plugins/{plugin_name}", bus=self.vdr_bus
        )
        return await plugin_interface.svdrpcommand(cmd, option)


class VDRController(FrontendProtocol):
    bus = None
    send_DLIC = False
    prepare_shutdown_timeout = 20
    attempt_shutdown_timeout = 5 * 60
    unit_name = "vdr.service"
    dbus2vdr: DBus2VDR

    def __init__(
        self, controller: "Controller", name: str = "VDR-Frontend", fe_type: str = "vdr"
    ):
        self._state = StartupStateEnum.PREPARE
        self.controller = controller
        self.config = controller.config
        self.name = name
        self.log = create_log_handler(
            self.name, LoggingEnum.DEBUG
        )  # TODO make this configurable
        self.fe_type = fe_type
        self.log.debug(f"init VDRFrontend with name '{name}' and fe_type '{fe_type}'")
        self.start = self._startup
        self.frontend: None | FrontendProtocol = None
        self.stop_on_shutdown = (
            True if self.config.vdr.attach_on_startup != "always" else False
        )
        self.systemd = controller.systemd_manager
        self.bus = get_bus(controller.config.vdr.dbus2vdr_bus)
        self.systemd_manager_proxy = create_systemd_manager_proxy(bus=self.bus)

        self.do_startup = True
        self.dbus2vdr = DBus2VDR(self.config.vdr)
        self.__vdr_status_task = asyncio.create_task(
            self.on_status_change()
        )  # track changes of the VDR dbus2vdr interface

    async def __async_init__(self) -> Self:
        # self.log.debug("running async init")
        try:
            self.unit_object_path = await self.systemd_manager_proxy.load_unit(
                self.unit_name
            )
            # self.dbus2vdr = DBus2VDR(self.bus, watchdog=True)
        except Exception as e:
            self.log.exception(e)
        else:
            self.status_change = self.dbus2vdr.vdr_status.properties_changed
            # self.dbus2vdr.status_change_callbacks.append(self.on_vdr_status_change)
            # TODO: use Systemd Status
            # TODO: we need to call load_frontend later if the VDR was not running
            # self.log.debug(
            #     f"{(await self.controller.vdr_status.is_running())=} {await self.vdr_is_ready()=}"
            # )
            if (
                await self.controller.vdr_status.is_running()
                and await self.vdr_is_ready()
            ):
                # self.log.debug("loading frontend")
                await self.load_frontend()

        return self

    async def start(self):
        self.log.debug(f"called start(), {self._startup_state=}")
        match self._startup_state:
            case StartupStateEnum.PREPARE:
                await self._startup()
            case StartupStateEnum.REGULAR:
                await self._start()

    def __await__(self) -> Generator[Any, None, Self]:  # noqa: F821
        return (
            self.__async_init__().__await__()
        )  # see https://stackoverflow.com/a/58976768

    async def on_status_change(self):
        async for s in self.dbus2vdr.vdr_status.properties_changed:
            p = parse_properties_changed(DeTvdrVdrVdrInterface, s, "ignore")
            print(f"vdr status change: {p}")
            # await self.on_vdr_status_change()

    # TODO: this method seems not to be used
    # async def on_vdr_ready(self):
    #     await self.load_frontend()

    async def on_vdr_status_change(self, vdr_is_running: bool):
        try:
            if await self.vdr_is_ready():
                await self.load_frontend()
                if isinstance(self.controller.frontends[0], VDRController):
                    await self.start()
                else:
                    await self.disable_remote()
            else:
                if self.frontend:
                    await self.frontend.stop()
                    self.frontend = None
        except Exception as err:
            self.log.warning(f"{err}")

    async def enable_remote(self):
        await self.dbus2vdr.vdr_remote.enable()
        if self.HAS_CEC:
            self.log.info("attaching cecremote")
            await self.dbus2vdr.svdrpcommand(plugin_name="cecremote", cmd="CONN")

    async def disable_remote(self):
        await self.dbus2vdr.vdr_remote.disable()
        if self.HAS_CEC:
            self.log.info("detaching cecremote")
            await self.dbus2vdr.svdrpcommand("cecremote", "DISC")

    async def attempt_shutdown(self):
        """this is the actual implementation of the shutdown method"""
        if self.frontend is None:
            self.log.info("VDR not running, trying again")
            return True
        # startup = self.controller.config.vdr.attach_on_startup # TODO: what is this for?
        try:
            code, msg, *_ = await self.dbus2vdr.vdr_shutdown.confirm_shutdown(
                ignoreuser=True
            )
            self.log.info("attempt_shutdown: %s", msg)
            if code == 250:
                await self.dbus2vdr.vdr_remote.enable()
                await self.dbus2vdr.vdr_remote.hit_key("Power")
                await self.dbus2vdr.vdr_remote.disable()
        except Exception as e:
            self.log.exception(e)
        finally:
            return True

    async def get_systemd_unit_names(self) -> list[str]:
        """
        this method returns the existing unit names.
        Don't remove or self.controller.get_frontend called with two arguments won't work!
        """
        return [
            os.path.basename(unit[0])
            for unit in await self.systemd_manager_proxy.list_unit_files()
        ]

    async def load_frontend(self):
        """
        This function sets self.frontend with the first match of plugins loaded
        by the VDR and the configured frontends in the configuration file's
        'vdr-frontend' section.
        """
        self.plugins = [
            plugin for plugin, _version in await self.dbus2vdr.vdr_plugin_manager.list()
        ]
        self.send_DLIC = "skindesigner" in self.plugins
        self.HAS_CEC = "cecremote" in self.plugins
        for plugin in self.plugins:
            # self.log.debug(f"checking for {plugin=}")
            config = self.controller.config.vdr.frontends.get(plugin)
            if config:  # there is an entry for the current plugin
                try:
                    frontend: FrontendProtocol = await system_frontend_factory(
                        config, controller=self
                    )
                except ValueError:
                    continue
                else:
                    self.frontend = frontend
                    self.log.debug(f"set {frontend=}")
                    return  # stop searching if we got a match
            # else:
            #     self.log.debug(f"could not find config for {plugin}")
        self.log.warning("No matching frontend could be found.")

    async def get_frontend(
        self,
        frontend_config: FrontendConfig,
        controller: "VDRController",
    ) -> FrontendProtocol: ...

    async def is_user_active(self):
        is_active = False
        try:
            is_active = await self.dbus2vdr.vdr_shutdown.is_user_active()
        except Exception as e:
            self.log.debug(f"Could not retrieve Shutdown.IsUserActive(): {e}")
        return is_active

    async def start_type(self) -> StartType:
        """
        Returns an enum StartType.
        We need to cover three cases:
            - Manual start (no timer or acpiwakeup): StartType.ManualStart
            - Start for a timer or vdr plugin:       StartType.VDR_WAKEUP
            - Start for vdr-addon-acpiwakeup:        StartType.OTHER_WAKEUP
        """

        def wakeup_timestamp_in_range(
            current_timestamp: float, wakeup_timestamp: float, delta_seconds: float
        ):
            return abs(current_timestamp - wakeup_timestamp) <= delta_seconds

        async def is_vdr_manual_start() -> StartType:
            try:
                is_manual_start = await self.dbus2vdr.vdr_shutdown.manual_start()
            except Exception as e:
                self.log.debug(f"calling dbus2vdr.Shutdown.ManualStart() failed: {e}")
            else:
                if is_manual_start:
                    return StartType.MANUAL
                else:
                    self.log.debug("Assuming Wakeup for VDR")
                    return StartType.VDR_WAKEUP
            return StartType.UNKNOWN

        start_type: StartType = await is_vdr_manual_start()
        if start_type != StartType.VDR_WAKEUP:
            try:
                wakeup_timestamp = int(
                    self.config.vdr.wakeup_ts_file.read_text().strip()
                )
            except ValueError:
                self.log.warning(
                    f"{self.config.vdr.wakeup_ts_file} does not contain a valid timestamp"
                )
            except IOError as e:
                self.log.debug(
                    "could not read %s: %s", self.config.vdr.wakeup_ts_file, e
                )
            else:
                if wakeup_timestamp_in_range(
                    current_timestamp=time.time(),
                    wakeup_timestamp=wakeup_timestamp,
                    delta_seconds=self.config.vdr.wakeup_delta_seconds,
                ):
                    start_type = StartType.OTHER_WAKEUP

        return start_type

    async def _start(self):
        # self.log.debug(f"{self.frontend=}")
        if not self.frontend:
            await self.controller.set_background(BackgroundType.NORMAL)
            return False
        if self.controller.expect_user_activity:
            await self.controller.set_background(BackgroundType.DETACHED)
            return True
        else:
            await self.controller.set_background(BackgroundType.NORMAL)
            user_active = await self.is_user_active() if self.do_startup else True
            self.log.debug(f"user is active: {user_active}")
            self.log.debug(
                f"starting vdr frontend {self.frontend.name}, current frontend is {self.frontend}"
            )
            await self.frontend.start()
            if not user_active:
                await self.dbus2vdr.vdr_shutdown.set_user_inactive()
                self.log.debug("set user inactive")
            await self.enable_remote()
            if self.controller.expect_user_activity:
                self.controller.expect_user_activity = False
            return True

    async def _startup(self):
        """
        Attach VDR Frontend on first call of this method only if:
        - manual start
        - wakeup start and user has chosen to attach the frontend anyway
        Set a shutdown timer if start_t is StartType.OTHER_WAKEUP (in this
        case the vdr sees the user active).
        """

        # this method is called by yaVDRFrontend regardless if VDR is ready, so
        # we need a mechanism to abort early
        # if not self.dbus2vdr.vdr_isready:
        if not await self.vdr_is_ready():
            self.log.warning("startup(): VDR is not ready")
            return

        start_t: StartType = await self.start_type()

        self.log.debug(f"start_t has value {start_t}")
        if start_t is StartType.OTHER_WAKEUP:
            try:
                (
                    (_tuple_data),
                    min_user_inactivity,
                    _data,
                ) = await self.dbus2vdr.vdr_setup.get("MinUserInactivity")
                self.log.debug(f"VDR MinUserInactivity: {min_user_inactivity}")

            except ValueError:
                self.log.debug("Retrieving MinUserInactivity failed")
                return
            except Exception as e:
                self.log.exception("Could not connect to dbus2vdr: %s", e)
                return
            else:
                if min_user_inactivity > 0:
                    shutdown_delay: float = 0.0
                    try:
                        shutdown_delay_response = (
                            await self.dbus2vdr.vdr_setup.get("MinEventTimeout") * 60
                        )
                        (shutdown_delay_value, _msg) = shutdown_delay_response
                        if shutdown_delay:
                            shutdown_delay = float(
                                cast(int | str, shutdown_delay_value)
                            )  # here the dbus2vdr interface is a bit muddy
                    except ValueError:
                        self.log.debug("Retrieving MinEventTimeout failed")
                    except Exception as e:
                        self.log.exception("Could not connect to dbus2vdr: %s", e)
                    finally:
                        if "shudown_delay" not in locals():
                            shutdown_delay = 30 * 60

                        self.log.debug(f"shutdown_delay is {shutdown_delay} seconds")
                        # TODO: can we move this to the controller?
                        if self.controller.shutdown_queue.empty():
                            await self.controller.delay(
                                shutdown_delay,
                                self.controller.poweroff(instant=True),
                            )
                            # poweroff_timer = GLib.timeout_add_seconds(
                            #   shutdown_delay, self.controller.poweroff, instant=True
                            # )

        if start_t == StartType.UNKNOWN:
            return
        else:
            self._state = StartupStateEnum.REGULAR
            self.log.debug(f"setting {self._state=:s}")
            # self.start = self._start  # switch to the regular start method

        startup = self.controller.config.vdr.attach_on_startup
        self.log.debug(f"attach_on_startup: {startup}")

        if (
            startup == "auto" and start_t is not StartType.MANUAL
        ) or startup == "never":
            self.controller.expect_user_activity = True
        await self._start()

    async def stop(self):
        if await self.vdr_is_ready():
            await self.disable_remote()
        if self.frontend:
            await self.frontend.stop()
        if self.send_DLIC:
            await self.dbus2vdr.svdrpcommand("skindesigner", "DLIC")

    async def status(self) -> FrontendStatusEnum:
        if self.frontend and await self.frontend.frontend_is_running():
            return FrontendStatusEnum.ACTIVE
        return FrontendStatusEnum.INACTIVE

    async def on_stopped(self, caller: FrontendProtocol) -> None:
        await self.controller.on_stopped(self)

    async def frontend_is_running(self) -> bool:
        if self.frontend:
            return await self.frontend.frontend_is_running()
        return False

    async def vdr_is_ready(self) -> bool:
        return await self.dbus2vdr.vdr_vdrstatus.status() == "Ready"

    async def started(self) -> None:
        raise NotImplementedError

    async def stopped(self) -> None:
        raise NotImplementedError

    async def status_message(self, status: str) -> None:
        self.log.info(f"{await self.frontend_is_running()=}")


class VDRStatusProtocol(Protocol):
    @abstractmethod
    async def is_running(self) -> bool:
        ...

        #     if config.vdr_status == VDRStatusEnum.SYSTEMD:
        #     self.vdr_unit = OrgFreedesktopSystemd1UnitInterface(
        #         "org.freedesktop.systemd1",
        #         "/org/freedesktop/systemd1/unit/vdr_2eservice",
        #         bus=self.vdr_bus,
        #     )
        #     self.is_running: callable[[], bool] = self.is_systemd_unit_running
        # elif config.vdr_status == VDRStatusEnum.DBUS2VDR:


class NameOwnerChangedSignal(NamedTuple):
    name: str
    old_owner: str
    new_owner: str


class DBus2VDRStatusHandler(VDRStatusProtocol):
    def __init__(self, config: VDRConfig, loglevel: LoggingEnum = LoggingEnum.INFO):
        self.config = config
        self.bus = get_bus(config.dbus2vdr_bus)
        self.vdr_name = f"de.tvdr.vdr{'' if self.config.id == 0 else self.config.id}"
        self.log = create_log_handler(
            f"{self.__class__.__name__}<{self.vdr_name}>", loglevel
        )
        self.vdr_bus_owner: str = ""

        self.vdr_status = DeTvdrVdrVdrInterface.new_proxy(
            get_vdr_service_name(config),
            "/vdr",
            bus=self.bus,
        )

        self.dbus_signals = OrgFreedesktopDBusInterface.new_proxy(
            "org.freedesktop.DBus", "/org/Freedesktop/DBus", self.bus
        )

    async def is_running(self) -> bool:
        self.log.debug(f"{await self.vdr_status.status()=}")
        return (await self.vdr_status.status()) == "Ready"

    # TODO: track NameOwnerChanged signals

    async def track_name_owner_changed(self):
        async for s in self.dbus_signals.name_owner_changed:
            signal = NameOwnerChangedSignal(*s)
            print(f"got signal {signal}")
            if signal.name == self.vdr_name and len(signal.old_owner) == 0:
                self.vdr_bus_owner = signal.new_owner
                print("dbus2vdr appeared on the bus")
            elif len(signal.new_owner) == 0 and signal.old_owner == self.vdr_bus_owner:
                self.vdr_bus_owner = ""
                print(print("dbus2vdr disappeared from the bus"))


# TODO: do we need this? The disadvantage of a systemd-based status handling is
#       that it won't work if you start the VDR manually for debugging
#
class SystemdVDRStatusHandler(VDRStatusProtocol):
    def __init__(self, config: VDRConfig, loglevel: LoggingEnum = LoggingEnum.INFO):
        self.log = create_log_handler("VDRSystemdStatusHandler", loglevel)
        self.vdr_unit = OrgFreedesktopSystemd1UnitInterface.new_proxy(
            "org.freedesktop.systemd1",
            "/org/freedesktop/systemd1/unit/vdr_2eservice",
            bus=get_bus(config.dbus2vdr_bus),
        )

    async def is_running(self) -> bool:
        print(f"{self.vdr_unit.active_state}, {self.vdr_unit.sub_state=}")
        return (
            self.vdr_unit.sub_state.__str__ == "running"
            and self.vdr_unit.active_state.__str__ == "active"
        )

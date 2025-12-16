from abc import abstractmethod
import asyncio
from collections import deque
from collections.abc import Coroutine
import enum
from functools import partial
import os
from typing import Any, Protocol, Self

from yavdr_frontend.config import (
    BackgroundConfig,
    BackgroundType,
    Config,
    FrontendConfig,
    KeymapConfig,
    LoggingEnum,
    NamedFrontend,
    ShutdownEnum,
    UnitFrontendConfig,
)

from yavdr_frontend.basicfrontend import BasicFrontend, FrontendState

from yavdr_frontend.protocols.frontend_protocols import (
    FrontendProtocol,
    StartupStateEnum,
)
from yavdr_frontend.frontend_manager import system_frontend_factory
from yavdr_frontend.interfaces.systemd_dbus_interface import (
    create_systemd_manager_proxy,
)
from yavdr_frontend.lirc import handle_lirc_connection
from yavdr_frontend.loghandler import create_log_handler

from yavdr_frontend.interfaces.yavdr_frontend_interface import (
    yaVDRFrontendInterface,
    YAVDR_FRONTEND_BUS_NAME,
)
from yavdr_frontend.systemdfrontend import SystemdUnitFrontend
from yavdr_frontend.tools import (
    DISPLAY_RE,
    feh_set_background,
    get_2nd_screen,
    get_bus,
    DelayedRepeatableTask,
)
from yavdr_frontend.shutdown_handler import ShutdownHandlerProtocol, VDRShutdownHandler
from yavdr_frontend.drm_hotlug import (
    check_configured_display,
    load_facts,
    drm_hotplug,
    DRMModel,
)


class VDRState(enum.Enum):
    RUNNING = enum.auto()
    STOPPED = enum.auto()
    CRASHED = enum.auto()


class NeedsControllerProtocol(Protocol):
    config: Config

    @abstractmethod
    async def __async_init__(self) -> Self: ...

    @abstractmethod
    async def on_stopped(self, caller: FrontendProtocol) -> None: ...

    @abstractmethod
    async def start(self) -> tuple[bool, str]: ...


class Controller(NeedsControllerProtocol):
    # primary DISPLAY
    display = ":0"

    keymap: dict[str, KeymapConfig] = {}
    expect_user_activity = False
    poweroff_timer = None
    # TODO: do we need this?
    # shutdown_methods = defaultdict(
    #     lambda: noop
    # )  # frontends can register custom shutdown methods

    shutdown_task: None | DelayedRepeatableTask = None

    def __init__(self, config: "Config"):
        self.log = create_log_handler("Controller", LoggingEnum.DEBUG)
        self.config = config
        # self.current_frontend = None
        self.status_lock = asyncio.Lock()
        self.state: FrontendState = FrontendState.STOP

        self.systemd_manager = create_systemd_manager_proxy(
            bus=get_bus(self.config.main.systemd_bus)
        )

        self.preconfigured_frontends: dict[str, FrontendProtocol] = {
            "dummy": BasicFrontend(self),  # fallback if no frontends are defined
        }

        self.lirc_connection = asyncio.create_task(
            handle_lirc_connection(self.on_keypress, config=self.config)
        )
        self.shutdown_queue: asyncio.Queue[Coroutine[Any, Any, None]] = asyncio.Queue(
            maxsize=1
        )
        match self.config.main.shutdown_manager:
            case ShutdownEnum.VDR:
                self.shutdown_handler: ShutdownHandlerProtocol = VDRShutdownHandler(
                    self
                )
            case _:
                raise ValueError("unsupported shutdown handler configured")


    async def __async_init__(self) -> Self:
        self.log.debug("exporting the Interface to the bus")
        self.interface: yaVDRFrontendInterface = yaVDRFrontendInterface(self)
        self.interface_bus = get_bus(self.config.main.interface_bus)

        for app_name, data in self.config.applications.items():
            try:
                self.preconfigured_frontends[app_name] = await self.get_frontend(data)
            except ValueError as e:
                self.log.warning(e)
                self.preconfigured_frontends[app_name] = BasicFrontend(self)

        primary_frontend = await self.get_frontend(
            NamedFrontend(name=self.config.main.primary_frontend), controller=self
        )
        secondary_frontend = await self.get_frontend(
            NamedFrontend(name=self.config.main.secondary_frontend), controller=self
        )

        self.frontends: deque[FrontendProtocol] = deque(
            (primary_frontend, secondary_frontend),
            maxlen=2,
        )

        await self.interface_bus.request_name_async(YAVDR_FRONTEND_BUS_NAME, 0)
        self.__interface_handler = self.interface.export_to_dbus(
            "/Controller", bus=self.interface_bus
        )
        await self.systemd_manager.subscribe()
        self.display: str | None = os.environ.get(
            "DISPLAY", (await self.get_systemd_env()).get("DISPLAY")
        )
        self.hasX = bool(self.display)
        self.poweroff_task = asyncio.create_task(self.process_shutdown_requests())
        await self.start()

        return self

    def __await__(self):
        return (
            self.__async_init__().__await__()
        )  # see https://stackoverflow.com/a/58976768

    @property
    def current_frontend(self) -> FrontendProtocol | None:
        try:
            return self.frontends[0]
        except IndexError:
            return None

    async def get_frontend(
        self,
        frontend_config: FrontendConfig,
        controller: "Controller|None" = None,
    ) -> FrontendProtocol:
        if controller is None:
            controller = self
        try:
            return await system_frontend_factory(frontend_config, controller)
        except ValueError:
            raise
        except Exception as e:
            self.log.exception(e, exc_info=True)
            raise

    async def on_keypress(self, key_name: str):
        self.log.info(f"on_keypress: try to call {key_name=}")
        self.log.debug(f"{self.keymap.get(key_name)=}")
        self.last_key = key_name

        if self.config.lirc.ignore_KEY_COFFE and key_name == "KEY_COFFEE":
            return
        if keymap_entry := self.keymap.get(key_name):
            self.log.debug(f"execute key action for {key_name}: {keymap_entry=}")
            try:
                func = getattr(self, keymap_entry.action)
                if callable(func):
                    func(keymap_entry.args)
                else:
                    raise ValueError(
                        f"on_keypress: {keymap_entry.action} is not callable"
                    )
            except Exception as err:
                self.log.exception(err)
        elif self.expect_user_activity:
            self.log.debug("we have user activity: attach frontend!")
            await self.start()

    async def get_systemd_unit_names(self) -> list[str]:
        """
        this method returns the existing unit names.
        Don't remove or self.controller.get_frontend called with two arguments won't work!
        """
        result = [
            os.path.basename(unit[0])
            for unit in await self.systemd_manager.list_unit_files()
        ]
        # self.log.debug(f"get_systemd_unit_names(): {result}")
        return result

    async def get_systemd_env(self) -> dict[str, str]:
        """
        return the current systemd_env as a dictionary
        """
        return {
            (t := tuple(item.split("=", maxsplit=1)))[0]: t[1]
            # workaround to avoid a tuple[str, ...] type, we need a tuple[str, str]
            for item in await self.systemd_manager.environment
        }

    async def set_systemd_env(self, env: dict[str, str]):
        """
        update systemd environment variables with key-value pairs from a dict.
        """
        env_list = ["{}={}".format(key, value) for key, value in env.items()]
        await self.systemd_manager.set_environment(env_list)

    async def set_background(self, background_type: BackgroundType):
        config: BackgroundConfig | None = self.config.backgrounds.get(background_type)
        env = os.environ
        env.update(await self.get_systemd_env())
        display = env.get("DISPLAY")
        if display and config:
            self.log.debug(
                f"set_background with options path: {config.path}, fill: {config.fill}"
            )
            feh_set_background(config.path, config.fill, env)

    async def is_active(self) -> bool:
        return await self.frontends[0].frontend_is_running()

    async def start(self) -> tuple[bool, str]:
        if not check_configured_display(os.environ.get("DISPLAY", ":0")):
            self.log.info("no configured display found, don't start yet")
            return False, ("no configured display found")
        self.expect_user_activity = False
        self.clear_poweroff_timer()
        current_frontend = self.current_frontend
        if current_frontend is None:
            self.log.warning("no primary frontend set")
            return False, "Frontend is None"
        await self.set_background(BackgroundType.NORMAL)
        try:
            self.log.debug(f"calling start() for {current_frontend.name=}")
            await current_frontend.start()
        except Exception as e:
            self.log.exception(e)
            return False, repr(e)
        else:
            return True, "OK"
        finally:
            await self.set_frontend_state(FrontendState.SWITCH)

    async def stop(self, extern: bool = True) -> tuple[bool, str]:
        """stop the current frontend"""
        self.log.debug(f"called stop(extern={extern})")
        if extern:
            match self.state:
                case FrontendState.PREPARE_SHUTDOWN:
                    await self.set_background(BackgroundType.PREPARE_SHUTDOWN)
                case FrontendState.QUIT:
                    await self.set_background(BackgroundType.SHUTDOWN)
                case FrontendState.RESTART:
                    await self.set_background(BackgroundType.NORMAL)
                case _:
                    await self.set_background(BackgroundType.DETACHED)
            await self.set_frontend_state(FrontendState.STOP)
            self.expect_user_activity = True

        self.log.debug(f"{self.current_frontend=}")

        if current_frontend := self.current_frontend:
            self.log.debug(f"stop: current frontend is {current_frontend.name}")
            is_running: bool = await current_frontend.frontend_is_running()
            self.log.debug(f"self.frontends[0].is_running: {is_running}")
            if is_running:
                self.log.debug("stop(): current frontend is running")
                result = (True, "OK")
                try:
                    await current_frontend.stop()
                except Exception as e:
                    self.log.exception(e)
                    result = (False, repr(e))
                finally:
                    self.log.debug("stop() got result %s", result)
                    return result
        return (True, "already stopped")

    async def on_stopped(self, caller: FrontendProtocol):
        """this is the callback function after a frontend has been stopped"""
        # TODO: call hooks
        if self.current_frontend and caller.name != self.current_frontend.name:
            self.log.debug(
                f"stop signal for {caller.name} not from current frontend ({self.current_frontend.name}), ignoring ..."
            )
            return
        self.log.debug(
            f"caller {caller.name=} ({caller.fe_type=}) has been stopped - {self.state=}"
        )
        self.interface.frontend_changed.emit((caller.name, "stopped"))
        # self.FrontendChanged(caller.name, "stopped") # TODO: remove
        match self.state:
            case FrontendState.SWITCH:
                await self.switch_on_stopped()
            case FrontendState.RESTART:
                await self.start()
            case FrontendState.STOP:
                return
            case FrontendState.PREPARE_SHUTDOWN | FrontendState.QUIT:
                await self.stop()

    async def switch_on_stopped(self):
        self.frontends.reverse()
        self.log.debug(f"{self.frontends=}")
        await self.start()

    async def set_frontend_state(self, state: FrontendState):
        async with self.status_lock:
            self.log.info(f"Setting state from '{self.state}' to '{state}'")
            self.state = state

    async def toggle(self, extern: bool = True) -> tuple[bool, str]:
        self.log.debug("toggle frontend")
        try:
            if await self.is_active():
                await self.set_frontend_state(FrontendState.STOP)
                await self.stop(extern=extern)
            else:
                await self.start()
        except Exception as e:
            return False, repr(e)
        else:
            return True, "OK"

    async def toggle_noninteractive(
        self,
    ) -> tuple[bool, str]:
        return await self.toggle(extern=False)

    async def switch(self):
        """
        stop the current frontend and set a flag to perform a switch to
        the next frontend
        """
        self.log.debug("called switch()")
        await self.set_frontend_state(FrontendState.SWITCH)
        result = (True, "OK")
        try:
            await self.stop(extern=False)
        except Exception as e:
            self.log.exception(e)
            result = (False, repr(e))
        finally:
            self.log.debug(f"switch(): got result {result}")
            return result

    async def switchto(self, next_frontend: str) -> bool:
        if next_frontend not in self.preconfigured_frontends:
            if not (
                next_frontend_candidate := await self.get_frontend(
                    NamedFrontend(name=next_frontend)
                )
            ):
                return False
            self.preconfigured_frontends[next_frontend] = next_frontend_candidate

        # don't set next frontend if the current and the next_fe are the same
        if self.frontends[0] is self.preconfigured_frontends.get(next_frontend):
            return True
        self.set_next_fe(next_frontend)
        await self.switch()
        return True

    async def switchbetween(self, frontend_a: str, frontend_b: str):
        if all((frontend_a, frontend_b)):
            if self.frontends[0] is self.preconfigured_frontends.get(frontend_a):
                await self.switchto(frontend_b)
            else:
                await self.switchto(frontend_a)
            return True
        else:
            return False

    async def set_next(self, next_frontend: str | None):
        if next_frontend is not None:
            if next_frontend not in self.preconfigured_frontends:
                self.preconfigured_frontends[next_frontend] = await self.get_frontend(
                    NamedFrontend(name=next_frontend)
                )
            # don't set next frontend if the current and the next_fe are the same
            if self.frontends[0] is self.preconfigured_frontends.get(next_frontend):
                return True
            self.set_next_fe(next_frontend)
            return True
        return False

    def set_next_fe(self, fe_type: str, fe_name: str = ""):
        self.log.debug(
            "called set_next_fe with fe_type=%s, fe_name=%s", fe_type, fe_name
        )
        if fe_type in ("unit", "app"):
            # TODO: we are not allowed to subscribe multiple times to
            # the same object, so we need to check if it is already used -
            # this should work for units, we also need to check for apps!
            fe = self.preconfigured_frontends.get(fe_name)
            if not fe:
                try:
                    self.log.debug("Calling SystemdUnitFrontend")
                    self.frontends[1] = SystemdUnitFrontend(
                        config=UnitFrontendConfig(
                            unit_name=fe_name,
                        ),
                        controller=self,
                    )
                except Exception as e:
                    self.log.exception(e)
                    return False
        else:
            fe = self.preconfigured_frontends.get(fe_type)
            if fe:
                self.frontends[1] = fe
                return True
            else:
                self.log.info("no matching frontend found for %s", fe_type)
                # TODO: get next frontend from string
                return False
        return True

    async def set_display(self, display: str) -> bool:
        if DISPLAY_RE.match(display):
            await self.set_systemd_env({"DISPLAY": display})
            second_display = get_2nd_screen(display)
            with open(os.path.expanduser("~/.second_display"), "w") as f:
                f.write("DISPLAY={}".format(second_display))
            return True
        else:
            return False

    async def quit(self) -> bool:
        """prepare for shutdown"""
        await self.set_frontend_state(FrontendState.QUIT)
        if (
            current_frontend := self.current_frontend
        ) and await current_frontend.frontend_is_running():
            success, _msg = await self.stop()
            return success
        return True

    async def delay(self, timeout: float, coro: Coroutine[Any, Any, Any]):
        await asyncio.sleep(timeout)
        await self.shutdown_queue.put(coro)

    async def repeat(self, timeout: float, coro: Coroutine[Any, Any, Any]):
        while True:
            await asyncio.sleep(timeout)
            await self.shutdown_queue.put(coro)

    async def process_shutdown_requests(self):
        while True:
            task = await self.shutdown_queue.get()
            await task
            self.shutdown_queue.task_done()

    def clear_poweroff_timer(self):
        if self.poweroff_timer:
            self.poweroff_timer.stop()
        self.poweroff_timer = None

    async def poweroff(self, instant: bool = False):
        self.expect_user_activity = True
        self.clear_poweroff_timer()
        if not self.current_frontend:
            timeout = 0.0
        elif instant:
            timeout: float = self.current_frontend.instant_shutdown_timeout
        else:
            timeout = self.current_frontend.prepare_shutdown_timeout

        prepare_shutdown = partial(self.prepare_shutdown, instant=instant)

        self.shutdown_task = DelayedRepeatableTask(
            interval=timeout, callback=prepare_shutdown
        )
        return False  # ensure this method isn't called repeatedly

    async def yavdr_compat_poweroff(self):
        """
        switch back to vdr if vdr is not the current frontend otherwise call poweroff
        """

        if (frontend := self.current_frontend) and frontend.fe_type != "vdr":
            await self.switchto("vdr")
        else:
            await self.poweroff()

    # General order of shutdown request:
    # prepare_shutdown -> attempt_shutdown - >
    async def prepare_shutdown(self, instant: bool = False) -> bool:
        timeout = 10 if instant else 60 * 5
        if current_frontend := self.current_frontend:
            stop_on_shutdown = current_frontend.stop_on_shutdown

            if stop_on_shutdown:
                self.log.debug("stop current_frontend: %s", current_frontend.name)
                await self.set_frontend_state(FrontendState.PREPARE_SHUTDOWN)
                await self.stop(extern=True)
            self.poweroff_timer = DelayedRepeatableTask(
                timeout, self.shutdown_handler.attempt_shutdown
            )
        return False  # ensure this method isn't called by a GLib callback again

    async def on_vdr_shutdown_successfull(self) -> bool:
        """
        This method prevents yavdr-frontend from retrying to shut down the system -
        call 'frontend-dbus-send shutdown_successfull' before entering standby
        """

        self.expect_user_activity = False
        self.clear_poweroff_timer()
        await self.set_background(BackgroundType.NORMAL)
        vdr_frontend = self.preconfigured_frontends.get("vdr")
        if vdr_frontend:
            await (
                vdr_frontend.reset()
            )  # TODO: what is the purpose of this otherwise unused variable?
            # vdr_frontend.start = vdr_frontend._startup
        await self.set_frontend_state(FrontendState.RESTART)
        return True

    async def drm_hotplug(self) -> None:
        """This method tries to update the display configuration
        We look for connected outputs for the primary and secondary connector
        if they are found we trigger xrandr to configure them. This can start an additional x-server
        on the respective screen
        """

        data = load_facts()
        try:
            self.log.info(f"{data=}")
            drm_model = DRMModel(**data).drm
        except Exception as e:
            self.log.exception(f"Invalid data: {e}")
        else:
            await drm_hotplug(drm_model)
            await asyncio.sleep(0.5)
            await self.set_background(BackgroundType.NORMAL)
            await self.start()
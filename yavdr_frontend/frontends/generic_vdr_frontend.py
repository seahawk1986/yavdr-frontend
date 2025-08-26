from enum import IntEnum
import logging
import time
from yavdr_frontend.loghandler import create_log_handler
from yavdr_frontend.tools import pasuspend, paresume
from yavdr_frontend.protocols.frontend_protocols import (
    FrontendStatusEnum,
    VDRFrontendProtocol,
)
from yavdr_frontend.interfaces.vdr_plugins import DeTvdrVdrPluginInterface
from functools import partial

from yavdr_frontend.vdr_controller import VDRController, VDRDevice


class GenericVDRFrontend(VDRFrontendProtocol):
    name = "generic"

    def __init__(self, controller: VDRController):
        self.log = create_log_handler(self.name)
        # self.dbus2vdr = controller.vdr
        self.vdr_controller = controller
        self.controller = controller.controller

    async def start(self, options: str | None = None) -> bool:
        if not await self.frontend_is_running():
            try:
                # await self.controller.dbus2vdr.vdr_device.request_primary()
                await self.vdr_controller.dbus2vdr.request_primary_by_name(self.name)
            except Exception as error:
                logging.exception(error)
            else:
                return True
        return False

    async def stop(self) -> bool:
        try:
            idx = await self.vdr_controller.dbus2vdr.vdr_device.get_null_device()
            await self.vdr_controller.dbus2vdr.vdr_device.request_primary(idx)
        except Exception as e:
            logging.exception(e)
            return False
        else:
            await self.vdr_controller.on_stopped(self)
            return True

    async def frontend_is_running(self) -> bool:
        current_primary_device = VDRDevice(
            *await self.vdr_controller.dbus2vdr.vdr_device.get_primary()
        )
        if current_primary_device.name:
            state = True
        else:
            state = False
        logging.debug(
            f"{self.name}: is_running: {state} with {current_primary_device=}"
        )
        return state

    async def started(self) -> None:
        raise NotImplementedError

    async def stopped(self) -> None:
        raise NotImplementedError

    async def status_message(self, status: str) -> None:
        self.log.info(f"{await self.frontend_is_running()=}")


class SofthdBaseClass(GenericVDRFrontend):
    name = "changeme"
    fe_type = "VDR Module"
    states = {910: "attached", 911: "suspended", 912: "detached"}

    def __init__(self, controller: VDRController):
        self.log = logging.getLogger(self.name)
        self.dbus2vdr = controller.dbus2vdr
        self._svdrpcmd = partial(self.dbus2vdr.svdrpcommand, plugin_name=self.name)
        self.vdrcontroller = controller
        self.controller = self.vdrcontroller.controller
        self.shddevice_config = self.vdrcontroller.controller.config.vdr.frontends[
            self.name
        ]
        self.use_pasuspend = self.shddevice_config.use_pasuspend
        self.log.debug("use_pasuspend is %s", self.use_pasuspend)

    async def __async_init__(self):
        self.plugin_proxy = DeTvdrVdrPluginInterface.new_proxy(
            "de.tvdr.vdr",
            f"/Plugins/{self.name}",
            bus=self.vdrcontroller.dbus2vdr.vdr_bus,
        )
        return self

    async def svdrpcmd(
        self, action: str, options: str = ""
    ) -> tuple[int, str] | tuple[None, None]:
        """
        Relevant description from SVDRP HELP:
        DETA
            Detach plugin.

            The plugin will be detached from the audio, video and DVB
            devices.  Other programs or plugins can use them now.

        RAISE
            raise window to the front
        """
        if await self.vdrcontroller.controller.vdr_status.is_running():
            try:
                return await self._svdrpcmd(cmd=action, option=options)
            except Exception as e:
                self.log.warning("DBus communication failed!")
                self.log.debug(e)
        return None, None

    async def atta(self, options: str | None = None):
        """
        ATTA <-d display> <-a audio> <-p pass>
            Attach plugin.

            Attach the plugin to audio, video and DVB devices. Use:
            -d display      display of x11 server (fe. :0.0)
            -a audio        audio device (fe. alsa: hw:0,0 oss: /dev/dsp)
            -p pass         audio device for pass-through (hw:0,1 or /dev/dsp1)
        """

        async def env2template(cmd_options: dict[str, str]):
            env = await self.vdrcontroller.controller.get_systemd_env()
            for variable, template in cmd_options.items():
                value = env.get(variable)
                if value:
                    yield template.format(value)

        cmd_options = {
            "DISPLAY": "-d {}",
            "ALSA_DEVICE": "-a {}",
            "ALSA_AC3_DEVICE": "-p {}",
        }

        result = await self.change_state(
            action="atta",
            options=options
            if options
            else " ".join([e async for e in env2template(cmd_options)]),
            expected_state="attached",
            logmsg="attached",
        )
        return result

    def deta(self):
        """detach softhddevice style frontend"""
        return self.change_state(
            action="deta", options="", expected_state="detached", logmsg="detached"
        )

    async def change_state(
        self,
        action: str,
        options: str = "",
        expected_state: str | None = None,
        logmsg: str = "contacted",
    ):
        """change softhddevice style frontend to the given state"""
        code, result = await self.svdrpcmd(action, options)
        self.log.debug(
            f'change_state with command {action} and options "{options}" to {expected_state}'
        )
        if code == 900 and await self.check_state() == expected_state:
            self.log.debug("%s successfully %s", self.name, logmsg)
            self.active = True
            return True
        else:
            self.log.debug("%s could not be %s: %s %s", self.name, logmsg, code, result)
        return False

    async def start(self, options: str | None | list[str] = None) -> bool:
        """suspend pulseaudio if configured and attach softhdcuvid"""
        if self.use_pasuspend:
            pasuspend()
        if options:
            if isinstance(options, str):
                pass
            elif isinstance(options, list):  # pyright: ignore[reportUnnecessaryIsInstance]
                options = " ".join(options)
        else:
            options = ""
        self.log.debug(f"{await self.status()=}, {await self.resume()=}")
        if not await self.frontend_is_running() and not await self.resume():
            result = await self.atta(options)
        else:
            result = False
        await self.make_primary()
        return result

    async def stop(self, options: str = "") -> bool:
        """
        perform necessary actions to detach softhdcuvid,
        resume pulseaudio if configured
        """
        try:
            await self.resume()
            if await self.frontend_is_running():
                r = await self.deta()
                if self.use_pasuspend:
                    paresume()
                await self.vdrcontroller.on_stopped(self)
                return r
        except TypeError:
            pass
        except Exception as e:
            self.log.debug(e)
        return False

    async def resume(self) -> bool:
        """
        if softhdcuvid is suspended, attach it
        returns True if the frontend was attached, otherwise False
        """
        if await self.check_state() == "suspended":
            result = await self.change_state(
                "resu", expected_state="attached", logmsg="resumed"
            )
            self.log.debug(f"resuming frontend: {result}")
            return result
        else:
            # self.log.debug("frontend does not need to resume")
            return False

    class SofthddeviceStatusEnum(IntEnum):
        NOT_SUSPENDED = 910
        SUSPEND_NORMAL = 911
        SUSPEND_DETACHED = 912

    async def check_state(self):
        code, _msg = await self._svdrpcmd(cmd="stat")
        self.log.debug(f"check_state(): got status code: {code}")
        if code in self.states:
            return self.states[code]

    async def status(self) -> FrontendStatusEnum:
        if await self.check_state() == "attached":
            self.log.debug(f"status: {self.name} is attached")
            return FrontendStatusEnum.ACTIVE
        else:
            self.log.debug(f"status: {self.name} is detached")
            return FrontendStatusEnum.INACTIVE

    async def frontend_is_running(self) -> bool:
        return await self.status() == FrontendStatusEnum.ACTIVE

    async def make_primary(self):
        ts_start = time.time()
        while True:
            # device_index and device_number are integers,
            # hasDecoder and isPrimary are boolean,
            # and device_name is a string
            device = VDRDevice(*(await self.dbus2vdr.vdr_device.get_primary()))

            self.log.debug(
                (
                    f"current PrimaryDevice is {device.name} "
                    f"(Index: {device.idx}, Number: {device.number}, "
                    f"hasDecoder: {device.has_decoder}, isPrimary: {device.is_primary})"
                )
            )

            if not device.name.startswith(self.name) or device.name in (
                "nulldevice",
                "vnsiserver",
            ):
                self.log.debug(f"make {self.name} the primary device")
                # self._svdrpcmd('PRIM')
                try:
                    response = await self.dbus2vdr.request_primary_by_name(self.name)
                    self.log.debug(f"set primary response: {response}")
                except ValueError:
                    self.log.error(
                        f"can't set primary device: no device with name '{self.name}'"
                    )
                time.sleep(0.25)
            else:
                self.log.debug(f"{self.name} is the primary device")
                self.log.debug(
                    "needed %0.3f s to switch primary device", (time.time() - ts_start)
                )
                break

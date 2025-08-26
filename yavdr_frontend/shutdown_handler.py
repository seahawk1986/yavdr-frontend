from abc import abstractmethod
import asyncio
from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from yavdr_frontend.controller import Controller
from yavdr_frontend.interfaces.vdr_remote import DeTvdrVdrRemoteInterface
from yavdr_frontend.interfaces.vdr_shutdown import DeTvdrVdrShutdownInterface
from yavdr_frontend.loghandler import create_log_handler
from yavdr_frontend.tools import get_bus


class ShutdownHandlerProtocol(Protocol):
    shutdown_wanted = asyncio.Condition()

    async def shutdown_loop(
        self,
    ):
        while True:
            async with self.shutdown_wanted:
                await self.shutdown_wanted.wait()
                await self.attempt_shutdown()

    @abstractmethod
    async def attempt_shutdown(self) -> bool: ...


class VDRShutdownHandler(ShutdownHandlerProtocol):
    def __init__(self, controller: "Controller"):
        self.log = create_log_handler(
            "VDRShutdownHandler",
        )
        self.controller = controller
        self.vdr_bus = get_bus(controller.config.vdr.dbus2vdr_bus)
        self.vdr_shutdown = DeTvdrVdrShutdownInterface.new_proxy(
            "de.tvdr.vdr", "/Shutdown", bus=self.vdr_bus
        )
        self.vdr_remote = DeTvdrVdrRemoteInterface.new_proxy(
            "de.tvdr.vdr", "/Remote", bus=self.vdr_bus
        )

    # async def shutdown_loop(
    #     self,
    # ):
    #     while True:
    #         async with self.shutdown_wanted:
    #             await self.shutdown_wanted.wait()
    #             await self.attempt_shutdown()

    async def attempt_shutdown(self) -> bool:
        """this is the actual implementation of the shutdown method"""
        if (
            self.controller.current_frontend is None
        ):  # TODO: use a better way to determine if the VDR is ready and running
            self.log.info("VDR not running, trying again")
            return True
        # startup = self.controller.config.vdr.attach_on_startup # TODO: what is this for?
        try:
            code, msg, *_ = await self.vdr_shutdown.confirm_shutdown(ignoreuser=True)
            self.log.info(f"attempt_shutdown: {msg}")
            if code == 250:
                await self.vdr_remote.enable()
                await self.vdr_remote.hit_key("Power")
                await self.vdr_remote.disable()
        except Exception as e:
            self.log.exception(e)
        finally:
            return True

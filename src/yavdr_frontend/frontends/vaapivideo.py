import asyncio
from enum import IntEnum
import subprocess
from types import CoroutineType
from typing import Any

from yavdr_frontend.frontends.generic_vdr_frontend import (
    SofthdBaseClass,
    SofthddeviceStatusEnum,
)
from yavdr_frontend.tools import pwresume, pwsuspend


class VaapivideoStatusEnum(IntEnum):
    ATTACHED = 900
    SUSPEND_DETACHED = 550


class Vaapivideo(SofthdBaseClass):
    name = "vaapivideo"

    async def change_state(
        self,
        action: str,
        options: str = "",
        expected_state: SofthddeviceStatusEnum | None = None,
        logmsg: str = "contacted",
    ):
        """change softhddevice style frontend to the given state"""
        code, result = await self.svdrpcmd(action, options)
        self.log.debug(
            f'change_state with command {action} and options "{options}" to {expected_state}'
        )
        await asyncio.sleep(0.5)
        state = await self.check_state()
        self.log.debug(f"{code=}, {result=}, current state: {state}")
        if code == 900 and state == expected_state:
            self.log.debug("%s successfully %s", self.name, logmsg)
            self.active = True
            return True
        else:
            self.log.debug("%s could not be %s: %s %s", self.name, logmsg, code, result)
        return False

    async def check_state(self) -> None | SofthddeviceStatusEnum:
        code, _msg = await self._svdrpcmd(cmd="stat")
        self.log.debug(f"check_state(): got status code: {code}")
        try:
            if code not in VaapivideoStatusEnum:
                raise ValueError("SVDRP request failed")

            result = (
                SofthddeviceStatusEnum.ATTACHED
                if code == VaapivideoStatusEnum.ATTACHED
                else SofthddeviceStatusEnum.SUSPEND_DETACHED
            )
            self.log.debug(f"state was {result}")
            return result
        except Exception as e:
            self.log.exception(f"unknown status {code=}: {e}")

    async def start(self, options: str | None | list[str] = None) -> bool:
        """suspend pipewire if configured and attach softhdcuvid"""
        if self.use_pwsuspend:
            pwsuspend()
        options = ""
        self.log.debug(f"{await self.status()=}, {await self.resume()=}")
        if not await self.frontend_is_running() and not await self.resume():
            result = await self.atta(options)
        else:
            result = False
        await self.make_primary()
        return result

    async def atta(self, options: str | None = None) -> bool:
        """
        ATTA
            Attach plugin.
        """

        # TODO: switch to VT9 (VDR)
        r = subprocess.run(["sudo", "/usr/bin/chvt", "9"], check=True)
        if r.returncode == 0:
            result = await self.change_state(
                action="atta",
                options="",
                expected_state=SofthddeviceStatusEnum.ATTACHED,
                logmsg="attached",
            )

            return result
        return False

    def deta(self) -> CoroutineType[Any, Any, bool]:
        """detach softhddevice style frontend

        DETA
            Detach plugin.

            The plugin will be detached from the audio, video and DVB
            devices.  Other programs or plugins can use them now.

        """
        return self.change_state(
            action="deta",
            options="",
            expected_state=SofthddeviceStatusEnum.SUSPEND_DETACHED,
            logmsg="detached",
        )

    async def stop(self, options: str = "") -> bool:
        """
        perform necessary actions to detach softhdcuvid,
        resume pipewire if configured
        """
        try:
            await self.resume()
            if await self.frontend_is_running():
                r = await self.deta()
                self.log.debug(f"deta returned: {r}")
                if r:
                    r = subprocess.run(["sudo", "/usr/bin/chvt", "7"], check=True)
                    await self.vdrcontroller.on_stopped(self)
                    if self.use_pwsuspend:
                        await pwresume()
                    return r.returncode == 0
        except TypeError:
            pass
        except Exception as e:
            self.log.debug(e)
        return False

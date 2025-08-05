from __future__ import annotations

from typing import List, Tuple

from sdbus import (
    DbusInterfaceCommonAsync,
    DbusUnprivilegedFlag,
    dbus_method_async,
)


# class DeTvdrVdrPluginInterface(
#     DbusInterfaceCommonAsync,
#     interface_name="de.tvdr.vdr.plugin",
# ):
#     @dbus_method_async(
#         result_signature="a(ss)",
#     )
#     async def list(
#         self,
#     ) -> List[Tuple[str, str]]:
#         raise NotImplementedError


class DeTvdrVdrPluginmanagerInterface(
    DbusInterfaceCommonAsync,
    interface_name="de.tvdr.vdr.pluginmanager",
):
    @dbus_method_async(
        result_signature="a(ss)",
    )
    async def list(
        self,
    ) -> List[Tuple[str, str]]:
        raise NotImplementedError

class DeTvdrVdrPluginInterface(
    DbusInterfaceCommonAsync,
    interface_name="de.tvdr.vdr.plugin",
):
    @dbus_method_async(
        input_signature="ss",
        result_signature="is",
        flags=DbusUnprivilegedFlag,
        method_name="SVDRPCommand",
        result_args_names=('replycode', 'replymessage'),
    )
    async def svdrpcommand(
        self,
        command: str,
        option: str,
    ) -> tuple[int, str]:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="ss",
        result_signature="b",
        flags=DbusUnprivilegedFlag,
        result_args_names=('handled',),
    )
    async def service(
        self,
        id: str,
        data: str,
    ) -> bool:
        raise NotImplementedError

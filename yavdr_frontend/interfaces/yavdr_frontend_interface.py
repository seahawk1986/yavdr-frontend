import asyncio
from sdbus import (
    DbusInterfaceCommonAsync,
    dbus_method_async,
    dbus_signal_async,
    dbus_property_async,
)
import sdbus

from typing import TYPE_CHECKING

from yavdr_frontend.config import Config
from yavdr_frontend.lirc import handle_lirc_connection

if TYPE_CHECKING:
    from yavdr_frontend.controller import Controller

YAVDR_FRONTEND_BUS_NAME = "de.yavdr.frontend"
YAVDR_FRONTEND_INTERFACE_NAME = "de.yavdr.frontend.Controller"


# <node>
#     <interface name='de.yavdr.frontend.Controller'>
class yaVDRFrontendInterface(
    DbusInterfaceCommonAsync, interface_name=YAVDR_FRONTEND_INTERFACE_NAME
):
    def __init__(self, controller: "Controller"):
        self.controller = controller
        super().__init__()
        self.controller.interface = self

    @dbus_method_async(flags=sdbus.DbusUnprivilegedFlag)
    async def start(self):
        await self.controller.start()

    @dbus_method_async(
        result_signature="bs", flags=sdbus.DbusUnprivilegedFlag, method_name="start"
    )
    async def _start(self):
        print("Warning: Deprecated method, use 'Start' instead")
        await self.controller.start()
        return True, "ok"
        #         <method name='start'>
        #             <arg type='b' name='response' direction='out'/>
        #             <arg type='s' name='reason' direction='out'/>
        #         </method>

    @dbus_method_async(result_signature="bs", flags=sdbus.DbusUnprivilegedFlag)
    async def stop(self) -> tuple[bool, str]:
        return await self.controller.stop()

    @dbus_method_async(
        result_signature="bs", flags=sdbus.DbusUnprivilegedFlag, method_name="stop"
    )
    async def _stop(self) -> tuple[bool, str]:
        print("Warning: Deprecated method, use 'Stop' instead")
        return await self.stop()
        #         <method name='stop'>
        #             <arg type='b' name='a' direction='out'/>
        #             <arg type='s' name='reason' direction='out'/>
        #         </method>

    @dbus_method_async(result_signature="bs", flags=sdbus.DbusUnprivilegedFlag)
    async def toggle(self) -> tuple[bool, str]:
        return await self.controller.toggle()

    @dbus_method_async(
        result_signature="bs", flags=sdbus.DbusUnprivilegedFlag, method_name="toggle"
    )
    async def _toggle(self) -> tuple[bool, str]:
        print("Warning: Deprecated method, use 'Toggle' instead")
        return await self.toggle()
        #         <method name='toggle'>
        #             <arg type='b' name='response' direction='out'/>
        #             <arg type='s' name='reason' direction='out'/>
        #         </method>

    @dbus_method_async(result_signature="bs", flags=sdbus.DbusUnprivilegedFlag)
    async def toggle_noninteractive(self) -> tuple[bool, str]:
        return await self.controller.toggle_noninteractive()
        #         <method name='toggle_noninteractive'>
        #             <arg type='b' name='response' direction='out'/>
        #             <arg type='s' name='reason' direction='out'/>
        #         </method>

    @dbus_method_async(result_signature="bs", flags=sdbus.DbusUnprivilegedFlag)
    async def switch(self) -> tuple[bool, str]:
        return await self.controller.switch()
        #         <method name='switch'>
        #             <arg type='b' name='response' direction='out'/>
        #             <arg type='s' name='reason' direction='out'/>
        #         </method>

    @dbus_method_async(
        input_signature="s", result_signature="b", flags=sdbus.DbusUnprivilegedFlag
    )
    async def switchto(self, next_frontend: str) -> bool:
        return await self.controller.switchto(next_frontend)

    @dbus_method_async(
        input_signature="s",
        result_signature="b",
        method_name="switchto",
        flags=sdbus.DbusUnprivilegedFlag,
    )
    async def _switchto(self, next_frontend: str) -> bool:
        print("Warning: Deprecated method, use 'SwitchTo' instead")
        return await self.switchto(next_frontend)
        #         <method name='switchto'>
        #             <arg type='s' name='frontend' direction='in'/>
        #             <arg type='b' name='response' direction='out'/>
        #         </method>

    @dbus_method_async(
        input_signature="ss", result_signature="b", flags=sdbus.DbusUnprivilegedFlag
    )
    async def switchbetween(self, frontend_a: str, frontend_b: str) -> bool:
        return await self.controller.switchbetween(frontend_a, frontend_b)
        #         <method name='switchbetween'>
        #             <arg type='s' name='frontendA' direction='in'/>
        #             <arg type='s' name='frontendB' direction='in'/>
        #             <arg type='b' name='response' direction='out'/>
        #         </method>

    @dbus_method_async(
        input_signature="s", result_signature="b", flags=sdbus.DbusUnprivilegedFlag
    )
    async def set_next(self, next_frontend: str) -> bool:
        return await self.controller.set_next(next_frontend)
        #         <method name='setNext'>
        #             <arg type='s' name='frontend' direction='in'/>
        #             <arg type='b' name='response' direction='out'/>
        #         </method>

    @dbus_method_async(input_signature="s", flags=sdbus.DbusUnprivilegedFlag)
    async def set_display(self, display: str) -> bool:
        await self.controller.set_display(display=display)
        return True  # TODO: do we need this or is it better to change the signature?
        #         <method name='setDisplay'>
        #             <arg type='s' name='frontend' direction='in'/>
        #             <arg type='b' name='response' direction='out'/>
        #         </method>

    @dbus_method_async(
        input_signature="s", result_signature="bs", flags=sdbus.DbusUnprivilegedFlag
    )
    async def start_desktop(self, application: str) -> tuple[bool, str]:
        # TODO: implement this
        return await self.controller.switchto(application), "Ok"

        #         <method name='start_desktop'>
        #             <arg type='s' name='frontend' direction='in'/>
        #             <arg type='b' name='response' direction='out'/>
        #             <arg type='s' name='reason' direction='out'/>
        #         </method>

    # TODO: create a method to start a .desktop file without involving the frontend

    @dbus_method_async(
        input_signature="sss", result_signature="b", flags=sdbus.DbusUnprivilegedFlag
    )
    async def set_next_fe(self, type_: str, name: str, class_: str) -> bool:
        return self.controller.set_next_fe(type_, name)
        #         <method name='set_next_fe'>
        #             <arg type='s' name='type' direction='in' />
        #             <arg type='s' name='name' direction='in' />
        #             <arg type='s' name='class' direction='in' />
        #             <arg type='b' name='response' direction='out'/>
        #         </method>

    @dbus_method_async(result_signature="b", flags=sdbus.DbusUnprivilegedFlag)
    async def quit(self) -> bool:
        return await self.controller.quit()
        #         <method name='quit'>
        #             <arg type='b' name='response' direction='out'/>
        #         </method>

    @dbus_method_async(result_signature="b", flags=sdbus.DbusUnprivilegedFlag)
    async def shutdown_successfull(self):
        return await self.controller.shutdown_successfull()
        #         <method name='shutdown_successfull'>
        #             <arg type='b' name='response' direction='out'/>
        #         </method>

    @dbus_signal_async(signal_signature="ss")
    def frontend_changed(self) -> tuple[str, str]:
        raise NotImplementedError
        #         <signal name="FrontendChanged">
        #             <arg direction="out" type="s" name="frontend"/>
        #             <arg direction="out" type="s" name="status"/>
        #         </signal>
        #     </interface>
        # </node>

    @dbus_property_async(property_signature="s")
    def current_frontend(self) -> str:
        return (
            self.controller.current_frontend.name
            if self.controller.current_frontend
            else ""
        )


async def export_frontend(config: Config, controller: "Controller"):
    print("open dbus connection ...")
    # Open a dbus connection
    interface_bus = (
        sdbus.sd_bus_open_system()
        if config.main.interface_bus == "SystemBus"
        else sdbus.sd_bus_open_user()
    )
    print("request a name on the bus")
    # Request a name on the interface bus
    await interface_bus.request_name_async(YAVDR_FRONTEND_INTERFACE_NAME, 0)

    print("export the Interface to the bus")

    interface = yaVDRFrontendInterface(controller)
    interface.export_to_dbus("/", interface_bus)

    async with asyncio.TaskGroup():
        _lirc_connection = asyncio.create_task(
            handle_lirc_connection(on_keypress, config=config)
        )
    print("Taskgroup returned")


async def on_keypress(cmd: str):
    print(f"got lirc {cmd=}")


# if __name__ == "___main__":
#     logging.basicConfig(level=logging.DEBUG)
#     config = load_yaml()
#     try:
#         asyncio.run(export_frontend(config,))
#     except KeyboardInterrupt:
#         pass

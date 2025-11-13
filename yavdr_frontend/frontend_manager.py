from pathlib import Path
import subprocess
from yavdr_frontend.basicfrontend import FrontendProtocol
from yavdr_frontend.config import (
    DesktopAppFrontendConfig,
    FrontendConfig,
    ModuleFrontendConfig,
    NamedFrontend,
    UnitFrontendConfig,
)
from yavdr_frontend.interfaces.systemd_dbus_interface import (
    create_systemd_manager_proxy,
)

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from yavdr_frontend.controller import Controller
    from yavdr_frontend.vdr_controller import VDRController
from yavdr_frontend.systemdfrontend import SystemdUnitFrontend
from yavdr_frontend.tools import get_DesktopAppInfo, get_bus, get_object_from_module

known_frontends: dict[FrontendConfig, FrontendProtocol] = {}


def systemd_escape_app(app_name: str):
    result = subprocess.run(
        ["systemd-escape", "--template=app@.service", app_name],
        universal_newlines=True,
        capture_output=True,
    )
    # print(result)
    return result.stdout.strip()


async def system_frontend_factory(
    config: FrontendConfig, controller: "Controller | VDRController"
) -> FrontendProtocol:
    global known_frontends
    if frontend := known_frontends.get(config):
        return frontend
    # NOTE: we need to await the SystemUnitFrontend initialization to get the async operations done
    if isinstance(config, UnitFrontendConfig):
        unit_name = config.unit_name
        frontend = await SystemdUnitFrontend(
            UnitFrontendConfig(
                unit_name=unit_name,
                use_pasuspend=config.use_pasuspend,
                bus=config.bus,
            ),
            controller=controller,
            fe_type="unit",
        )
    elif isinstance(config, DesktopAppFrontendConfig):
        # unit_name = f"app@{config.app_name}.service"  # TODO: do we need to escape this?
        unit_name = systemd_escape_app(app_name=config.app_name)
        frontend = await SystemdUnitFrontend(
            UnitFrontendConfig(
                unit_name=unit_name,
                use_pasuspend=config.use_pasuspend,
                bus=config.bus,
            ),
            controller=controller,
            fe_type="app",
        )
    elif isinstance(config, ModuleFrontendConfig):
        frontend_class = get_object_from_module(config.module_name, config.class_name)
        frontend = await frontend_class(controller=controller).__async_init__()

    elif isinstance(config, NamedFrontend):  # type: ignore
        # check preconfigured frontends
        if cfg := controller.config.applications.get(config.name):
            # We got a frontend config and have to check it, so let's call this method recursively
            return await system_frontend_factory(cfg, controller)
        else:
            # we only got a name to work with
            controller.log.debug(f"looking for Frontend with name '{config.name}'")

            # let's check if we got the name of a .desktop file
            if config.name.endswith(".desktop"):
                try:
                    app = get_DesktopAppInfo(config.name)
                except (TypeError, ValueError) as e:
                    controller.log.exception(e, exc_info=True)
                else:
                    if id := app.get_id():
                        return await system_frontend_factory(
                            config=DesktopAppFrontendConfig(
                                app_name=id,
                                use_pasuspend=False,
                                bus=controller.config.main.systemd_bus,
                            ),
                            controller=controller,
                        )
            # is ist a systemd service?
            elif config.name.endswith(".service"):
                return await SystemdUnitFrontend(
                    config=UnitFrontendConfig(
                        unit_name=config.name,
                        use_pasuspend=config.use_pasuspend,
                        bus=config.bus,
                    ),
                    controller=controller,
                    fe_type="unit",
                )
            else:
                # TODO: we need to guess - is it a systend unit?
                systemd_manager_proxy = create_systemd_manager_proxy(
                    bus=get_bus(controller.config.main.systemd_bus)
                )
                units = await systemd_manager_proxy.list_unit_files_by_patterns(
                    [], [(unit_name := f"{config.name}.service")]
                )
                for unit_path, _t in units:
                    p = Path(unit_path)
                    if p.name == unit_name:
                        return await SystemdUnitFrontend(
                            config=UnitFrontendConfig(
                                unit_name=unit_name,
                                use_pasuspend=False,
                                bus=controller.config.main.systemd_bus,
                            ),
                            controller=controller,
                            fe_type="unit",
                        )
                #

            raise ValueError(f"unknown frontend name for {config=}")

        # elif (
        #     name := f"{config.name}.service"
        #     if not config.name.endswith(".service")
        #     else config.name
        # ) in await controller.get_systemd_unit_names():
        #     return await SystemdUnitFrontend(
        #         config=UnitFrontendConfig(
        #             unit_name=name, use_pasuspend=config.use_pasuspend, bus=config.bus
        #         ),
        #         controller=controller,
        #         fe_type="unit",
        #     )
        # else:
        #     return await SystemdUnitFrontend(
        #         config=UnitFrontendConfig(
        #             unit_name=systemd_escape_app(app_name=config.name),
        #             use_pasuspend=config.use_pasuspend,
        #             bus=config.bus,
        #         ),
        #         controller=controller,
        #         fe_type="app",
        #     )

    if not frontend:
        raise ValueError("Unknown Frontend")
    known_frontends[config] = frontend
    return frontend

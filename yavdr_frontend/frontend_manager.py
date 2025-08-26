import subprocess
from yavdr_frontend.basicfrontend import FrontendProtocol
from yavdr_frontend.config import (
    DesktopAppFrontendConfig,
    FrontendConfig,
    ModuleFrontendConfig,
    NamedFrontend,
    UnitFrontendConfig,
)
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from yavdr_frontend.controller import Controller
    from yavdr_frontend.vdr_controller import VDRController
from yavdr_frontend.systemdfrontend import SystemdUnitFrontend
from yavdr_frontend.tools import get_object_from_module

known_frontends: dict[str, FrontendProtocol] = {}


def systemd_escape_app(app_name: str):
    result = subprocess.run(
        ["systemd-escape", "--template=app@.service", app_name],
        universal_newlines=True,
    )
    return result.stdout.strip()


async def system_frontend_factory(
    config: FrontendConfig, controller: "Controller | VDRController"
) -> FrontendProtocol:
    global known_frontends
    frontend = None
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
        unit_name = f"app@{config.app_name}.service"  # TODO: do we need to escape this?
        # unit_name = systemd_escape_app(app_name=config.app_name)
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
        if config.name in controller.config.applications:
            if cfg := controller.config.applications.get(config.name):
                # We got a frontend config and have to check it, so let's call this method recursively
                return await system_frontend_factory(cfg, controller)
        elif (
            name := f"{config.name}.service"
            if not config.name.endswith(".service")
            else config.name
        ) in await controller.get_systemd_unit_names():
            return await SystemdUnitFrontend(
                config=UnitFrontendConfig(
                    unit_name=name, use_pasuspend=config.use_pasuspend, bus=config.bus
                ),
                controller=controller,
                fe_type="unit",
            )
        else:
            return await SystemdUnitFrontend(
                config=UnitFrontendConfig(
                    unit_name=f"app@{config.name}.service",
                    use_pasuspend=config.use_pasuspend,
                    bus=config.bus,
                ),
                controller=controller,
                fe_type="app",
            )

    if not frontend:
        raise ValueError("Unknown Frontend")
    return frontend

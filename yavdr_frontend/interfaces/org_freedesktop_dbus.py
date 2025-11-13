from __future__ import annotations

from typing import Any

from sdbus import (
    DbusInterfaceCommonAsync,
    DbusPropertyConstFlag,
    DbusUnprivilegedFlag,
    dbus_method_async,
    dbus_property_async,
    dbus_signal_async,
)


class OrgFreedesktopDBusInterface(
    DbusInterfaceCommonAsync,
    interface_name="org.freedesktop.DBus",
):
    @dbus_method_async(
        result_signature="s",
        flags=DbusUnprivilegedFlag,
    )
    async def hello(
        self,
    ) -> str:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="su",
        result_signature="u",
        flags=DbusUnprivilegedFlag,
    )
    async def request_name(
        self,
        arg_0: str,
        arg_1: int,
    ) -> int:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="s",
        result_signature="u",
        flags=DbusUnprivilegedFlag,
    )
    async def release_name(
        self,
        arg_0: str,
    ) -> int:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="su",
        result_signature="u",
        flags=DbusUnprivilegedFlag,
    )
    async def start_service_by_name(
        self,
        arg_0: str,
        arg_1: int,
    ) -> int:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="a{ss}",
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def update_activation_environment(
        self,
        arg_0: dict[str, str],
    ) -> None:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="s",
        result_signature="b",
        flags=DbusUnprivilegedFlag,
    )
    async def name_has_owner(
        self,
        arg_0: str,
    ) -> bool:
        raise NotImplementedError

    @dbus_method_async(
        result_signature="as",
        flags=DbusUnprivilegedFlag,
    )
    async def list_names(
        self,
    ) -> list[str]:
        raise NotImplementedError

    @dbus_method_async(
        result_signature="as",
        flags=DbusUnprivilegedFlag,
    )
    async def list_activatable_names(
        self,
    ) -> list[str]:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="s",
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def add_match(
        self,
        arg_0: str,
    ) -> None:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="s",
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def remove_match(
        self,
        arg_0: str,
    ) -> None:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="s",
        result_signature="s",
        flags=DbusUnprivilegedFlag,
    )
    async def get_name_owner(
        self,
        arg_0: str,
    ) -> str:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="s",
        result_signature="as",
        flags=DbusUnprivilegedFlag,
    )
    async def list_queued_owners(
        self,
        arg_0: str,
    ) -> list[str]:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="s",
        result_signature="u",
        flags=DbusUnprivilegedFlag,
    )
    async def get_connection_unix_user(
        self,
        arg_0: str,
    ) -> int:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="s",
        result_signature="u",
        flags=DbusUnprivilegedFlag,
        method_name="GetConnectionUnixProcessID",
    )
    async def get_connection_unix_process_id(
        self,
        arg_0: str,
    ) -> int:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="s",
        result_signature="ay",
        flags=DbusUnprivilegedFlag,
    )
    async def get_adt_audit_session_data(
        self,
        arg_0: str,
    ) -> bytes:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="s",
        result_signature="ay",
        flags=DbusUnprivilegedFlag,
        method_name="GetConnectionSELinuxSecurityContext",
    )
    async def get_connection_selinux_security_context(
        self,
        arg_0: str,
    ) -> bytes:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="s",
        result_signature="s",
        flags=DbusUnprivilegedFlag,
    )
    async def get_connection_app_armor_security_context(
        self,
        arg_0: str,
    ) -> str:
        raise NotImplementedError

    @dbus_method_async(
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def reload_config(
        self,
    ) -> None:
        raise NotImplementedError

    @dbus_method_async(
        result_signature="s",
        flags=DbusUnprivilegedFlag,
    )
    async def get_id(
        self,
    ) -> str:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="s",
        result_signature="a{sv}",
        flags=DbusUnprivilegedFlag,
    )
    async def get_connection_credentials(
        self,
        arg_0: str,
    ) -> dict[str, tuple[str, Any]]:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="as",
        flags=DbusPropertyConstFlag,
    )
    def features(self) -> list[str]:
        raise NotImplementedError

    @dbus_property_async(
        property_signature="as",
        flags=DbusPropertyConstFlag,
    )
    def interfaces(self) -> list[str]:
        raise NotImplementedError

    @dbus_signal_async(
        signal_signature="sss",
    )
    def name_owner_changed(self) -> tuple[str, str, str]:
        raise NotImplementedError

    @dbus_signal_async(
        signal_signature="s",
    )
    def name_lost(self) -> str:
        raise NotImplementedError

    @dbus_signal_async(
        signal_signature="s",
    )
    def name_acquired(self) -> str:
        raise NotImplementedError

    @dbus_signal_async(
        signal_args_names=(),
    )
    def activatable_services_changed(self) -> None:
        raise NotImplementedError


class OrgFreedesktopDBusMonitoringInterface(
    DbusInterfaceCommonAsync,
    interface_name="org.freedesktop.DBus.Monitoring",
):
    @dbus_method_async(
        input_signature="asu",
        flags=DbusUnprivilegedFlag,
        result_args_names=(),
    )
    async def become_monitor(
        self,
        arg_0: list[str],
        arg_1: int,
    ) -> None:
        raise NotImplementedError


class OrgFreedesktopDBusDebugStatsInterface(
    DbusInterfaceCommonAsync,
    interface_name="org.freedesktop.DBus.Debug.Stats",
):
    @dbus_method_async(
        result_signature="a{sv}",
        flags=DbusUnprivilegedFlag,
    )
    async def get_stats(
        self,
    ) -> dict[str, tuple[str, Any]]:
        raise NotImplementedError

    @dbus_method_async(
        input_signature="s",
        result_signature="a{sv}",
        flags=DbusUnprivilegedFlag,
    )
    async def get_connection_stats(
        self,
        arg_0: str,
    ) -> dict[str, tuple[str, Any]]:
        raise NotImplementedError

    @dbus_method_async(
        result_signature="a{sas}",
        flags=DbusUnprivilegedFlag,
    )
    async def get_all_match_rules(
        self,
    ) -> dict[str, list[str]]:
        raise NotImplementedError


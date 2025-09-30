"""Template content for the Panorama Config Pump plugin."""

from __future__ import annotations

from netbox.plugins import PluginTemplateExtension

from netbox_panorama_configpump_plugin.device_config_sync_status.models import (
    DeviceConfigSyncStatus,
)


# pylint: disable=abstract-method
class ConnectionButtons(PluginTemplateExtension):
    """Add custom buttons to Connection object views."""

    models = ["netbox_panorama_configpump_plugin.connection"]

    def buttons(self) -> str:
        """
        Add Pull All Configuration and Push All Configuration buttons
        to the object view.
        """

        buttons = [
            {
                "text": "Pull all configuration",
                "uri": "connection_pull_all_configs",
                "pk": self.context["object"].pk,
                "icon": "mdi-sync",
            },
            {
                "text": "Push all configuration",
                "uri": "connection_push_all_configs",
                "pk": self.context["object"].pk,
                "icon": "mdi-upload",
            },
        ]

        return self.render(
            "netbox_panorama_configpump_plugin/connection_buttons.html",
            {
                "label": "Panorama Actions",
                "color": "btn-purple",
                "buttons": buttons,
            },
        )


# pylint: disable=abstract-method
class DevicePanoramaConnectionButton(PluginTemplateExtension):
    """Add View Panorama Connection button to Device object views."""

    models = ["dcim.device"]

    def buttons(self) -> str:
        """
        Add View Panorama Connection button if device has associated
        DeviceConfigSyncStatus.
        """

        user = self.context["request"].user
        if not user.has_perm("netbox_panorama_configpump_plugin.view_connection"):
            return ""

        device_id = self.context["object"].pk
        device_config_sync_status = DeviceConfigSyncStatus.objects.filter(
            device_id=device_id
        ).first()
        if not device_config_sync_status:
            return ""
        connection = device_config_sync_status.connection

        buttons = [
            {
                "text": "Pull configuration",
                "uri": "deviceconfigsyncstatus_pull_config",
                "pk": device_config_sync_status.pk,
                "icon": "mdi-sync",
            },
            {
                "text": "Push configuration",
                "uri": "deviceconfigsyncstatus_push_config",
                "pk": device_config_sync_status.pk,
                "icon": "mdi-upload",
            },
            {
                "text": "View Connection",
                "uri": "connection",
                "pk": connection.pk,
                "icon": "mdi-connection",
            },
        ]

        return self.render(
            "netbox_panorama_configpump_plugin/device_panorama_connection_button.html",
            {
                "label": "Panorama Actions",
                "color": "btn-purple",
                "buttons": buttons,
            },
        )


template_extensions = [ConnectionButtons, DevicePanoramaConnectionButton]

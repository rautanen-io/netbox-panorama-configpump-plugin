"""Models for PanoramaConfigPump plugin."""

from __future__ import annotations

from netbox_panorama_configpump_plugin.connection.models import Connection
from netbox_panorama_configpump_plugin.connection_template.models import (
    ConnectionTemplate,
)
from netbox_panorama_configpump_plugin.device_config_sync_status.models import (
    DeviceConfigSyncStatus,
)

# pylint: disable=line-too-long
__all__ = ("ConnectionTemplate", "Connection", "DeviceConfigSyncStatus")

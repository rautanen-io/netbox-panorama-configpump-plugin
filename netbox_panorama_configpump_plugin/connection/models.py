"""Panorama connection model."""

# pylint: disable=too-many-ancestors

from __future__ import annotations

from dcim.models import Device
from django.db import models
from django.db.models import QuerySet
from netbox.models import PrimaryModel

from netbox_panorama_configpump_plugin.connection_template.models import (
    ConnectionTemplate,
)


class Connection(PrimaryModel):
    """Maps NetBox devices to a Panorama template."""

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique name for this connection.",
    )

    connection_template = models.ForeignKey(
        ConnectionTemplate,
        on_delete=models.PROTECT,
        related_name="connections",
        help_text="Connection template this connection targets.",
    )

    # Devices are managed through DeviceConfigSyncStatus objects
    # Use the devices property to access them
    @property
    def devices(self) -> QuerySet[Device]:
        """Get all devices associated with this connection."""
        return Device.objects.filter(
            device_config_sync_statuses__connection=self
        ).distinct()

    # pylint: disable=no-member
    def add_device(self, device: Device) -> None:
        """Add a device to this connection."""
        self.device_config_sync_statuses.get_or_create(device=device)

    def remove_device(self, device: Device) -> None:
        """Remove a device from this connection."""
        self.device_config_sync_statuses.filter(device=device).delete()

    def clear_devices(self) -> None:
        """Remove all devices from this connection."""
        self.device_config_sync_statuses.all().delete()

    @property
    def config_render_ok(self) -> bool:
        """Check if the configuration renders properly."""
        return all(
            device_config_sync_status.config_render_ok
            for device_config_sync_status in self.device_config_sync_statuses.all()
        )

    # pylint: disable=too-few-public-methods
    class Meta:
        """Meta options for PanoramaConnection."""

        ordering = ("name",)

    def __str__(self) -> str:
        return str(self.name)

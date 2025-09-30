"""Device config sync status models."""

from __future__ import annotations

from typing import Any

from core.models import Job
from dcim.models import Device
from django.db import models
from netbox.models import JobsMixin, NetBoxModel

from netbox_panorama_configpump_plugin.connection.models import Connection
from netbox_panorama_configpump_plugin.device_config_sync_status.panorama import (
    PanoramaMixin,
)
from netbox_panorama_configpump_plugin.utils.helpers import (
    calculate_diff,
    normalize_xml,
)


# pylint: disable=too-many-ancestors
class DeviceConfigSyncStatus(PanoramaMixin, JobsMixin, NetBoxModel):
    """Documents the config sync status between a Device in Netbox and Panorama."""

    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name="device_config_sync_statuses",
        help_text="Device this configuration belongs to.",
    )

    connection = models.ForeignKey(
        Connection,
        on_delete=models.CASCADE,
        related_name="device_config_sync_statuses",
        help_text="Panorama connection context for this configuration.",
    )

    panorama_configuration = models.TextField(
        null=True,
        blank=True,
        default="",
        help_text="XML format configuration pulled from Panorama.",
    )

    lines_added = models.PositiveIntegerField(
        null=True,
        blank=True,
        default=0,
        help_text="Line additions compared to NetBox rendered configuration.",
    )

    lines_removed = models.PositiveIntegerField(
        null=True,
        blank=True,
        default=0,
        help_text="Line removals compared to NetBox rendered configuration.",
    )

    lines_changed = models.PositiveIntegerField(
        null=True,
        blank=True,
        default=0,
        help_text="Line changes compared to NetBox rendered configuration.",
    )

    last_pull = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when configuration was last pulled from Panorama.",
    )

    last_push = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when configuration was last pushed to Panorama.",
    )

    config_render_ok = models.BooleanField(
        default=False,
        help_text="Whether NetBox rendered configuration is valid XML.",
    )

    sync_job = models.ForeignKey(
        Job,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="device_config_sync_statuses",
        help_text="Last synchronization job for this configuration.",
    )

    # pylint: disable=no-member
    def get_rendered_configuration(self) -> str:
        """Get the rendered configuration."""

        config_template = self.device.get_config_template()
        if not config_template:
            return ""

        context_data = self.device.get_config_context()

        # pylint: disable=protected-access
        context_data.update({self.device._meta.model_name: self.device})

        return config_template.render(context=context_data)

    def update_diffs(self) -> None:
        """Update the diffs."""

        rendered_configuration = self.get_rendered_configuration()
        panorama_configuration = self.panorama_configuration

        diff = calculate_diff(panorama_configuration, rendered_configuration)
        self.lines_added = diff["added"]
        self.lines_removed = diff["removed"]
        self.lines_changed = diff["changed"]

    def update_config_render_ok(self) -> None:
        """Update the config_render_ok field."""
        _, rendered_configuration_valid = normalize_xml(
            self.get_rendered_configuration()
        )
        self.config_render_ok = rendered_configuration_valid

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Override save to automatically update diffs and config render status."""
        # Update diffs and config render status before saving
        self.update_diffs()
        self.update_config_render_ok()
        super().save(*args, **kwargs)

    # pylint: disable=too-few-public-methods
    class Meta:
        """Meta options for DeviceConfigSyncStatus."""

        ordering = ("device", "connection")
        constraints = [
            models.UniqueConstraint(
                fields=["device"],
                name="uniq_configsyncstatus_device",
            )
        ]
        indexes = [
            models.Index(fields=["last_pull"], name="idx_configsyncstatus_last_pull"),
        ]

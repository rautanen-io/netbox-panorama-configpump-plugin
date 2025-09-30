"""
Signals for the NetBox Panorama ConfigPump Plugin. If the Device, Platform, DeviceRole,
or ConfigTemplate is saved, the device config sync statuses will be updated.

Saving the above models might change the rendered configuration, so we need to update
the device config sync statuses, i.e. calculate the diffs and update the
config_render_ok field.
"""

from __future__ import annotations

from typing import Any

from dcim.models import Device, DeviceRole, Interface, Platform
from dcim.models.devices import post_save
from django.db.models import QuerySet
from django.db.models.signals import post_delete
from django.dispatch import receiver
from extras.models import ConfigTemplate

from netbox_panorama_configpump_plugin.device_config_sync_status.models import (
    DeviceConfigSyncStatus,
)


def _update_device_config_sync_statuses(
    device_config_sync_statuses: QuerySet[DeviceConfigSyncStatus],
) -> None:
    for device_config_sync_status in device_config_sync_statuses:
        # config_render_ok and diffs are updated by save
        device_config_sync_status.save(
            update_fields=[
                "config_render_ok",
                "lines_added",
                "lines_removed",
                "lines_changed",
            ]
        )


# pylint: disable=unused-argument
@receiver(post_save, sender=ConfigTemplate)
def update_device_config_sync_status_on_config_template_change(
    instance: ConfigTemplate, **kwargs: Any
) -> None:
    """
    Update the device config sync statuses for a config template.
    """

    device_config_sync_statuses = DeviceConfigSyncStatus.objects.filter(
        device__in=Device.objects.filter(platform__in=instance.platforms.all())
    )
    if not device_config_sync_statuses:
        return
    _update_device_config_sync_statuses(device_config_sync_statuses)


# pylint: disable=unused-argument
@receiver(post_save, sender=Device)
def update_device_config_sync_status_on_device_change(
    instance: Device, **kwargs: Any
) -> None:
    """
    Update the device config sync statuses for a device.
    """

    device_config_sync_statuses = DeviceConfigSyncStatus.objects.filter(device=instance)
    if not device_config_sync_statuses:
        return

    _update_device_config_sync_statuses(device_config_sync_statuses)


# pylint: disable=unused-argument
@receiver(post_save, sender=Interface)
@receiver(post_delete, sender=Interface)
def update_device_config_sync_status_on_interface_change(
    instance: Interface, **kwargs: Any
) -> None:
    """
    Update the device config sync statuses when an interface is created,
    updated, or deleted.
    """

    device_config_sync_statuses = DeviceConfigSyncStatus.objects.filter(
        device=instance.device
    )

    if not device_config_sync_statuses:
        return

    _update_device_config_sync_statuses(device_config_sync_statuses)


# pylint: disable=unused-argument
@receiver(post_save, sender=Platform)
def update_device_config_sync_status_on_platform_change(
    instance: Platform, **kwargs: Any
) -> None:
    """
    Update the device config sync statuses for a platform.
    """

    device_config_sync_statuses = DeviceConfigSyncStatus.objects.filter(
        device__platform=instance
    )
    if not device_config_sync_statuses:
        return

    _update_device_config_sync_statuses(device_config_sync_statuses)


# pylint: disable=unused-argument
@receiver(post_save, sender=DeviceRole)
def update_device_config_sync_status_on_device_role_change(
    instance: DeviceRole, **kwargs: Any
) -> None:
    """
    Update the device config sync statuses for a device role.
    """

    device_config_sync_statuses = DeviceConfigSyncStatus.objects.filter(
        device__in=Device.objects.filter(role=instance)
    )
    if not device_config_sync_statuses:
        return

    _update_device_config_sync_statuses(device_config_sync_statuses)

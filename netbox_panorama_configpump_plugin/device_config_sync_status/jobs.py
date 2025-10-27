"""Jobs for device config sync status."""

from __future__ import annotations

import datetime
from typing import Any

from django.utils import timezone
from netbox.jobs import JobRunner

from netbox_panorama_configpump_plugin.device_config_sync_status.models import (
    DeviceConfigSyncStatus,
)
from netbox_panorama_configpump_plugin.device_config_sync_status.panorama import (
    PanoramaLogger,
    Status,
)

# pylint: disable=line-too-long


def _get_device_config_sync_status(
    panorama_logger: PanoramaLogger, **kwargs: Any
) -> DeviceConfigSyncStatus | None:
    """Get device config sync status."""

    device_config_sync_status_id = kwargs.get("device_config_sync_status_id")
    if not device_config_sync_status_id:
        panorama_logger.log(
            Status.FAILURE,
            None,
            "device_config_sync_status_id",
            "device_config_sync_status_id is required",
        )
        return

    device_config_sync_status = DeviceConfigSyncStatus.objects.filter(
        id=device_config_sync_status_id
    ).first()
    if not device_config_sync_status:
        panorama_logger.log(
            Status.FAILURE,
            None,
            "device_config_sync_status_id",
            "device_config_sync_status_id is required",
        )
        return

    return device_config_sync_status


def _update_device_config_sync_status(
    device_config_sync_status: DeviceConfigSyncStatus,
    push_time: datetime.datetime | None = None,
    pull_time: datetime.datetime | None = None,
) -> None:
    """Update device config sync status."""

    update_fields = {}
    if push_time:
        update_fields["last_push"] = push_time

    if pull_time:
        update_fields["last_pull"] = pull_time

    if update_fields:
        DeviceConfigSyncStatus.objects.filter(pk=device_config_sync_status.pk).update(
            **update_fields
        )


class PushAndPullDeviceConfigJobRunner(JobRunner):
    """Job runner for pushing and pulling configuration to Panorama."""

    # pylint: disable=too-few-public-methods
    class Meta:
        """Meta options for PushAndPullDeviceConfigJobRunner."""

        name = "Push and Pull Configuration to Panorama"

    def run(self, *args: Any, **kwargs: Any) -> None:

        panorama_logger = PanoramaLogger()

        device_config_sync_status = _get_device_config_sync_status(
            panorama_logger, **kwargs
        )
        if not device_config_sync_status:
            self.job.data = panorama_logger.to_sanitized_dict()
            raise ValueError("Device config sync status not found")

        push_ok = device_config_sync_status.push(panorama_logger)
        self.job.data = panorama_logger.to_sanitized_dict()

        if not push_ok:
            raise ValueError(
                "Tried to push configuration to Panorama but there were issues. Check the job data for more details."
            )

        _update_device_config_sync_status(
            device_config_sync_status,
            push_time=timezone.now(),
            pull_time=timezone.now(),
        )


class PullDeviceConfigJobRunner(JobRunner):
    """Job runner for pulling configuration from Panorama."""

    # pylint: disable=too-few-public-methods
    class Meta:
        """Meta options for PullDeviceConfigJobRunner."""

        name = "Pull Configuration from Panorama"

    def run(self, *args: Any, **kwargs: Any) -> None:

        panorama_logger = PanoramaLogger()

        device_config_sync_status = _get_device_config_sync_status(
            panorama_logger, **kwargs
        )
        if not device_config_sync_status:
            self.job.data = panorama_logger.to_sanitized_dict()
            raise ValueError("Device config sync status not found")

        pull_ok = device_config_sync_status.pull(panorama_logger)
        self.job.data = panorama_logger.to_sanitized_dict()

        if not pull_ok:
            raise ValueError(
                "Tried to pull configuration from Panorama but there were issues. Check the job data for more details."
            )

        _update_device_config_sync_status(
            device_config_sync_status, pull_time=timezone.now()
        )

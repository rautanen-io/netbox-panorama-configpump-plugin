"""Jobs for device config sync status."""

from __future__ import annotations

import datetime
from typing import Any

from core.models import Job
from django.utils import timezone
from netbox.jobs import JobRunner

from netbox_panorama_configpump_plugin.device_config_sync_status.models import (
    DeviceConfigSyncStatus,
)
from netbox_panorama_configpump_plugin.utils.helpers import (
    sanitize_error_message,
    sanitize_nested_values,
)

# pylint: disable=line-too-long


def _get_device_config_sync_status(**kwargs: Any) -> DeviceConfigSyncStatus | None:
    """Get device config sync status."""

    device_config_sync_status_id = kwargs.get("device_config_sync_status_id")
    if not device_config_sync_status_id:
        raise ValueError("device_config_sync_status_id is required")

    device_config_sync_status = DeviceConfigSyncStatus.objects.filter(
        id=device_config_sync_status_id
    ).first()
    if not device_config_sync_status:
        raise ValueError("device_config_sync_status_id is required")

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


def _set_response_stats(
    job: Job,
    device_config_sync_status: DeviceConfigSyncStatus,
    push_response_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Get response stats."""

    response_stats = {
        "config_pull_length": (
            len(device_config_sync_status.panorama_configuration)
            if device_config_sync_status.panorama_configuration
            else 0
        ),
        "timestamp": timezone.now().isoformat(),
    }
    if push_response_stats:
        response_stats["config_push_http_status"] = push_response_stats[
            "config_push_http_status"
        ]
        response_stats["config_load_responses"] = sanitize_nested_values(
            push_response_stats["config_load_responses"]
        )
    job.data = response_stats


def _find_issues_in_config_load_responses(
    config_load_responses: list[dict[str, Any]],
) -> bool:
    """Find issues in config load responses."""

    for config_load_response in config_load_responses:
        if "CDATA" in config_load_response["response"]:
            return True
    return False


class PushAndPullDeviceConfigJobRunner(JobRunner):
    """Job runner for pushing and pulling configuration to Panorama."""

    # pylint: disable=too-few-public-methods
    class Meta:
        """Meta options for PushAndPullDeviceConfigJobRunner."""

        name = "Push and Pull Configuration to Panorama"

    def run(self, *args: Any, **kwargs: Any) -> None:

        try:
            device_config_sync_status = _get_device_config_sync_status(**kwargs)

            push_response = device_config_sync_status.push()
            if push_response["config_push_http_status"] != 200:
                raise ValueError("Push configuration returned non-200 status code")
            push_time = timezone.now()

            device_config_sync_status.pull()
            pull_time = timezone.now()

            _update_device_config_sync_status(
                device_config_sync_status,
                push_time=push_time,
                pull_time=pull_time,
            )

        except ValueError as value_error:
            sanitized_error_message = sanitize_error_message(str(value_error))
            self.job.error = sanitized_error_message
            raise ValueError(
                f"Configuration push and pull failed: {sanitized_error_message}"
            ) from value_error

        _set_response_stats(
            self.job,
            device_config_sync_status,
            push_response_stats=push_response,
        )

        has_issues = _find_issues_in_config_load_responses(
            push_response["config_load_responses"],
        )
        if has_issues:
            raise ValueError(
                "Configuration was loaded but there were issues. Check the job data for more details."
            )


class PullDeviceConfigJobRunner(JobRunner):
    """Job runner for pulling configuration from Panorama."""

    # pylint: disable=too-few-public-methods
    class Meta:
        """Meta options for PullDeviceConfigJobRunner."""

        name = "Pull Configuration from Panorama"

    def run(self, *args: Any, **kwargs: Any) -> None:
        try:
            device_config_sync_status = _get_device_config_sync_status(**kwargs)

            device_config_sync_status.pull()

            _update_device_config_sync_status(
                device_config_sync_status, pull_time=timezone.now()
            )

            _set_response_stats(self.job, device_config_sync_status)

        except ValueError as value_error:
            sanitized_error_message = sanitize_error_message(str(value_error))
            self.job.error = sanitized_error_message

            error_stats = {
                "response_length": 0,
                "has_response": False,
                "timestamp": timezone.now().isoformat(),
                "status": "error",
                "error_message": sanitized_error_message,
            }
            self.job.data = error_stats
            raise ValueError(
                f"Configuration pull failed: {sanitized_error_message}"
            ) from value_error

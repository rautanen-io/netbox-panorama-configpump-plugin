"""Device config sync status forms."""

from __future__ import annotations

from core.models import Job
from dcim.models import Device
from netbox.forms import NetBoxModelFilterSetForm, NetBoxModelForm
from utilities.forms.fields import DynamicModelChoiceField, TagFilterField

from netbox_panorama_configpump_plugin.connection.models import Connection
from netbox_panorama_configpump_plugin.device_config_sync_status.filtersets import (
    DeviceConfigSyncStatusFilterSet,
)
from netbox_panorama_configpump_plugin.device_config_sync_status.models import (
    DeviceConfigSyncStatus,
)


# pylint: disable=too-many-ancestors
class DeviceConfigSyncStatusForm(NetBoxModelForm):
    """Form for DeviceConfigSyncStatus model."""

    device: DynamicModelChoiceField = DynamicModelChoiceField(
        queryset=Device.objects.all(),
        required=True,
        label="Device",
        help_text="Device this configuration belongs to.",
    )
    connection: DynamicModelChoiceField = DynamicModelChoiceField(
        queryset=Connection.objects.all(),
        required=True,
        label="Connection",
        help_text="Connection context for this configuration.",
    )
    sync_job: DynamicModelChoiceField = DynamicModelChoiceField(
        queryset=Job.objects.all(),
        required=False,
        label="Sync Job",
        help_text="Last synchronization job for this configuration.",
    )

    # pylint: disable=too-few-public-methods
    class Meta:
        """Meta options for DeviceConfigSyncStatusForm."""

        model = DeviceConfigSyncStatus
        fields = (
            "device",
            "connection",
            "panorama_configuration",
            "lines_added",
            "lines_removed",
            "lines_changed",
            "last_pull",
            "last_push",
            "config_render_ok",
            "sync_job",
            "tags",
        )


class DeviceConfigSyncStatusFilterForm(NetBoxModelFilterSetForm):
    """Filter form for DeviceConfigSyncStatus model."""

    model = DeviceConfigSyncStatus
    filterset = DeviceConfigSyncStatusFilterSet

    device_id: DynamicModelChoiceField = DynamicModelChoiceField(
        queryset=Device.objects.all(),
        required=False,
        label="Devices",
    )
    connection_id: DynamicModelChoiceField = DynamicModelChoiceField(
        queryset=Connection.objects.all(),
        required=False,
        label="Connections",
    )
    sync_job_id: DynamicModelChoiceField = DynamicModelChoiceField(
        queryset=Job.objects.all(),
        required=False,
        label="Sync Jobs",
    )

    tag = TagFilterField(model)

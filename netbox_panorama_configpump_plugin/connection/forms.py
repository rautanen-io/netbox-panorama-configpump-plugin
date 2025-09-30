"""Forms for the connection app."""

from __future__ import annotations

from typing import Any

from dcim.models import Device
from django.forms import ValidationError
from netbox.forms import NetBoxModelFilterSetForm, NetBoxModelForm
from utilities.forms.fields import (
    CommentField,
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
    TagFilterField,
)
from utilities.forms.widgets import APISelectMultiple

from netbox_panorama_configpump_plugin.connection.filtersets import ConnectionFilterSet
from netbox_panorama_configpump_plugin.connection.models import Connection
from netbox_panorama_configpump_plugin.connection_template.models import (
    ConnectionTemplate,
)
from netbox_panorama_configpump_plugin.device_config_sync_status.models import (
    DeviceConfigSyncStatus,
)


# pylint: disable=too-many-ancestors
class ConnectionForm(NetBoxModelForm):
    """Form for the connection model."""

    devices = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        widget=APISelectMultiple(api_url="/api/plugins/panorama-configpump/devices/"),
        query_params={
            "connection_template_id": "$connection_template",
        },
        required=False,
        label="Devices",
        help_text=(
            "Select devices to include in this connection. Only devices with the "
            "same platform as the selected connection template are shown."
        ),
    )

    comments = CommentField()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the form with device data."""
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["devices"].initial = list(
                self.instance.devices.values_list("pk", flat=True)
            )

    def clean_devices(self) -> list[Device]:
        """Clean the devices field."""
        devices = self.cleaned_data.get("devices", [])
        taken_devices = []

        for device in devices:
            existing_sync_status = DeviceConfigSyncStatus.objects.filter(
                device=device
            ).first()
            if (
                existing_sync_status
                and existing_sync_status.connection != self.instance
            ):
                taken_devices.append(
                    f"Device {device} is already associated with connection "
                    f"'{existing_sync_status.connection.name}'"
                )

        if taken_devices:
            raise ValidationError(taken_devices)

        return devices

    # pylint: disable=arguments-differ
    def save(self, commit: bool = True) -> Connection:
        """Save the form and manage device relationships."""
        super().save(commit=commit)

        if commit:
            selected_devices = self.cleaned_data.get("devices", [])
            self.instance.clear_devices()
            for device in selected_devices:
                self.instance.add_device(device)

        return self.instance

    # pylint: disable=too-few-public-methods
    class Meta:
        """Meta class for the connection form."""

        model = Connection
        fields = (
            "name",
            "connection_template",
            "devices",
            "description",
            "tags",
            "comments",
        )


class ConnectionFilterForm(NetBoxModelFilterSetForm):
    """Filter form for the connection model."""

    model = Connection
    filterset = ConnectionFilterSet

    connection_template_id = DynamicModelChoiceField(
        queryset=ConnectionTemplate.objects.all(),
        required=False,
        label="Connection Template",
    )

    tag = TagFilterField(model)

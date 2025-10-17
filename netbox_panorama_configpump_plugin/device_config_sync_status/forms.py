"""Device config sync status forms."""

from __future__ import annotations

from core.models import Job
from dcim.models import Device
from django.forms import BooleanField, CharField, Textarea, ValidationError
from django.utils.safestring import mark_safe
from lxml import etree
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
    # pylint: disable=line-too-long
    deduce_xpaths = BooleanField(
        label="Deduce XPaths",
        required=False,
        help_text=(
            "Automatically deduces which parts of the Panorama configuration to update. "
            "Updates are applied under the following XPath: "
            "<ul>"
            "<li><i>devices/entry[@name='localhost.localdomain']/template/entry[@name='< template name >']</i></li>"
            "<li><i>devices/entry[@name='localhost.localdomain']/device-group/entry[@name='< device-group name >']</i></li>"
            "</ul>"
            "The template and device-group names are inferred from the ConfigTemplate associated with the Device."
        ),
    )
    # pylint: disable=line-too-long
    manual_xpath_entries = CharField(
        label="Manual XPath Entries",
        required=False,
        widget=Textarea,
        help_text=mark_safe(
            'List of <a href="https://en.wikipedia.org/wiki/XPath" target="_blank" rel="noopener noreferrer">XPath</a> '
            "expressions to manually override the automatic deduction. "
            "This applies only if 'Deduce XPaths' is unchecked. "
            "Enter one XPath per line."
        ),
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
            "deduce_xpaths",
            "manual_xpath_entries",
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

    def clean_manual_xpath_entries(self):
        """Clean xpath entries. Light sanity check for manual XPath entries."""

        data = self.cleaned_data.get("manual_xpath_entries", "").strip()

        if not data or data == "[]":
            return []

        entries = [line.strip() for line in data.splitlines() if line.strip()]

        # pylint: disable=c-extension-no-member
        for xpath in entries:
            if not xpath.startswith("/config/"):
                raise ValidationError(
                    f"XPath entry must start with '/config/': {xpath}"
                )
            try:
                etree.XPath(xpath)
            except etree.XPathSyntaxError as e:
                raise ValidationError(f"Invalid XPath '{xpath}': {e}") from e

        return entries

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        entries = getattr(self.instance, "manual_xpath_entries", None)

        if isinstance(entries, list) and entries:
            self.initial["manual_xpath_entries"] = "\n".join(entries)
        else:
            self.initial["manual_xpath_entries"] = ""


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

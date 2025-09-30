"""Device config sync status tables."""

from __future__ import annotations

import django_tables2 as tables
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString
from netbox.tables import NetBoxTable, columns
from netbox.tables.columns import ActionsItem

from netbox_panorama_configpump_plugin.device_config_sync_status.models import (
    DeviceConfigSyncStatus,
)
from netbox_panorama_configpump_plugin.device_config_sync_status.template_code import (
    DEVICE_CONFIG_SYNC_STATUS_ACTIONS,
    SYNC_JOB_STATUS_BADGE,
)


class DeviceConfigSyncStatusActionsColumn(columns.ActionsColumn):
    """Custom ActionsColumn with additional actions for DeviceConfigSyncStatus."""

    actions = {
        "": ActionsItem("View", "eye", "view", "secondary"),
        "delete": ActionsItem("Detach device", "close-circle", "delete", "danger"),
        "changelog": ActionsItem("Changelog", "history", "changelog", "secondary"),
    }


class DeviceConfigSyncStatusTable(NetBoxTable):
    """Table for DeviceConfigSyncStatus model."""

    device = tables.Column(linkify=True)
    connection = tables.Column(linkify=True)
    lines_added = tables.Column(verbose_name="Lines Added")
    lines_removed = tables.Column(verbose_name="Lines Removed")
    lines_changed = tables.Column(verbose_name="Lines Changed")
    last_pull = tables.DateTimeColumn(format="Y-m-d H:i:s", verbose_name="Last Pull")
    last_push = tables.DateTimeColumn(format="Y-m-d H:i:s", verbose_name="Last Push")
    config_render_ok = columns.BooleanColumn(verbose_name="Config Render OK")
    sync_job = tables.TemplateColumn(
        template_code=SYNC_JOB_STATUS_BADGE, verbose_name="Sync Job Status"
    )
    tags = columns.TagColumn(
        url_name="plugins:netbox_panorama_configpump_plugin:deviceconfigsyncstatus_list"
    )
    actions = DeviceConfigSyncStatusActionsColumn(
        actions=("", "delete", "changelog"),
        split_actions=True,
        extra_buttons=DEVICE_CONFIG_SYNC_STATUS_ACTIONS,
    )

    def render_lines_added(self, value: int | None) -> int | SafeString:
        """Render lines added as green badge."""
        if value is None or value == 0:
            return 0
        return format_html('<span class="badge text-bg-success">{}</span>', value)

    def render_lines_removed(self, value: int | None) -> int | SafeString:
        """Render lines removed as red badge."""
        if value is None or value == 0:
            return 0
        return format_html('<span class="badge text-bg-danger">{}</span>', value)

    def render_lines_changed(self, value: int | None) -> int | SafeString:
        """Render lines changed as blue badge."""
        if value is None or value == 0:
            return 0
        return format_html('<span class="badge text-bg-info">{}</span>', value)

    def render_device(self, record: DeviceConfigSyncStatus) -> str | SafeString:
        """Render device column with link to panorama-diff tab."""
        if not hasattr(record, "device") or not record.device:
            return ""

        config_diff_url = reverse(
            "dcim:device_panorama_diff",
            kwargs={"pk": record.device.pk},
        )

        return format_html(
            '<a href="{}">{}</a>',
            config_diff_url,
            record.device,
        )

    # pylint: disable=too-few-public-methods
    class Meta(NetBoxTable.Meta):
        """Meta options for DeviceConfigSyncStatusTable."""

        model = DeviceConfigSyncStatus
        fields = (
            "id",
            "pk",
            "device",
            "connection",
            "lines_added",
            "lines_removed",
            "lines_changed",
            "last_pull",
            "last_push",
            "config_render_ok",
            "sync_job",
            "tags",
            "actions",
        )
        default_columns = (
            "device",
            "lines_added",
            "lines_removed",
            "lines_changed",
            "last_pull",
            "last_push",
            "config_render_ok",
            "sync_job",
            "actions",
        )

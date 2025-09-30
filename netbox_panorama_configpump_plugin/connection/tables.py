"""Django models import for tables."""

from __future__ import annotations

import django_tables2 as tables
from django.utils.html import format_html
from django.utils.safestring import SafeString
from netbox.tables import NetBoxTable, columns

from netbox_panorama_configpump_plugin.connection.models import Connection
from netbox_panorama_configpump_plugin.connection.template_code import DEVICES_TEMPLATE


class ConnectionTable(NetBoxTable):
    """Table for the connection model."""

    name = tables.Column(linkify=True)
    connection_template = tables.Column(linkify=True)
    devices = tables.TemplateColumn(
        template_code=DEVICES_TEMPLATE,
        orderable=False,
        verbose_name="Devices",
    )
    description = tables.Column()
    comments = tables.Column()
    tags = columns.TagColumn(
        url_name="plugins:netbox_panorama_configpump_plugin:connection_list"
    )

    device_count = columns.TemplateColumn(
        template_code="""{{ record.devices.count }}""",
        orderable=False,
        verbose_name="Device Count",
    )
    lines_added = tables.Column(
        accessor="total_lines_added",
        verbose_name="Lines Added",
        orderable=False,
    )
    lines_removed = tables.Column(
        accessor="total_lines_removed",
        verbose_name="Lines Removed",
        orderable=False,
    )
    lines_changed = tables.Column(
        accessor="total_lines_changed",
        verbose_name="Lines Changed",
        orderable=False,
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

    # pylint: disable=too-few-public-methods
    class Meta(NetBoxTable.Meta):
        """Meta options."""

        model = Connection
        fields = (
            "pk",
            "id",
            "name",
            "connection_template",
            "devices",
            "device_count",
            "lines_added",
            "lines_removed",
            "lines_changed",
            "description",
            "comments",
            "tags",
            "created",
            "last_updated",
        )
        default_columns = (
            "pk",
            "name",
            "device_count",
            "lines_added",
            "lines_removed",
            "lines_changed",
            "description",
            "connection_template",
        )

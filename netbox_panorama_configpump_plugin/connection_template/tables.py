"""Django models import for tables."""

from __future__ import annotations

import django_tables2 as tables
from netbox.tables import NetBoxTable, columns

from .models import ConnectionTemplate


class ConnectionTemplateTable(NetBoxTable):
    """Table for ConnectionTemplate model."""

    name = tables.Column(linkify=True)
    panorama_url = tables.URLColumn()
    token_key = tables.Column()
    file_name_prefix = tables.Column()
    platforms = columns.ManyToManyColumn(linkify_item=True)
    connections = columns.ManyToManyColumn(
        linkify_item=True, verbose_name="Connection Names"
    )
    connections_count = columns.LinkedCountColumn(
        accessor="connections__count",
        viewname="plugins:netbox_panorama_configpump_plugin:connectiontemplate_list",
        url_params={"template_id": "pk"},
        verbose_name="Connection Count",
    )
    request_timeout = tables.Column()
    description = tables.Column()
    comments = tables.Column()
    tags = columns.TagColumn(
        url_name="plugins:netbox_panorama_configpump_plugin:connectiontemplate_list"
    )

    # pylint: disable=too-few-public-methods
    class Meta(NetBoxTable.Meta):
        """Meta options."""

        model = ConnectionTemplate
        fields = (
            "pk",
            "id",
            "name",
            "panorama_url",
            "token_key",
            "file_name_prefix",
            "platforms",
            "connections",
            "connections_count",
            "request_timeout",
            "description",
            "comments",
            "tags",
            "created",
            "last_updated",
        )
        default_columns = (
            "pk",
            "name",
            "panorama_url",
            "file_name_prefix",
            "connections_count",
            "request_timeout",
            "description",
        )

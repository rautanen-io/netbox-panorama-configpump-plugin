"""Connection filtersets."""

from __future__ import annotations

from django.db import models
from django.db.models import QuerySet
from netbox.filtersets import NetBoxModelFilterSet
from utilities import filters

from netbox_panorama_configpump_plugin.connection.models import Connection


class ConnectionFilterSet(NetBoxModelFilterSet):
    """Connection filterset."""

    connection_template_id = filters.MultiValueNumberFilter(
        field_name="connection_template__id",
        label="Connection template (ID)",
    )
    connection_template = filters.MultiValueCharFilter(
        field_name="connection_template__name",
        label="Connection template (name)",
    )

    # pylint: disable=too-few-public-methods
    class Meta:
        """Meta options for ConnectionFilterSet."""

        model = Connection
        fields = [
            "id",
            "name",
            "description",
            "comments",
            "connection_template_id",
            "connection_template",
        ]

    def search(
        self, queryset: QuerySet[Connection], name: str, value: str
    ) -> QuerySet[Connection]:
        """Search for connections."""

        if not value.strip():
            return queryset
        return queryset.filter(
            models.Q(name__icontains=value)
            | models.Q(connection_template__name__icontains=value)
            | models.Q(description__icontains=value)
            | models.Q(comments__icontains=value)
        )

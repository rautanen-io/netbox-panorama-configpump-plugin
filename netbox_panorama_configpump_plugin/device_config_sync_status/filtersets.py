"""Device config sync status filtersets."""

from __future__ import annotations

from django.db import models
from django.db.models import QuerySet
from django_filters import BooleanFilter, DateTimeFilter
from netbox.filtersets import NetBoxModelFilterSet
from utilities import filters

from netbox_panorama_configpump_plugin.device_config_sync_status.models import (
    DeviceConfigSyncStatus,
)


# pylint: disable=too-many-ancestors
class DeviceConfigSyncStatusFilterSet(NetBoxModelFilterSet):
    """Filterset for DeviceConfigSyncStatus."""

    device_id = filters.MultiValueNumberFilter(
        field_name="device__id",
        label="Device (ID)",
    )
    device = filters.MultiValueCharFilter(
        field_name="device__name",
        label="Device (name)",
    )
    connection_id = filters.MultiValueNumberFilter(
        field_name="connection__id",
        label="Connection (ID)",
    )
    connection = filters.MultiValueCharFilter(
        field_name="connection__name",
        label="Connection (name)",
    )
    config_render_ok = BooleanFilter()
    last_pull = DateTimeFilter()
    last_pull_before = DateTimeFilter(
        field_name="last_pull",
        lookup_expr="lte",
    )
    last_pull_after = DateTimeFilter(
        field_name="last_pull",
        lookup_expr="gte",
    )
    last_push = DateTimeFilter()
    last_push_before = DateTimeFilter(
        field_name="last_push",
        lookup_expr="lte",
    )
    last_push_after = DateTimeFilter(
        field_name="last_push",
        lookup_expr="gte",
    )
    sync_job_id = filters.MultiValueNumberFilter(
        field_name="sync_job__id",
        label="Sync Job (ID)",
    )
    sync_job = filters.MultiValueCharFilter(
        field_name="sync_job__name",
        label="Sync Job (name)",
    )

    # pylint: disable=too-few-public-methods
    class Meta:
        """Meta options for DeviceConfigSyncStatusFilterSet."""

        model = DeviceConfigSyncStatus
        fields = [
            "id",
            "device_id",
            "device",
            "connection_id",
            "connection",
            "lines_added",
            "lines_removed",
            "config_render_ok",
            "last_pull",
            "last_pull_before",
            "last_pull_after",
            "last_push",
            "last_push_before",
            "last_push_after",
            "sync_job_id",
            "sync_job",
        ]

    def search(
        self, queryset: QuerySet[DeviceConfigSyncStatus], name: str, value: str
    ) -> QuerySet[DeviceConfigSyncStatus]:
        if not value.strip():
            return queryset
        return queryset.filter(
            models.Q(device__name__icontains=value)
            | models.Q(connection__name__icontains=value)
            | models.Q(panorama_configuration__icontains=value)
            | models.Q(sync_job__name__icontains=value)
        )

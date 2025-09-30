"""Filtersets for the PanoramaConfigPump plugin."""

import django_filters
from dcim.models import Device
from django.core.exceptions import ObjectDoesNotExist
from netbox.filtersets import NetBoxModelFilterSet

from netbox_panorama_configpump_plugin.connection_template.models import (
    ConnectionTemplate,
)


class DeviceByConnectionTemplateFilter(NetBoxModelFilterSet):
    """Filter for devices by connection template."""

    connection_template_id = django_filters.NumberFilter(
        method="filter_by_connection_template", label="Connection template ID"
    )

    # pylint: disable=too-few-public-methods
    class Meta:
        """Meta options."""

        model = Device
        fields = []

    def filter_by_connection_template(self, queryset, _, value):
        """Filter for devices by connection template."""

        try:
            connection_template = ConnectionTemplate.objects.get(pk=value)
        except ObjectDoesNotExist:
            return queryset.none()

        platforms = connection_template.platforms.all()
        if not platforms.exists():
            return queryset.none()

        return queryset.filter(platform__in=platforms)

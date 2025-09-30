"""Django models import for filtersets."""

from __future__ import annotations

from django.db import models
from django.db.models import QuerySet
from netbox.filtersets import NetBoxModelFilterSet
from utilities import filters

from .models import ConnectionTemplate


class ConnectionTemplateFilterSet(NetBoxModelFilterSet):
    """Filterset for ConnectionTemplate model."""

    platform_id = filters.MultiValueNumberFilter(
        field_name="platforms__id",
        label="Platform (ID)",
    )
    platform = filters.MultiValueCharFilter(
        field_name="platforms__slug",
        label="Platform (slug)",
    )

    # pylint: disable=too-few-public-methods
    class Meta:
        """Meta options."""

        model = ConnectionTemplate
        fields = [
            "id",
            "name",
            "panorama_url",
            "token_key",
            "file_name_prefix",
            "request_timeout",
            "description",
            "comments",
            "platform_id",
            "platform",
        ]

    def search(
        self, queryset: QuerySet[ConnectionTemplate], name: str, value: str
    ) -> QuerySet[ConnectionTemplate]:
        if not value.strip():
            return queryset
        return queryset.filter(
            models.Q(name__icontains=value)
            | models.Q(panorama_url__icontains=value)
            | models.Q(token_key__icontains=value)
            | models.Q(file_name_prefix__icontains=value)
            | models.Q(description__icontains=value)
            | models.Q(comments__icontains=value)
        )

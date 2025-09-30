"""Serializers for PanoramaConfigPump plugin."""

# pylint: disable=too-many-ancestors
from core.api.serializers_.jobs import JobSerializer
from dcim.api.serializers_.devices import DeviceSerializer
from dcim.api.serializers_.platforms import PlatformSerializer
from netbox.api.serializers import NetBoxModelSerializer

from netbox_panorama_configpump_plugin.connection.models import Connection
from netbox_panorama_configpump_plugin.connection_template.models import (
    ConnectionTemplate,
)
from netbox_panorama_configpump_plugin.device_config_sync_status.models import (
    DeviceConfigSyncStatus,
)


class ConnectionTemplateSerializer(NetBoxModelSerializer):
    """Serializer for ConnectionTemplate model."""

    platforms = PlatformSerializer(
        nested=True, many=True, required=False, allow_null=True
    )

    # pylint: disable=too-few-public-methods
    class Meta:
        """Meta options."""

        model = ConnectionTemplate
        fields = [
            "id",
            "url",
            "display_url",
            "display",
            "name",
            "panorama_url",
            "token_key",
            "file_name_prefix",
            "platforms",
            "request_timeout",
            "description",
            "comments",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        ]
        brief_fields = ("id", "url", "display", "name")


class ConnectionSerializer(NetBoxModelSerializer):
    """Serializer for Connection model."""

    connection_template = ConnectionTemplateSerializer(nested=True)
    devices = DeviceSerializer(nested=True, many=True, required=False)

    # pylint: disable=too-few-public-methods
    class Meta:
        """Meta options."""

        model = Connection
        fields = [
            "id",
            "url",
            "display_url",
            "display",
            "name",
            "connection_template",
            "devices",
            "description",
            "comments",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        ]
        brief_fields = ("id", "url", "display", "name")


class DeviceConfigSyncStatusSerializer(NetBoxModelSerializer):
    """Serializer for DeviceConfigSyncStatus model."""

    device = DeviceSerializer(nested=True)
    connection = ConnectionSerializer(nested=True)
    sync_job = JobSerializer(nested=True, required=False, allow_null=True)

    # pylint: disable=too-few-public-methods
    class Meta:
        """Meta options."""

        model = DeviceConfigSyncStatus
        fields = [
            "id",
            "url",
            "display_url",
            "display",
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
            "custom_fields",
            "created",
            "last_updated",
        ]
        brief_fields = ("id", "url", "display", "device", "connection")

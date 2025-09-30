"""Views for PanoramaConfigPump plugin."""

# pylint: disable=too-many-ancestors
from dcim.api.serializers_.devices import DeviceSerializer
from dcim.models import Device
from netbox.api.viewsets import NetBoxModelViewSet
from rest_framework.exceptions import PermissionDenied

from netbox_panorama_configpump_plugin.api.filtersets import (
    DeviceByConnectionTemplateFilter,
)
from netbox_panorama_configpump_plugin.api.serializers import (
    ConnectionSerializer,
    ConnectionTemplateSerializer,
    DeviceConfigSyncStatusSerializer,
)
from netbox_panorama_configpump_plugin.connection.filtersets import ConnectionFilterSet
from netbox_panorama_configpump_plugin.connection.models import Connection
from netbox_panorama_configpump_plugin.connection_template.filtersets import (
    ConnectionTemplateFilterSet,
)
from netbox_panorama_configpump_plugin.connection_template.models import (
    ConnectionTemplate,
)
from netbox_panorama_configpump_plugin.device_config_sync_status.filtersets import (
    DeviceConfigSyncStatusFilterSet,
)
from netbox_panorama_configpump_plugin.device_config_sync_status.models import (
    DeviceConfigSyncStatus,
)


class ConnectionTemplateViewSet(NetBoxModelViewSet):
    """Viewset for ConnectionTemplate model."""

    queryset = ConnectionTemplate.objects.all()
    serializer_class = ConnectionTemplateSerializer
    filterset_class = ConnectionTemplateFilterSet


class ConnectionViewSet(NetBoxModelViewSet):
    """Viewset for Connection model."""

    queryset = Connection.objects.all()
    serializer_class = ConnectionSerializer
    filterset_class = ConnectionFilterSet


class DeviceViewSet(NetBoxModelViewSet):
    """Viewset for Device model."""

    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    filterset_class = DeviceByConnectionTemplateFilter

    def get_queryset(self):
        """Restrict access to users with permission to view plugin connections."""
        if not self.request.user.has_perm(
            "netbox_panorama_configpump_plugin.view_connection"
        ):
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().get_queryset()


class DeviceConfigSyncStatusViewSet(NetBoxModelViewSet):
    """Viewset for DeviceConfigSyncStatus model."""

    queryset = DeviceConfigSyncStatus.objects.all()
    serializer_class = DeviceConfigSyncStatusSerializer
    filterset_class = DeviceConfigSyncStatusFilterSet

"""URLs for PanoramaConfigPump plugin."""

from netbox.api.routers import NetBoxRouter

from netbox_panorama_configpump_plugin.api.views import (
    ConnectionTemplateViewSet,
    ConnectionViewSet,
    DeviceConfigSyncStatusViewSet,
    DeviceViewSet,
)

router = NetBoxRouter()
router.register("connection-templates", ConnectionTemplateViewSet)
router.register("connections", ConnectionViewSet)
router.register("devices", DeviceViewSet)
router.register("device-config-sync-statuses", DeviceConfigSyncStatusViewSet)

urlpatterns = router.urls

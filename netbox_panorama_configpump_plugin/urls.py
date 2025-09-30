"""URLs for PanoramaConfigPump plugin."""

from __future__ import annotations

from django.urls import include, path
from django.urls.resolvers import URLPattern
from utilities.urls import get_model_urls

from netbox_panorama_configpump_plugin.connection import views as connection_views
from netbox_panorama_configpump_plugin.connection_template import (
    views as connection_template_views,
)
from netbox_panorama_configpump_plugin.device_config_sync_status import (
    views as device_config_sync_status_views,
)

urlpatterns: list[URLPattern] = [
    path(
        "connection-templates/",
        connection_template_views.ConnectionTemplateListView.as_view(),
        name="connectiontemplate_list",
    ),
    path(
        "connection-templates/<int:pk>/",
        include(
            get_model_urls("netbox_panorama_configpump_plugin", "connectiontemplate")
        ),
    ),
    path(
        "connection-templates/add/",
        connection_template_views.ConnectionTemplateEditView.as_view(),
        name="connectiontemplate_add",
    ),
    path(
        "connections/",
        connection_views.ConnectionListView.as_view(),
        name="connection_list",
    ),
    path(
        "connections/<int:pk>/",
        include(get_model_urls("netbox_panorama_configpump_plugin", "connection")),
    ),
    path(
        "connections/add/",
        connection_views.ConnectionEditView.as_view(),
        name="connection_add",
    ),
    path(
        "device-config-sync-statuses/",
        device_config_sync_status_views.DeviceConfigSyncStatusListView.as_view(),
        name="deviceconfigsyncstatus_list",
    ),
    path(
        "device-config-sync-statuses/<int:pk>/",
        include(
            get_model_urls(
                "netbox_panorama_configpump_plugin", "deviceconfigsyncstatus"
            )
        ),
    ),
    path(
        "device-config-sync-statuses/add/",
        device_config_sync_status_views.DeviceConfigSyncStatusEditView.as_view(),
        name="deviceconfigsyncstatus_add",
    ),
]

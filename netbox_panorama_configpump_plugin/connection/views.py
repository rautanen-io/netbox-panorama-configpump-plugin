"""Views for Connection model."""

from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from netbox.views.generic import (
    ObjectDeleteView,
    ObjectEditView,
    ObjectListView,
    ObjectView,
)
from netbox.views.generic.base import get_object_or_404
from utilities.forms import ConfirmationForm
from utilities.views import register_model_view

from netbox_panorama_configpump_plugin.connection.filtersets import ConnectionFilterSet
from netbox_panorama_configpump_plugin.connection.forms import (
    ConnectionFilterForm,
    ConnectionForm,
)
from netbox_panorama_configpump_plugin.connection.models import Connection
from netbox_panorama_configpump_plugin.connection.tables import ConnectionTable
from netbox_panorama_configpump_plugin.device_config_sync_status.jobs import (
    PullDeviceConfigJobRunner,
    PushAndPullDeviceConfigJobRunner,
)
from netbox_panorama_configpump_plugin.device_config_sync_status.models import (
    DeviceConfigSyncStatus,
)
from netbox_panorama_configpump_plugin.device_config_sync_status.tables import (
    DeviceConfigSyncStatusTable,
)
from netbox_panorama_configpump_plugin.utils.helpers import get_return_url


@register_model_view(Connection)
class ConnectionView(ObjectView):
    """View for Connection model."""

    queryset = Connection.objects.all()

    def get_extra_context(
        self, request: HttpRequest, instance: Connection
    ) -> dict[str, Any]:
        """Add DeviceConfigSyncStatus table to context."""
        context = super().get_extra_context(request, instance)

        device_config_sync_statuses = instance.device_config_sync_statuses.all()
        table = DeviceConfigSyncStatusTable(device_config_sync_statuses)
        table.configure(request)

        context["device_config_sync_status_table"] = table
        return context


# pylint: disable=too-many-ancestors
class ConnectionListView(ObjectListView):
    """List view for Connection model."""

    queryset = Connection.objects.annotate(
        total_lines_added=Sum("device_config_sync_statuses__lines_added"),
        total_lines_removed=Sum("device_config_sync_statuses__lines_removed"),
        total_lines_changed=Sum("device_config_sync_statuses__lines_changed"),
    )

    table = ConnectionTable
    filterset = ConnectionFilterSet
    filterset_form = ConnectionFilterForm


@register_model_view(Connection, "edit")
class ConnectionEditView(ObjectEditView):
    """Edit view for Connection model."""

    queryset = Connection.objects.all()
    form = ConnectionForm


@register_model_view(Connection, "delete")
class ConnectionDeleteView(ObjectDeleteView):
    """Delete view for Connection model."""

    queryset = Connection.objects.all()


@register_model_view(Connection, "pull_all_configs")
class ConnectionPullView(ObjectView):
    """View to pull all configurations from Panorama for a connection."""

    queryset = Connection.objects.all()

    def get(self, request: HttpRequest, **kwargs: Any) -> HttpResponse:
        connection = get_object_or_404(Connection, pk=kwargs["pk"])
        device_config_sync_statuses = connection.device_config_sync_statuses.all()
        if device_config_sync_statuses.count() == 0:
            messages.warning(
                request,
                f"No devices found in connection '{connection.name}'.",
            )
            return redirect(get_return_url(connection))

        for device_config_sync_status in device_config_sync_statuses:
            sync_job = PullDeviceConfigJobRunner.enqueue(
                instance=device_config_sync_status,
                name=f"Pull configurations for {device_config_sync_status.device.name}",
                user=request.user,
                device_config_sync_status_id=device_config_sync_status.id,
            )
            device_config_sync_status.sync_job = sync_job
            DeviceConfigSyncStatus.objects.filter(
                pk=device_config_sync_status.pk
            ).update(sync_job=sync_job)

        messages.success(
            request,
            (
                "Configuration pull initiated from Panorama for "
                f"{device_config_sync_statuses.count()} device(s) in "
                f"connection '{connection.name}'."
            ),
        )

        return redirect(get_return_url(connection))


@register_model_view(Connection, "push_all_configs")
class ConnectionPushView(ObjectView):
    """View to push all configurations to Panorama for a connection."""

    queryset = Connection.objects.all()
    template_name = "netbox_panorama_configpump_plugin/confirm_push.html"

    # pylint: disable=arguments-differ
    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        """
        Display confirmation form for pushing configurations for all devices
        in connection.
        """
        form = ConfirmationForm()
        connection = get_object_or_404(Connection, pk=pk)

        if not connection.config_render_ok:
            messages.error(
                request,
                (
                    "Cannot push configuration for one or more devices in this "
                    "connection because their current configurations do not "
                    "render properly. Please review and fix the configuration "
                    "template or context data for all affected devices before "
                    "attempting to push."
                ),
            )
            return redirect(get_return_url(connection))

        devices = connection.devices

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "object": connection,
                "return_url": get_return_url(connection),
                "devices": devices,
                "is_connection_push": True,
            },
        )

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Handle the push configurations request for all devices in connection."""
        connection = get_object_or_404(Connection, pk=pk)
        form = ConfirmationForm(request.POST)

        if form.is_valid():
            device_config_sync_statuses = connection.device_config_sync_statuses.all()
            if device_config_sync_statuses.count() == 0:
                messages.warning(
                    request,
                    f"No devices found in connection '{connection.name}'.",
                )
                return redirect(get_return_url(connection))

            for device_config_sync_status in device_config_sync_statuses:
                sync_job = PushAndPullDeviceConfigJobRunner.enqueue(
                    instance=device_config_sync_status,
                    name=(
                        f"Push and pull configurations for "
                        f"{device_config_sync_status.device.name}"
                    ),
                    user=request.user,
                    device_config_sync_status_id=device_config_sync_status.id,
                )
                device_config_sync_status.sync_job = sync_job
                DeviceConfigSyncStatus.objects.filter(
                    pk=device_config_sync_status.pk
                ).update(sync_job=sync_job)

            messages.success(
                request,
                (
                    "Configuration push initiated to Panorama for "
                    f"{device_config_sync_statuses.count()} device(s) in "
                    f"connection '{connection.name}'."
                ),
            )

        else:
            messages.error(request, "Invalid form submission.")

        return redirect(get_return_url(connection))

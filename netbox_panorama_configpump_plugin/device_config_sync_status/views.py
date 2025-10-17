"""Device config sync status views."""

from __future__ import annotations

from typing import Any

from dcim.models import Device
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from netbox.views.generic import (
    ObjectDeleteView,
    ObjectEditView,
    ObjectListView,
    ObjectView,
)
from netbox.views.generic.base import get_object_or_404
from utilities.forms import ConfirmationForm
from utilities.views import (
    ContentTypePermissionRequiredMixin,
    ViewTab,
    register_model_view,
)

from netbox_panorama_configpump_plugin.device_config_sync_status.filtersets import (
    DeviceConfigSyncStatusFilterSet,
)
from netbox_panorama_configpump_plugin.device_config_sync_status.forms import (
    DeviceConfigSyncStatusFilterForm,
    DeviceConfigSyncStatusForm,
)
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
from netbox_panorama_configpump_plugin.utils.helpers import (
    extract_matching_xml_by_xpaths,
    get_return_url,
    normalize_xml,
)


@register_model_view(DeviceConfigSyncStatus)
class DeviceConfigSyncStatusView(ObjectView):
    """View for DeviceConfigSyncStatus model."""

    queryset = DeviceConfigSyncStatus.objects.all()


# pylint: disable=too-many-ancestors
class DeviceConfigSyncStatusListView(ObjectListView):
    """List view for DeviceConfigSyncStatus model."""

    queryset = DeviceConfigSyncStatus.objects.all()
    table = DeviceConfigSyncStatusTable
    filterset = DeviceConfigSyncStatusFilterSet
    filterset_form = DeviceConfigSyncStatusFilterForm


@register_model_view(DeviceConfigSyncStatus, "edit")
class DeviceConfigSyncStatusEditView(ObjectEditView):
    """Edit view for DeviceConfigSyncStatus model."""

    queryset = DeviceConfigSyncStatus.objects.all()
    form = DeviceConfigSyncStatusForm


@register_model_view(DeviceConfigSyncStatus, "delete")
class DeviceConfigSyncStatusDeleteView(ObjectDeleteView):
    """Delete view for DeviceConfigSyncStatus model."""

    queryset = DeviceConfigSyncStatus.objects.all()


@register_model_view(DeviceConfigSyncStatus, "pull_config")
class DeviceConfigPullView(ObjectView):
    """View to pull configurations from Panorama for a device config sync status."""

    queryset = DeviceConfigSyncStatus.objects.all()

    def get(self, request: HttpRequest, **kwargs: Any) -> HttpResponse:
        device_config_sync_status = get_object_or_404(
            DeviceConfigSyncStatus, pk=kwargs["pk"]
        )

        sync_job = PullDeviceConfigJobRunner.enqueue(
            instance=device_config_sync_status,
            name=f"Pull configurations for {device_config_sync_status.device.name}",
            user=request.user,
            device_config_sync_status_id=device_config_sync_status.id,
        )
        device_config_sync_status.sync_job = sync_job
        DeviceConfigSyncStatus.objects.filter(pk=device_config_sync_status.pk).update(
            sync_job=sync_job
        )

        messages.success(
            request,
            (
                "Configuration pull initiated from Panorama for device "
                f"'{device_config_sync_status.device}'."
            ),
        )

        return redirect(get_return_url(device_config_sync_status.connection))


@register_model_view(DeviceConfigSyncStatus, "push_config")
class DeviceConfigPushView(ObjectView):
    """View to push configurations to Panorama for a device config sync status."""

    queryset = DeviceConfigSyncStatus.objects.all()
    template_name = "netbox_panorama_configpump_plugin/confirm_push.html"

    # pylint: disable=arguments-differ
    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Display confirmation form for pushing configuration."""
        form = ConfirmationForm()
        device_config_sync_status = get_object_or_404(DeviceConfigSyncStatus, pk=pk)

        if not device_config_sync_status.config_render_ok:
            messages.error(
                request,
                (
                    "Cannot push configuration for device "
                    f"'{device_config_sync_status.device}' "
                    "because the current configuration does not render properly. "
                    "Please fix the configuration template or context data first."
                ),
            )
            return redirect(get_return_url(device_config_sync_status.connection))

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "object": device_config_sync_status,
                "device": device_config_sync_status.device,
                "connection": device_config_sync_status.connection,
            },
        )

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Handle the push configuration request."""
        device_config_sync_status = get_object_or_404(DeviceConfigSyncStatus, pk=pk)
        form = ConfirmationForm(request.POST)

        if form.is_valid():

            sync_job = PushAndPullDeviceConfigJobRunner.enqueue(
                instance=device_config_sync_status,
                name=(
                    "Push and pull configurations for "
                    f"'{device_config_sync_status.device.name}'"
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
                    f"Configuration push initiated to Panorama for "
                    f"{device_config_sync_status.device.name}."
                ),
            )
        else:
            messages.error(request, "Invalid form submission.")

        return redirect(get_return_url(device_config_sync_status.connection))


@register_model_view(Device, "panorama_diff", path="panorama-diff")
class DeviceConfigDiffView(ContentTypePermissionRequiredMixin, ObjectView):
    """
    Device config diff tab view for comparing current configuration
    with Panorama templates.
    """

    queryset = Device.objects.all()
    template_name = "netbox_panorama_configpump_plugin/deviceconfigdiff.html"
    additional_permissions = ["dcim.view_device"]

    def get_required_permission(self):
        return "netbox_panorama_configpump_plugin.view_connection"

    tab = ViewTab(
        label=_("Panorama Config Diff"),
        weight=10000,
        permission="netbox_panorama_configpump_plugin.view_connection",
    )

    def get_extra_context(
        self, request: HttpRequest, instance: Device
    ) -> dict[str, Any]:
        """
        Add old and new configuration for the Panorama config diff view.
        """

        config_sync_status = instance.device_config_sync_statuses.first()
        if config_sync_status:
            panorama_configuration, panorama_configuration_valid = normalize_xml(
                config_sync_status.panorama_configuration
            )
            rendered_configuration, rendered_configuration_valid = normalize_xml(
                config_sync_status.get_rendered_configuration()
            )
            if rendered_configuration_valid:
                rendered_configuration = extract_matching_xml_by_xpaths(
                    rendered_configuration, config_sync_status.get_xpath_entries()
                )

        else:
            panorama_configuration = ""
            panorama_configuration_valid = False
            rendered_configuration = ""
            rendered_configuration_valid = False

        return {
            "device": instance,
            "panorama_configuration": (
                panorama_configuration
                if panorama_configuration_valid
                else (
                    config_sync_status.panorama_configuration
                    if config_sync_status
                    else ""
                )
            ),
            "rendered_configuration": (
                rendered_configuration
                if rendered_configuration_valid
                else (
                    config_sync_status.get_rendered_configuration()
                    if config_sync_status
                    else ""
                )
            ),
            "rendered_configuration_valid": rendered_configuration_valid,
            "panorama_configuration_valid": panorama_configuration_valid,
        }

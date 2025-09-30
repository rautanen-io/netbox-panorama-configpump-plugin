"""Views for ConnectionTemplate model."""

# pylint: disable=too-many-ancestors
from __future__ import annotations

from netbox.views.generic import (
    ObjectDeleteView,
    ObjectEditView,
    ObjectListView,
    ObjectView,
)
from utilities.views import register_model_view

from netbox_panorama_configpump_plugin.connection_template.filtersets import (
    ConnectionTemplateFilterSet,
)
from netbox_panorama_configpump_plugin.connection_template.forms import (
    ConnectionTemplateFilterForm,
    ConnectionTemplateForm,
)
from netbox_panorama_configpump_plugin.connection_template.models import (
    ConnectionTemplate,
)
from netbox_panorama_configpump_plugin.connection_template.tables import (
    ConnectionTemplateTable,
)


@register_model_view(ConnectionTemplate)
class ConnectionTemplateView(ObjectView):
    """View for ConnectionTemplate model."""

    queryset = ConnectionTemplate.objects.all()


class ConnectionTemplateListView(ObjectListView):
    """List view for ConnectionTemplate model."""

    queryset = ConnectionTemplate.objects.all()
    table = ConnectionTemplateTable
    filterset = ConnectionTemplateFilterSet
    filterset_form = ConnectionTemplateFilterForm


@register_model_view(ConnectionTemplate, "edit")
class ConnectionTemplateEditView(ObjectEditView):
    """Edit view for ConnectionTemplate model."""

    queryset = ConnectionTemplate.objects.all()
    form = ConnectionTemplateForm


@register_model_view(ConnectionTemplate, "delete")
class ConnectionTemplateDeleteView(ObjectDeleteView):
    """Delete view for ConnectionTemplate model."""

    queryset = ConnectionTemplate.objects.all()

"""Form for ConnectionTemplate model."""

# pylint: disable=too-many-ancestors
from __future__ import annotations

from typing import Any

from dcim.models import Platform
from django.forms import ChoiceField
from netbox.forms import NetBoxModelFilterSetForm, NetBoxModelForm
from netbox.plugins import get_plugin_config
from utilities.forms.fields import (
    CommentField,
    DynamicModelMultipleChoiceField,
    TagFilterField,
)

from netbox_panorama_configpump_plugin import config
from netbox_panorama_configpump_plugin.connection_template.filtersets import (
    ConnectionTemplateFilterSet,
)
from netbox_panorama_configpump_plugin.connection_template.models import (
    ConnectionTemplate,
)


class ConnectionTemplateForm(NetBoxModelForm):
    """Form for ConnectionTemplate model."""

    comments = CommentField()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Populate defaults from plugin settings."""

        super().__init__(*args, **kwargs)

        # Populate token key choices from plugin settings:
        self.fields["token_key"] = ChoiceField(
            choices=[
                (k, k)
                for k in get_plugin_config(
                    "netbox_panorama_configpump_plugin",
                    "tokens",
                    default=config.default_settings["tokens"],
                ).keys()
            ],
        )
        self.fields["token_key"].help_text = (
            "Key name for the Panorama API token in "
            "PLUGINS_CONFIG['netbox_panorama_configpump_plugin']['tokens']"
        )

        # Add the default request timeout to the help text:
        default_request_timeout = str(
            get_plugin_config(
                "netbox_panorama_configpump_plugin",
                "default_request_timeout",
                default=config.default_settings["default_request_timeout"],
            )
        )
        if "request_timeout" in self.fields:
            self.fields["request_timeout"].help_text = (
                "Request timeout in seconds (1-3600). Leave blank to use default. "
                f"Default: {default_request_timeout}."
            )

        # Add the default file name prefix to the help text:
        default_filename_prefix = str(
            get_plugin_config(
                "netbox_panorama_configpump_plugin",
                "default_filename_prefix",
                default=config.default_settings["default_filename_prefix"],
            )
        )
        if "file_name_prefix" in self.fields:
            self.fields["file_name_prefix"].help_text = (
                "File name prefix for this template. XML files with this prefix "
                "will be uploaded to Panorama. The format of the file name is "
                "&lt;prefix&gt;_&lt;device_name&gt;.xml. Leave blank to use default. "
                f"Default: {default_filename_prefix}"
            )

    # pylint: disable=too-few-public-methods
    class Meta:
        """Meta options."""

        model = ConnectionTemplate
        fields = (
            "name",
            "panorama_url",
            "token_key",
            "file_name_prefix",
            "platforms",
            "request_timeout",
            "description",
            "tags",
            "comments",
        )


class ConnectionTemplateFilterForm(NetBoxModelFilterSetForm):
    """Filter form for ConnectionTemplate model."""

    model = ConnectionTemplate
    filterset = ConnectionTemplateFilterSet

    platform_id = DynamicModelMultipleChoiceField(
        queryset=Platform.objects.all(),
        required=False,
        label="Platforms",
    )
    tag = TagFilterField(model)

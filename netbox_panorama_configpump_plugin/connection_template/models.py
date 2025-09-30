"""Connection template models."""

# pylint: disable=too-many-ancestors
from __future__ import annotations

from typing import Any

from dcim.models import Platform
from django.core.validators import MaxValueValidator, MinValueValidator, URLValidator
from django.db import models
from netbox.models import PrimaryModel
from netbox.plugins import get_plugin_config

from netbox_panorama_configpump_plugin import config


class ConnectionTemplate(PrimaryModel):
    """Model storing Panorama connection templates and related settings."""

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique name for this Panorama connection template.",
    )

    panorama_url = models.URLField(
        help_text=("Panorama base URL (must start with http:// or https://)."),
        validators=[URLValidator(schemes=["http", "https"])],
    )

    token_key = models.CharField(
        max_length=255,
    )

    platforms = models.ManyToManyField(
        Platform,
        related_name="connection_templates",
        blank=True,
        help_text="Platforms this template applies to.",
    )

    request_timeout = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Request timeout for Panorama API calls in seconds (1-3600). "
            "Leave blank to use default."
        ),
        validators=[MinValueValidator(1), MaxValueValidator(3600)],
    )

    file_name_prefix = models.CharField(
        max_length=255,
        blank=True,
        help_text=(
            "File name prefix for this template. XML files with this prefix "
            "will be uploaded to Panorama. The format of the file name is "
            "&lt;prefix&gt;_&lt;device_name&gt;.xml. Leave blank to use default."
        ),
    )

    # pylint: disable=too-few-public-methods
    class Meta:
        """Meta options for ConnectionTemplate."""

        ordering = ("name",)

    def __str__(self) -> str:
        return str(self.name)

    def _get_request_timeout(self) -> int:
        if self.request_timeout:
            return self.request_timeout
        return int(
            get_plugin_config(
                "netbox_panorama_configpump_plugin",
                "default_request_timeout",
                default=config.default_settings["default_request_timeout"],
            )
        )

    def _get_file_name_prefix(self) -> str:
        if self.file_name_prefix:
            return self.file_name_prefix
        return str(
            get_plugin_config(
                "netbox_panorama_configpump_plugin",
                "default_filename_prefix",
                default=config.default_settings["default_filename_prefix"],
            )
        )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Populate defaults from plugin settings on save when fields are empty."""

        if not self.request_timeout:
            self.request_timeout = self._get_request_timeout()
        if not self.file_name_prefix:
            self.file_name_prefix = self._get_file_name_prefix()

        super().save(*args, **kwargs)

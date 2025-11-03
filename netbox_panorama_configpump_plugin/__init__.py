"""Top-level package for NetBox Panorama ConfigPump Plugin."""

from __future__ import annotations

__author__ = """Veikko Pankakoski"""
__email__ = "veikko@rautanen.io"
__version__ = "1.0.6"


from netbox.plugins import PluginConfig


class PanoramaConfigPumpConfig(PluginConfig):
    """Plugin configuration for the NetBox Panorama ConfigPump Plugin."""

    name = "netbox_panorama_configpump_plugin"
    verbose_name = "Panorama ConfigPump"
    description = (
        "A NetBox plugin for synchronizing device configs with Palo Alto Panorama, "
        "supporting pull, diff, and push workflows."
    )
    version = __version__
    base_url = "panorama-configpump"
    author = "rautanen.io"
    author_email = "veikko@rautanenyhtiot.fi"
    min_version = "4.2.5"
    max_version = "4.3.7"

    required_settings = []
    default_settings = {
        "default_request_timeout": 60,  # seconds
        "default_filename_prefix": "netbox-panorama",
        "ignore_ssl_warnings": False,
        "tokens": {},
        "commit_poll_attempts": 30,
        "commit_poll_interval": 3,  # seconds
        "top_level_menu": False,
    }

    # pylint: disable=import-outside-toplevel,unused-import
    def ready(self) -> None:
        from . import signals  # noqa: F401

        super().ready()


config = PanoramaConfigPumpConfig  # pylint: disable=invalid-name

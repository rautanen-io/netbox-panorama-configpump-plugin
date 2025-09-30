"""Navigation for PanoramaConfigPump plugin."""

# pylint: disable=line-too-long
from __future__ import annotations

from netbox.plugins import (
    PluginMenu,
    PluginMenuButton,
    PluginMenuItem,
    get_plugin_config,
)

from netbox_panorama_configpump_plugin import config

_menu_items = (
    PluginMenuItem(
        link="plugins:netbox_panorama_configpump_plugin:connection_list",
        link_text="Connections",
        permissions=["netbox_panorama_configpump_plugin.view_connection"],
        buttons=[
            PluginMenuButton(
                link="plugins:netbox_panorama_configpump_plugin:connection_add",
                title="Add",
                icon_class="mdi mdi-plus-thick",
                permissions=["netbox_panorama_configpump_plugin.add_connection"],
            )
        ],
    ),
    PluginMenuItem(
        link="plugins:netbox_panorama_configpump_plugin:connectiontemplate_list",
        link_text="Connection Templates",
        permissions=["netbox_panorama_configpump_plugin.view_connectiontemplate"],
        buttons=[
            PluginMenuButton(
                link="plugins:netbox_panorama_configpump_plugin:connectiontemplate_add",
                title="Add",
                icon_class="mdi mdi-plus-thick",
                permissions=[
                    "netbox_panorama_configpump_plugin.add_connectiontemplate"
                ],
            )
        ],
    ),
    # PluginMenuItem(
    #     link="plugins:netbox_panorama_configpump_plugin:deviceconfigsyncstatus_list",
    #     link_text="Device Config Sync Status",
    #     permissions=["netbox_panorama_configpump_plugin.view_deviceconfigsyncstatus"],
    #     buttons=[
    #         PluginMenuButton(
    #             link="plugins:netbox_panorama_configpump_plugin:deviceconfigsyncstatus_add",
    #             title="Add",
    #             icon_class="mdi mdi-plus-thick",
    #             permissions=[
    #                 "netbox_panorama_configpump_plugin.add_deviceconfigsyncstatus"
    #             ],
    #         )
    #     ],
    # ),
)

if get_plugin_config(
    "netbox_panorama_configpump_plugin",
    "top_level_menu",
    default=config.default_settings["top_level_menu"],
):
    menu = PluginMenu(
        label="Panorama ConfigPump",
        groups=(
            (
                "Panorama ConfigPump",
                _menu_items,
            ),
        ),
        icon_class="mdi mdi-water-pump",
    )
else:
    menu_items = _menu_items

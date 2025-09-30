"""Panorama mixin for common Panorama-related functionality."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from io import BytesIO
from typing import Any

import requests
import urllib3
from lxml import etree
from netbox.plugins import get_plugin_config
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, RequestException, SSLError, Timeout
from urllib3.exceptions import InsecureRequestWarning

from netbox_panorama_configpump_plugin import config
from netbox_panorama_configpump_plugin.utils.helpers import normalize_xml


class PanoramaMixin:
    """Mixin class providing common Panorama-related functionality."""

    def _deduce_file_name(self) -> str:
        """Deduce the file name for a device config sync status."""

        # Make the filename systemwide friendly: remove whitespace, make lowercase, etc.
        # Remove leading/trailing whitespace, replace spaces with underscores, make
        # lowercase, remove problematic chars
        file_name = self.device.name.strip().lower()
        file_name = re.sub(r"\s+", "_", file_name)
        file_name = re.sub(r"[^a-z0-9_\-\.]", "", file_name)

        return (
            f"{self.connection.connection_template.file_name_prefix}"
            f"_{file_name}.xml"
        )

    def get_connection_config(self) -> dict[str, Any]:
        """Get the connection configuration for a device config sync status."""

        tokens = get_plugin_config(
            "netbox_panorama_configpump_plugin",
            "tokens",
            default=config.default_settings["tokens"],
        )
        token_key = self.connection.connection_template.token_key
        try:
            token = tokens[token_key]
        except (KeyError, TypeError) as exc:
            raise ValueError(
                f"Token key '{token_key}' not found in plugin configuration."
            ) from exc

        request_timeout = self.connection.connection_template.request_timeout
        panorama_url = self.connection.connection_template.panorama_url
        file_name_prefix = self.connection.connection_template.file_name_prefix
        ignore_ssl_warnings = get_plugin_config(
            "netbox_panorama_configpump_plugin",
            "ignore_ssl_warnings",
            default=config.default_settings["ignore_ssl_warnings"],
        )

        return {
            "token": token,
            "request_timeout": request_timeout,
            "panorama_url": panorama_url,
            "ignore_ssl_warnings": ignore_ssl_warnings,
            "file_name_prefix": file_name_prefix,
        }

    def pull_candidate_config(self) -> str:
        """
        Pull the candidate configuration from Panorama.
        """

        connection_config = self.get_connection_config()

        params = {
            "type": "export",
            "category": "configuration",
            "key": connection_config["token"],
        }

        if connection_config["ignore_ssl_warnings"]:
            urllib3.disable_warnings(InsecureRequestWarning)

        try:
            response = requests.get(
                connection_config["panorama_url"] + "/api/",
                params=params,
                verify=not connection_config["ignore_ssl_warnings"],
                timeout=connection_config["request_timeout"],
            )
            response.raise_for_status()
        except SSLError as exc:
            raise ValueError(
                f"SSL error occurred when connecting to Panorama: {exc}"
            ) from exc
        except RequestsConnectionError as exc:
            raise ValueError(
                f"Connection error occurred when connecting to Panorama: {exc}"
            ) from exc
        except Timeout as exc:
            raise ValueError(
                f"Request timeout occurred when connecting to Panorama: {exc}"
            ) from exc
        except HTTPError as exc:
            raise ValueError(
                f"HTTP error occurred when connecting to Panorama: {exc}"
            ) from exc
        except RequestException as exc:
            raise ValueError(
                f"Request error occurred when connecting to Panorama: {exc}"
            ) from exc

        return response.text

    def push_candidate_config(self, rendered_configuration: str) -> int:
        """Push the configuration for a device config sync status."""

        connection_config = self.get_connection_config()

        file_obj = BytesIO(rendered_configuration.encode("utf-8"))
        file_name = self._deduce_file_name()

        files = {"file": (file_name, file_obj, "application/xml")}
        url = (
            f"""{connection_config["panorama_url"]}/api/?"""
            f"""type=import&category=configuration&key={connection_config["token"]}"""
        )

        if connection_config["ignore_ssl_warnings"]:
            urllib3.disable_warnings(InsecureRequestWarning)

        try:
            response = requests.post(
                url,
                files=files,
                verify=not connection_config["ignore_ssl_warnings"],
                timeout=connection_config["request_timeout"],
            )
            response.raise_for_status()
        except SSLError as exc:
            raise ValueError(
                f"SSL error occurred when connecting to Panorama: {exc}"
            ) from exc
        except RequestsConnectionError as exc:
            raise ValueError(
                f"Connection error occurred when connecting to Panorama: {exc}"
            ) from exc
        except Timeout as exc:
            raise ValueError(
                f"Request timeout occurred when connecting to Panorama: {exc}"
            ) from exc
        except HTTPError as exc:
            raise ValueError(
                f"HTTP error occurred when connecting to Panorama: {exc}"
            ) from exc
        except RequestException as exc:
            raise ValueError(
                f"Request error occurred when connecting to Panorama: {exc}"
            ) from exc

        return response.status_code

    def list_item_names_in_xml(self, configuration: str, item_type: str) -> list[str]:
        """
        Process the configuration string and extract item names from the XML structure.

        Looks for items in the path:
        <config><devices><entry><{item_type}><entry name="ITEM_NAME">

        Args:
            configuration: XML configuration string
            item_type: Type of items to extract ("template" or "device-group")

        Returns:
            List of item names found in the configuration
        """
        try:
            root = ET.fromstring(configuration)

            item_list = []

            devices = root.find("devices")
            if devices is not None:
                for device_entry in devices.findall("entry"):
                    item_section = device_entry.find(item_type)
                    if item_section is not None:
                        # Find all item entries within this device
                        for item_entry in item_section.findall("entry"):
                            item_name = item_entry.get("name")
                            if item_name:
                                item_list.append(item_name)

            return item_list

        except ET.ParseError as e:
            raise ValueError(f"Error parsing XML config: {e}") from e
        except (AttributeError, KeyError) as e:
            raise ValueError(f"Error processing config: {e}") from e

    def extract_templates_and_device_groups_from_config(
        self,
        candidate_config: str,
        template_names: list[str],
        device_group_names: list[str],
    ) -> str:
        """
        Extract specified templates and device-groups from a Panorama configuration.

        This method processes a candidate config by:

        1. Finding all templates in
            devices/entry[@name='localhost.localdomain']/template/
        2. Copying those blocks whose entry[@name] matches with the names in
            template_names list.
        3. Finding all device-groups in
            devices/entry[@name='localhost.localdomain']/device-group/
        4. Copying those blocks whose entry[@name] matches with the names in
            device_group_names list.
        5. Creating a new XML string with the following structure:
        <?xml version="1.0"?>
        <config version="11.1.0" urldb="paloaltonetworks" detail-version="11.1.6">
            <devices>
                <entry name="localhost.localdomain">
                    <template>
                        <first template entry >
                        <second template entry >
                        ...
                    </template>
                    <device-group>
                        <first device-group entry >
                        <second device-group entry >
                    </device-group>
                </entry>
            </devices>
        </config>
        6. Returning the new XML string.
        """
        try:
            # Parse the candidate config
            root = ET.fromstring(candidate_config)

            # Create new root element with proper attributes
            new_root = ET.Element("config")
            new_root.set("version", "11.1.0")
            new_root.set("urldb", "paloaltonetworks")
            new_root.set("detail-version", "11.1.6")

            # Create devices element
            devices = ET.SubElement(new_root, "devices")

            # Create device entry
            device_entry = ET.SubElement(devices, "entry")
            device_entry.set("name", "localhost.localdomain")

            # Find the source device entry in candidate config
            source_devices = root.find("devices")
            if source_devices is not None:
                source_device_entry = None
                for entry in source_devices.findall("entry"):
                    if entry.get("name") == "localhost.localdomain":
                        source_device_entry = entry
                        break

                if source_device_entry is not None:
                    # Process templates
                    if template_names:
                        template_section = ET.SubElement(device_entry, "template")
                        source_template_section = source_device_entry.find("template")
                        if source_template_section is not None:
                            for template_entry in source_template_section.findall(
                                "entry"
                            ):
                                template_name = template_entry.get("name")
                                if template_name in template_names:
                                    # Deep copy the template entry
                                    new_template_entry = ET.SubElement(
                                        template_section, "entry"
                                    )
                                    new_template_entry.set("name", template_name)
                                    # Copy all child elements
                                    for child in template_entry:
                                        new_template_entry.append(child)

                    # Process device-groups
                    if device_group_names:
                        device_group_section = ET.SubElement(
                            device_entry, "device-group"
                        )
                        source_device_group_section = source_device_entry.find(
                            "device-group"
                        )
                        if source_device_group_section is not None:
                            for (
                                device_group_entry
                            ) in source_device_group_section.findall("entry"):
                                device_group_name = device_group_entry.get("name")
                                if device_group_name in device_group_names:
                                    # Deep copy the device-group entry
                                    new_device_group_entry = ET.SubElement(
                                        device_group_section, "entry"
                                    )
                                    new_device_group_entry.set(
                                        "name", device_group_name
                                    )
                                    # Copy all child elements
                                    for child in device_group_entry:
                                        new_device_group_entry.append(child)

            # Convert to string with proper formatting using lxml
            # Convert ElementTree to lxml ElementTree for better control
            lxml_root = etree.fromstring(ET.tostring(new_root, encoding="unicode"))
            xml_string = etree.tostring(
                lxml_root,
                pretty_print=True,
                encoding="unicode",
                doctype='<?xml version="1.0" encoding="utf-8"?>',
            )

            return xml_string

        except ET.ParseError as e:
            raise ValueError(f"Error parsing candidate config: {e}") from e
        except (AttributeError, KeyError) as e:
            raise ValueError(f"Error processing config: {e}") from e

    def load_config_to_panorama(
        self, entry_names: list[str], entry_type: str
    ) -> list[dict[str, Any]]:
        """Load the configuration to Panorama."""

        connection_config = self.get_connection_config()
        file_name = self._deduce_file_name()

        panorama_responses = []

        for entry_name in entry_names:
            command = f"""<load>
                <config>
                    <partial>
                        <mode>replace</mode>
                        <from-xpath>devices/entry[@name='localhost.localdomain']/{entry_type}/entry[@name='{entry_name}']</from-xpath>
                        <to-xpath>
                            /config/devices/entry[@name='localhost.localdomain']/{entry_type}/entry[@name='{entry_name}']</to-xpath>
                        <from>{file_name}</from>
                    </partial>
                </config>
            </load>
            """
            command = "".join(line.strip() for line in command.splitlines())
            params = {
                "type": "op",
                "cmd": command,
                "key": connection_config["token"],
            }

            if connection_config["ignore_ssl_warnings"]:
                urllib3.disable_warnings(InsecureRequestWarning)

            try:
                response = requests.get(
                    f"{connection_config['panorama_url']}/api/",
                    params=params,
                    verify=not connection_config["ignore_ssl_warnings"],
                    timeout=connection_config["request_timeout"],
                )
                response.raise_for_status()
                panorama_responses.append(
                    {
                        "entry_name": entry_name,
                        "entry_type": entry_type,
                        "status_code": response.status_code,
                        "response": response.text,
                    }
                )
            except SSLError as exc:
                raise ValueError(
                    f"SSL error occurred when connecting to Panorama: {exc}"
                ) from exc
            except RequestsConnectionError as exc:
                raise ValueError(
                    f"Connection error occurred when connecting to Panorama: {exc}"
                ) from exc
            except Timeout as exc:
                raise ValueError(
                    f"Request timeout occurred when connecting to Panorama: {exc}"
                ) from exc

        return panorama_responses

    def pull(self) -> None:
        """Pull the configuration from Panorama."""

        pulled_config = self.pull_candidate_config()
        rendered_config = self.get_rendered_configuration()

        template_names = self.list_item_names_in_xml(rendered_config, "template")
        device_group_names = self.list_item_names_in_xml(
            rendered_config, "device-group"
        )

        extracted_config = self.extract_templates_and_device_groups_from_config(
            pulled_config, template_names, device_group_names
        )

        self.panorama_configuration = extracted_config
        self.save()

    def push(self) -> dict[str, Any]:
        """Push the configuration to Panorama."""

        rendered_configuration = self.get_rendered_configuration()
        if not rendered_configuration:
            raise ValueError("Rendered configuration is empty.")

        template_names = self.list_item_names_in_xml(rendered_configuration, "template")
        device_group_names = self.list_item_names_in_xml(
            rendered_configuration, "device-group"
        )

        normalized_configuration, _ = normalize_xml(rendered_configuration)
        push_response_status = self.push_candidate_config(normalized_configuration)
        template_load_responses = self.load_config_to_panorama(
            template_names, "template"
        )
        device_group_load_responses = self.load_config_to_panorama(
            device_group_names, "device-group"
        )

        return {
            "config_push_http_status": push_response_status,
            "config_load_responses": template_load_responses
            + device_group_load_responses,
        }

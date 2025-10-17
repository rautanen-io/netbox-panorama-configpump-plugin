"""Panorama mixin for common Panorama-related functionality."""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any

import requests
import urllib3
from netbox.plugins import get_plugin_config
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, RequestException, SSLError, Timeout
from urllib3.exceptions import InsecureRequestWarning

from netbox_panorama_configpump_plugin import config
from netbox_panorama_configpump_plugin.utils.helpers import (
    extract_matching_xml_by_xpaths,
    list_item_names_in_xml,
    normalize_xml,
)


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

    def load_config_to_panorama(self, xpath_entries: list[str]) -> list[dict[str, Any]]:
        """Load the configuration to Panorama."""

        connection_config = self.get_connection_config()
        file_name = self._deduce_file_name()

        panorama_responses = []

        for to_xpath in xpath_entries:
            if not to_xpath.startswith("/config/"):
                raise ValueError(f"XPath entry must start with '/config/': {to_xpath}")

            # From xpath should be just the path after '/config/':
            from_xpath = f"{to_xpath.replace('/config/', '', 1)}"

            command = f"""<load>
                <config>
                    <partial>
                        <mode>replace</mode>
                        <from-xpath>{from_xpath}</from-xpath>
                        <to-xpath>{to_xpath}</to-xpath>
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
                        "xpath": to_xpath,
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

    def get_deduced_xpath_entries(self) -> None | list[str]:
        """Get the deduced XPath entries."""

        rendered_configuration = self.get_rendered_configuration()
        if not rendered_configuration:
            return []

        normalized_configuration, normalized_configuration_valid = normalize_xml(
            rendered_configuration
        )
        if not normalized_configuration_valid:
            return []

        template_names = list_item_names_in_xml(normalized_configuration, "template")
        device_group_names = list_item_names_in_xml(
            normalized_configuration, "device-group"
        )

        xpath_entries = []
        for entry_type, entry_names in [
            ("template", template_names),
            ("device-group", device_group_names),
        ]:
            for entry_name in entry_names:
                # pylint: disable=line-too-long
                xpath = f"/config/devices/entry[@name='localhost.localdomain']/{entry_type}/entry[@name='{entry_name}']"
                xpath_entries.append(xpath)
        return xpath_entries

    def pull(self) -> None:
        """Pull the configuration from Panorama."""

        filtered_panorama_config = extract_matching_xml_by_xpaths(
            self.pull_candidate_config(), self.get_xpath_entries()
        )
        self.panorama_configuration = filtered_panorama_config
        self.save()

    def push(self) -> dict[str, Any]:
        """Push the configuration to Panorama."""

        rendered_configuration = self.get_rendered_configuration()
        if not rendered_configuration:
            raise ValueError("Rendered configuration is empty.")

        normalized_configuration, normalized_configuration_valid = normalize_xml(
            rendered_configuration
        )
        if not normalized_configuration_valid:
            raise ValueError("Configuration is invalid.")

        push_response_status = self.push_candidate_config(normalized_configuration)
        load_responses = self.load_config_to_panorama(self.get_xpath_entries())

        return {
            "config_push_http_status": push_response_status,
            "config_load_responses": load_responses,
        }

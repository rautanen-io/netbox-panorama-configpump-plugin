"""Panorama mixin for common Panorama-related functionality."""

from __future__ import annotations

import datetime
import re
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from typing import Any
from xml.parsers.expat import ExpatError

import requests
import urllib3
import xmltodict
from netbox.plugins import get_plugin_config
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, RequestException, SSLError, Timeout
from urllib3.exceptions import InsecureRequestWarning

from netbox_panorama_configpump_plugin import config
from netbox_panorama_configpump_plugin.utils.helpers import (
    extract_matching_xml_by_xpaths,
    extract_strings_from_nested,
    list_item_names_in_xml,
    normalize_xml,
    sanitize_nested_values,
)


class Status(Enum):
    """Status of a Panorama operation."""

    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"


@dataclass
class PanoramaLogEntry:
    """Log entry for a Panorama operation."""

    status: Status
    http_status_code: int | None
    call_type: str
    response: str
    change_id: str
    timestamp: datetime.datetime


class PanoramaLogger:
    """Logger for Panorama messages."""

    def __init__(self):
        self.change_id = str(uuid.uuid4())
        self.entries: list[PanoramaLogEntry] = []

    def log(
        self,
        status: Status,
        http_status_code: int | None,
        call_type: str,
        response: str,
    ):
        """Log a message."""

        self.entries.append(
            PanoramaLogEntry(
                status,
                http_status_code,
                call_type,
                response,
                self.change_id,
                datetime.datetime.now(datetime.timezone.utc),
            )
        )

    def to_sanitized_dict(self) -> list[dict[str, Any]]:
        """Convert the log entries to a dictionary list."""
        log_entries = []
        for e in self.entries:
            log_entries.append(
                {
                    "status": e.status.value.upper(),
                    "http_status_code": e.http_status_code,
                    "call_type": e.call_type,
                    "response": e.response,
                    "change_id": e.change_id,
                    "timestamp": str(e.timestamp.isoformat()),
                }
            )
        return sanitize_nested_values(log_entries)


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

    def _get_connection_config(self) -> dict[str, Any]:
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

    def _load_partial_config(self, panorama_logger: PanoramaLogger) -> bool:
        """Load the partial configuration to Panorama."""

        file_name = self._deduce_file_name()
        for to_xpath in self.get_xpath_entries():

            if not to_xpath.startswith("/config/"):
                raise ValueError(f"XPath entry must start with '/config/': {to_xpath}")

            # From xpath should be just the path after '/config/':
            from_xpath = f"{to_xpath.replace('/config/', '', 1)}"

            cmd = f"""<load>
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
            cmd = "".join(line.strip() for line in cmd.splitlines())
            http_status_code, response = self._panorama_get(
                {
                    "type": "op",
                    "cmd": cmd,
                }
            )

            partial_config_load_result = self._parse_panorama_response(
                panorama_logger,
                "load partial configuration",
                http_status_code,
                response,
                extra=to_xpath,
            )

            if not partial_config_load_result["status"]:
                return False

        return True

    def _get_deduced_xpath_entries(self) -> list[str]:
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

    def _panorama_get(self, kwargs: dict[str, str]) -> tuple[int, str]:
        """HTTP GET request to Panorama."""

        connection_config = self._get_connection_config()

        params = {
            **kwargs,
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
            return response.status_code, response.text

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
        except Exception as exc:
            raise ValueError(
                f"Unexpected error occurred when connecting to Panorama: {exc}"
            ) from exc

    def _panorama_post(
        self, request_type: str, category: str, message: str
    ) -> tuple[int, str]:
        """HTTP POST request to Panorama."""

        connection_config = self._get_connection_config()

        url = (
            connection_config["panorama_url"] + "/api/"
            f"""?type={request_type}&category={category}"""
            f"""&key={connection_config["token"]}"""
        )

        if connection_config["ignore_ssl_warnings"]:
            urllib3.disable_warnings(InsecureRequestWarning)

        try:
            file_obj = BytesIO(message.encode("utf-8"))
            file_name = self._deduce_file_name()
            files = {"file": (file_name, file_obj, "application/xml")}

            response = requests.post(
                url,
                files=files,
                verify=not connection_config["ignore_ssl_warnings"],
                timeout=connection_config["request_timeout"],
            )
            response.raise_for_status()
            return response.status_code, response.text

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
        except Exception as exc:
            raise ValueError(
                f"Unexpected error occurred when connecting to Panorama: {exc}"
            ) from exc

    def _check_pending_changes(
        self, panorama_logger: PanoramaLogger, http_status_code: int, response: str
    ) -> bool:
        """Check if there are pending changes."""

        call_type = "check pending changes"

        try:
            data = xmltodict.parse(response)
            response_dict = data.get("response") or {}
            result = response_dict.get("result")

            if not result or not isinstance(result, str):
                panorama_logger.log(
                    Status.FAILURE, http_status_code, call_type, "invalid result format"
                )
                return True
            if result.strip().lower() == "yes":
                panorama_logger.log(
                    Status.FAILURE, http_status_code, call_type, "pending changes found"
                )
                return True
            panorama_logger.log(
                Status.SUCCESS, http_status_code, call_type, "no pending changes found"
            )
            return False
        except ExpatError as e:
            panorama_logger.log(Status.FAILURE, None, call_type, f"Invalid XML: {e}")
            return True
        # pylint: disable=broad-exception-caught
        except Exception as e:
            panorama_logger.log(
                Status.FAILURE, None, call_type, f"Unexpected error: {e}"
            )
            return True

    def _parse_panorama_response(
        self,
        panorama_logger: PanoramaLogger,
        call_type: str,
        http_status_code: int,
        response: str,
        extra: str | None = None,
    ) -> dict[str, Any]:
        """Parse the panorama response."""

        result_dict = {}
        commit_job_id = None

        try:
            data = xmltodict.parse(response)
            response_dict = data.get("response") or {}

            # Status:
            status = response_dict.get("@status")

            # Line messages:
            msg = response_dict.get("msg")
            if isinstance(msg, dict):
                line_messages_raw = msg.get("line")
            else:
                line_messages_raw = msg
            line_messages = extract_strings_from_nested(line_messages_raw)

            # Result messages and possible job ID:
            result = response_dict.get("result")
            result_messages = extract_strings_from_nested(result)
            if isinstance(result, dict):
                # Commit job ID:
                commit_job_id = result.get("job")
                if commit_job_id:
                    result_dict["commit_job_id"] = commit_job_id

            messages = " ".join(
                [message for message in [line_messages, result_messages] if message]
                or ["empty message"]
            )
            if extra:
                messages += f" {extra}"

            # Status missing:
            if not status or not isinstance(status, str):
                panorama_logger.log(
                    Status.FAILURE, http_status_code, call_type, "invalid status format"
                )
                result_dict["status"] = False
                return result_dict

            # Success:
            if status.strip().lower() == "success":
                panorama_logger.log(
                    Status.SUCCESS, http_status_code, call_type, messages
                )
                result_dict["status"] = True
                return result_dict

            # Failure (e.g. lock already taken):
            panorama_logger.log(Status.FAILURE, http_status_code, call_type, messages)
            result_dict["status"] = False
            return result_dict

        except ExpatError as e:
            panorama_logger.log(Status.FAILURE, None, call_type, f"Invalid XML: {e}")
            result_dict["status"] = False
            return result_dict
        # pylint: disable=broad-exception-caught
        except Exception as e:
            panorama_logger.log(
                Status.FAILURE, None, call_type, f"Unexpected error: {e}"
            )
            result_dict["status"] = False
            return result_dict

    # pylint: disable=line-too-long
    def _remove_locks_and_export(self, panorama_logger: PanoramaLogger) -> bool:
        """Remove the config or commit lock and export the configuration."""

        # Remove commit lock:
        remove_commit_lock_result = self._parse_panorama_response(
            panorama_logger,
            "remove commit lock",
            *self._panorama_get(
                {
                    "type": "op",
                    "cmd": "<request><commit-lock><remove></remove></commit-lock></request>",
                },
            ),
        )

        # Remove config lock:
        remove_config_lock_result = self._parse_panorama_response(
            panorama_logger,
            "remove config lock",
            *self._panorama_get(
                {
                    "type": "op",
                    "cmd": "<request><config-lock><remove></remove></config-lock></request>",
                },
            ),
        )

        export_configuration_ok = self._export_configuration(panorama_logger)

        return (
            remove_commit_lock_result["status"]
            and remove_config_lock_result["status"]
            and export_configuration_ok
        )

    def _revert_remove_locks_and_export(self, panorama_logger: PanoramaLogger) -> bool:
        """Revert the configuration and remove the locks."""

        revert_config_result = self._parse_panorama_response(
            panorama_logger,
            "revert configuration",
            *self._panorama_get(
                {
                    "type": "op",
                    "cmd": "<revert><config></config></revert>",
                },
            ),
        )
        remove_locks_ok = self._remove_locks_and_export(panorama_logger)

        return revert_config_result["status"] and remove_locks_ok

    def _poll_show_jobs(
        self, panorama_logger: PanoramaLogger, commit_job_id: str
    ) -> bool:
        """Poll for pending changes."""

        commit_poll_attempts = get_plugin_config(
            "netbox_panorama_configpump_plugin",
            "commit_poll_attempts",
            default=config.default_settings["commit_poll_attempts"],
        )
        commit_poll_interval = get_plugin_config(
            "netbox_panorama_configpump_plugin",
            "commit_poll_interval",
            default=config.default_settings["commit_poll_interval"],
        )
        call_type = "show jobs"
        http_status_code = 0

        try:
            for _ in range(commit_poll_attempts):
                time.sleep(commit_poll_interval)

                http_status_code, response = self._panorama_get(
                    {
                        "type": "op",
                        "cmd": f"<show><jobs><id>{commit_job_id}</id></jobs></show>",
                    },
                )

                data = xmltodict.parse(response)
                response_dict = data.get("response") or {}

                # Status:
                status = response_dict.get("@status")
                if not isinstance(status, str) or status.strip().lower() != "success":
                    panorama_logger.log(
                        Status.FAILURE,
                        http_status_code,
                        call_type,
                        f"Commit job '{commit_job_id}' returned unknown status {status}",
                    )
                    break

                # Trying to read response.result.job.result:
                result = response_dict.get("result")
                if not isinstance(result, dict):
                    continue

                job = result.get("job")
                if not isinstance(job, dict):
                    continue

                job_result = job.get("result")
                if not isinstance(job_result, str):
                    continue

                progress = job.get("progress")
                if not isinstance(progress, str):
                    continue

                if job_result.strip().lower() != "ok":
                    panorama_logger.log(
                        Status.PENDING,
                        http_status_code,
                        call_type,
                        f"Commit job progress: {progress}%",
                    )
                    continue

                panorama_logger.log(
                    Status.SUCCESS,
                    http_status_code,
                    call_type,
                    f"Commit job '{commit_job_id}' completed successfully",
                )
                return True

            panorama_logger.log(
                Status.FAILURE,
                http_status_code,
                call_type,
                "Job did not complete on time",
            )
            return False

        except ExpatError as e:
            panorama_logger.log(Status.FAILURE, None, call_type, f"Invalid XML: {e}")
            return False
        # pylint: disable=broad-exception-caught
        except Exception as e:
            panorama_logger.log(
                Status.FAILURE, None, call_type, f"Unexpected error: {e}"
            )
            return False

    def _export_configuration(self, panorama_logger: PanoramaLogger) -> bool:
        """Export the configuration from Panorama."""

        http_status_code, response = self._panorama_get(
            {
                "type": "export",
                "category": "configuration",
            }
        )
        if http_status_code != 200:
            panorama_logger.log(
                Status.FAILURE,
                http_status_code,
                "export configuration",
                "HTTP status code is not 200",
            )
            return False

        filtered_panorama_config = extract_matching_xml_by_xpaths(
            response, self.get_xpath_entries()
        )
        self.panorama_configuration = filtered_panorama_config
        self.save()

        panorama_logger.log(
            Status.SUCCESS,
            http_status_code,
            "export configuration",
            "Configuration exported successfully",
        )
        return True

    def _locks_exist(self, panorama_logger: PanoramaLogger, lock_type: str) -> bool:
        """Check if there are locks."""

        call_type = f"show {lock_type} locks"

        try:
            http_status_code, response = self._panorama_get(
                {
                    "type": "op",
                    "cmd": f"<show><{lock_type}-locks></{lock_type}-locks></show>",
                },
            )

            data = xmltodict.parse(response)
            response_dict = data.get("response") or {}

            status = response_dict.get("@status")
            if not isinstance(status, str) or status.strip().lower() != "success":
                panorama_logger.log(
                    Status.FAILURE,
                    http_status_code,
                    call_type,
                    f"Show {lock_type} locks returned unknown status {status}",
                )
                return True

            result = response_dict.get("result")
            if not isinstance(result, dict):
                panorama_logger.log(
                    Status.FAILURE,
                    http_status_code,
                    call_type,
                    "Unknown result format",
                )
                return True

            locks = result.get(f"{lock_type}-locks")
            if locks:
                panorama_logger.log(
                    Status.FAILURE,
                    http_status_code,
                    call_type,
                    "Locks exist",
                )
                return True

            panorama_logger.log(
                Status.SUCCESS,
                http_status_code,
                call_type,
                "No locks exist",
            )
            return False

        except ExpatError as e:
            panorama_logger.log(Status.FAILURE, None, call_type, f"Invalid XML: {e}")
            return True
        # pylint: disable=broad-exception-caught
        except Exception as e:
            panorama_logger.log(
                Status.FAILURE, None, call_type, f"Unexpected error: {e}"
            )
            return True

    def pull(self, panorama_logger: PanoramaLogger) -> bool:
        """Pull the configuration from Panorama."""

        return self._export_configuration(panorama_logger)

    def push(self, panorama_logger: PanoramaLogger) -> bool:
        """Push the configuration to Panorama."""

        netbox_message = f"NetBox change ID: {panorama_logger.change_id}"

        # In case something weird happens, we try to remove the locks and export the latest config.
        try:
            # Pending changes?
            pending_changes_found = self._check_pending_changes(
                panorama_logger,
                *self._panorama_get(
                    {
                        "type": "op",
                        "cmd": "<check><pending-changes></pending-changes></check>",
                    },
                ),
            )
            if pending_changes_found:
                self._export_configuration(panorama_logger)
                return False

            # Show commit locks:
            commit_locks_exist = self._locks_exist(panorama_logger, "commit")
            if commit_locks_exist:
                self._export_configuration(panorama_logger)
                return False

            # Show config locks:
            config_locks_exist = self._locks_exist(panorama_logger, "config")
            if config_locks_exist:
                self._export_configuration(panorama_logger)
                return False

            # Take config lock:
            config_lock_result = self._parse_panorama_response(
                panorama_logger,
                "add config lock",
                *self._panorama_get(
                    {
                        "type": "op",
                        "cmd": f"<request><config-lock><add><comment>{netbox_message}</comment></add></config-lock></request>",
                    },
                ),
            )
            if not config_lock_result["status"]:
                self._remove_locks_and_export(panorama_logger)
                return False

            # Take commit lock:
            commit_lock_result = self._parse_panorama_response(
                panorama_logger,
                "add commit lock",
                *self._panorama_get(
                    {
                        "type": "op",
                        "cmd": f"<request><commit-lock><add><comment>{netbox_message}</comment></add></commit-lock></request>",
                    },
                ),
            )
            if not commit_lock_result["status"]:
                self._remove_locks_and_export(panorama_logger)
                return False

            # Pending changes?
            pending_changes_found = self._check_pending_changes(
                panorama_logger,
                *self._panorama_get(
                    {
                        "type": "op",
                        "cmd": "<check><pending-changes></pending-changes></check>",
                    },
                ),
            )
            if pending_changes_found:
                self._remove_locks_and_export(panorama_logger)
                return False

            # Import config:
            rendered_configuration = self.get_rendered_configuration()
            if not rendered_configuration:
                raise ValueError("Rendered configuration is empty.")

            normalized_configuration, normalized_configuration_valid = normalize_xml(
                rendered_configuration
            )
            if not normalized_configuration_valid:
                raise ValueError("Configuration is invalid.")

            import_config_result = self._parse_panorama_response(
                panorama_logger,
                "import configuration",
                *self._panorama_post(
                    "import",
                    "configuration",
                    normalized_configuration,
                ),
            )
            if not import_config_result["status"]:
                self._remove_locks_and_export(panorama_logger)
                return False

        except ValueError as value_error:
            panorama_logger.log(
                Status.FAILURE,
                None,
                "Unexpected error.",
                str(value_error),
            )
            try:
                self._remove_locks_and_export(panorama_logger)
            # pylint: disable=broad-exception-caught
            except Exception as e:
                panorama_logger.log(
                    Status.FAILURE,
                    None,
                    "Unknown error. Tried to remove locks and export latest config but failed.",
                    str(e),
                )
            return False

        # In case something weird happens, in addition to removing the locks and exporting the
        # latest config, we also try to revert to the latest config.
        try:
            # Load partial config:
            load_partial_config_ok = self._load_partial_config(panorama_logger)
            if not load_partial_config_ok:
                self._revert_remove_locks_and_export(panorama_logger)
                return False

            # Full commit:
            commit_result = self._parse_panorama_response(
                panorama_logger,
                "commit",
                *self._panorama_get(
                    {
                        "type": "commit",
                        "cmd": f"<commit><description>{netbox_message}</description></commit>",
                    },
                ),
            )
            if not commit_result["status"] or not commit_result.get("commit_job_id"):
                self._revert_remove_locks_and_export(panorama_logger)
                return False

            # Poll pending changes:
            commit_job_completed = self._poll_show_jobs(
                panorama_logger, commit_result.get("commit_job_id")
            )
            if not commit_job_completed:
                self._revert_remove_locks_and_export(panorama_logger)
                return False

            export_configuration_ok = self._export_configuration(panorama_logger)
            return export_configuration_ok

        except ValueError as value_error:
            panorama_logger.log(
                Status.FAILURE,
                None,
                "Unexpected error.",
                str(value_error),
            )
            try:
                self._revert_remove_locks_and_export(panorama_logger)
            # pylint: disable=broad-exception-caught
            except Exception as e:
                panorama_logger.log(
                    Status.FAILURE,
                    None,
                    (
                        "Unknown error. Tried to revert to the latest config, "
                        "remove locks and export the latest config but failed."
                    ),
                    str(e),
                )
            return False

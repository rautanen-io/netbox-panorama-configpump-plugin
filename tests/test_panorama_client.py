"""Test panorama client."""

# pylint: disable=missing-function-docstring, missing-class-docstring


import os
from unittest.mock import Mock, patch

from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Platform, Site
from django.test import TestCase
from extras.models import ConfigTemplate
from requests import HTTPError, RequestException, Timeout
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import SSLError

from netbox_panorama_configpump_plugin.connection.models import Connection
from netbox_panorama_configpump_plugin.connection_template.models import (
    ConnectionTemplate,
)
from netbox_panorama_configpump_plugin.device_config_sync_status.models import (
    DeviceConfigSyncStatus,
)


@patch(
    "netbox_panorama_configpump_plugin.device_config_sync_status.panorama.get_plugin_config"
)
class PanoramaClientTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.connection_template1 = ConnectionTemplate.objects.create(
            name="Template A",
            panorama_url="https://panorama.example.com",
            token_key="TOKEN_KEY1",
            request_timeout=1234,
            file_name_prefix="panorama-netbox",
        )
        self.device_role1 = DeviceRole.objects.create(name="Device Role A")
        self.manufacturer1 = Manufacturer.objects.create(name="Manufacturer A")
        self.device_type1 = DeviceType.objects.create(
            model="Device Type A", manufacturer=self.manufacturer1
        )
        self.site1 = Site.objects.create(name="Site A")
        self.config_template = ConfigTemplate.objects.create(
            name="Template A",
            template_code="some code",
        )
        self.platform1 = Platform.objects.create(
            name="PanOS", config_template=self.config_template
        )
        self.device1 = Device.objects.create(
            name="Device A",
            role=self.device_role1,
            device_type=self.device_type1,
            site=self.site1,
            platform=self.platform1,
        )
        self.connection1 = Connection.objects.create(
            name="Connection A",
            connection_template=self.connection_template1,
        )
        self.connection1.add_device(self.device1)
        self.device_config_sync_status1 = DeviceConfigSyncStatus.objects.filter(
            device=self.device1
        ).first()

    def test_get_connection_config_with_missing_token(self, mock_get_plugin_config):

        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {}.get(
            key, default
        )
        with self.assertRaises(ValueError) as context:
            self.device_config_sync_status1.get_connection_config()
        self.assertEqual(
            context.exception.args[0],
            "Token key 'TOKEN_KEY1' not found in plugin configuration.",
        )

    def test_get_connection_config(self, mock_get_plugin_config):

        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {
            "tokens": {
                "TOKEN_KEY1": "token1",
                "TOKEN_KEY2": "token2",
            },
            "ignore_ssl_warnings": True,
        }.get(key, default)

        config = self.device_config_sync_status1.get_connection_config()
        self.assertEqual(config["token"], "token1")
        self.assertEqual(config["request_timeout"], 1234)
        self.assertEqual(config["panorama_url"], "https://panorama.example.com")
        self.assertEqual(config["ignore_ssl_warnings"], True)

    @patch(
        "netbox_panorama_configpump_plugin.device_config_sync_status.panorama.requests.get"
    )
    def test_pull_candidate_config(self, mock_requests_get, mock_get_plugin_config):

        # Mock the plugin configuration
        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {
            "tokens": {
                "TOKEN_KEY1": "token1",
                "TOKEN_KEY2": "token2",
            },
            "ignore_ssl_warnings": True,
        }.get(key, default)

        # Mock the requests response
        mock_response = Mock()
        mock_response.text = "<?xml version='1.0'?><config>test configuration</config>"
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        panorama_configuration = self.device_config_sync_status1.pull_candidate_config()

        self.assertEqual(
            panorama_configuration,
            "<?xml version='1.0'?><config>test configuration</config>",
        )

        # Verify the requests.get was called with correct parameters
        mock_requests_get.assert_called_once_with(
            "https://panorama.example.com/api/",
            params={
                "type": "export",
                "category": "configuration",
                "key": "token1",
            },
            verify=False,  # ignore_ssl_warnings is True
            timeout=1234,
        )

    @patch(
        "netbox_panorama_configpump_plugin.device_config_sync_status.panorama.requests.get"
    )
    def test_pull_candidate_config_ssl_error(
        self, mock_requests_get, mock_get_plugin_config
    ):
        """Test SSL error handling."""
        # Mock the plugin configuration
        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {
            "tokens": {"TOKEN_KEY1": "token1"},
            "ignore_ssl_warnings": False,
        }.get(key, default)

        # Mock SSL error
        mock_requests_get.side_effect = SSLError("SSL certificate verification failed")

        with self.assertRaises(ValueError) as context:
            self.device_config_sync_status1.pull_candidate_config()

        self.assertIn(
            "SSL error occurred when connecting to Panorama", str(context.exception)
        )
        self.assertIn("SSL certificate verification failed", str(context.exception))

    @patch(
        "netbox_panorama_configpump_plugin.device_config_sync_status.panorama.requests.get"
    )
    def test_pull_candidate_config_connection_error(
        self, mock_requests_get, mock_get_plugin_config
    ):
        """Test connection error handling."""
        # Mock the plugin configuration
        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {
            "tokens": {"TOKEN_KEY1": "token1"},
            "ignore_ssl_warnings": True,
        }.get(key, default)

        # Mock connection error
        mock_requests_get.side_effect = RequestsConnectionError("Connection refused")

        with self.assertRaises(ValueError) as context:
            self.device_config_sync_status1.pull_candidate_config()

        self.assertIn(
            "Connection error occurred when connecting to Panorama",
            str(context.exception),
        )
        self.assertIn("Connection refused", str(context.exception))

    @patch(
        "netbox_panorama_configpump_plugin.device_config_sync_status.panorama.requests.get"
    )
    def test_pull_candidate_config_timeout_error(
        self, mock_requests_get, mock_get_plugin_config
    ):
        """Test timeout error handling."""
        # Mock the plugin configuration
        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {
            "tokens": {"TOKEN_KEY1": "token1"},
            "ignore_ssl_warnings": True,
        }.get(key, default)

        # Mock timeout error
        mock_requests_get.side_effect = Timeout("Request timed out")

        with self.assertRaises(ValueError) as context:
            self.device_config_sync_status1.pull_candidate_config()

        self.assertIn(
            "Request timeout occurred when connecting to Panorama",
            str(context.exception),
        )
        self.assertIn("Request timed out", str(context.exception))

    @patch(
        "netbox_panorama_configpump_plugin.device_config_sync_status.panorama.requests.get"
    )
    def test_pull_candidate_config_http_error(
        self, mock_requests_get, mock_get_plugin_config
    ):
        """Test HTTP error handling."""
        # Mock the plugin configuration
        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {
            "tokens": {"TOKEN_KEY1": "token1"},
            "ignore_ssl_warnings": True,
        }.get(key, default)

        # Mock HTTP error (e.g., 404, 500)
        mock_requests_get.side_effect = HTTPError("404 Client Error: Not Found")

        with self.assertRaises(ValueError) as context:
            self.device_config_sync_status1.pull_candidate_config()

        self.assertIn(
            "HTTP error occurred when connecting to Panorama", str(context.exception)
        )
        self.assertIn("404 Client Error: Not Found", str(context.exception))

    @patch(
        "netbox_panorama_configpump_plugin.device_config_sync_status.panorama.requests.get"
    )
    def test_pull_candidate_config_general_request_error(
        self, mock_requests_get, mock_get_plugin_config
    ):
        """Test general request error handling."""
        # Mock the plugin configuration
        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {
            "tokens": {"TOKEN_KEY1": "token1"},
            "ignore_ssl_warnings": True,
        }.get(key, default)

        # Mock general request error
        mock_requests_get.side_effect = RequestException("Unknown request error")

        with self.assertRaises(ValueError) as context:
            self.device_config_sync_status1.pull_candidate_config()

        self.assertIn(
            "Request error occurred when connecting to Panorama", str(context.exception)
        )
        self.assertIn("Unknown request error", str(context.exception))

    @patch(
        "netbox_panorama_configpump_plugin.device_config_sync_status.panorama.requests.post"
    )
    def test_push_candidate_config(self, mock_requests_post, mock_get_plugin_config):
        """Test push configuration."""
        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {
            "tokens": {
                "TOKEN_KEY1": "token1",
                "TOKEN_KEY2": "token2",
            },
            "ignore_ssl_warnings": True,
        }.get(key, default)

        # Mock the requests response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_requests_post.return_value = mock_response

        response = self.device_config_sync_status1.push_candidate_config(
            self.device_config_sync_status1.get_rendered_configuration()
        )

        # Assertions
        self.assertEqual(response, 200)

        # Verify the requests.post was called with correct parameters
        mock_requests_post.assert_called_once()
        call_args = mock_requests_post.call_args
        self.assertIn("files", call_args.kwargs)
        self.assertEqual(
            call_args.kwargs["verify"], False
        )  # ignore_ssl_warnings is True
        self.assertEqual(call_args.kwargs["timeout"], 1234)

    @patch(
        "netbox_panorama_configpump_plugin.device_config_sync_status.panorama.requests.post"
    )
    def test_push_configuration_ssl_error(
        self, mock_requests_post, mock_get_plugin_config
    ):
        """Test SSL error handling in push configuration."""
        # Mock the plugin configuration
        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {
            "tokens": {"TOKEN_KEY1": "token1"},
            "ignore_ssl_warnings": False,
        }.get(key, default)

        # Mock SSL error
        mock_requests_post.side_effect = SSLError("SSL certificate verification failed")

        with self.assertRaises(ValueError) as context:
            self.device_config_sync_status1.push_candidate_config(
                self.device_config_sync_status1.get_rendered_configuration()
            )

        self.assertIn(
            "SSL error occurred when connecting to Panorama", str(context.exception)
        )
        self.assertIn("SSL certificate verification failed", str(context.exception))

    @patch(
        "netbox_panorama_configpump_plugin.device_config_sync_status.panorama.requests.post"
    )
    def test_push_configuration_connection_error(
        self, mock_requests_post, mock_get_plugin_config
    ):
        """Test connection error handling in push configuration."""
        # Mock the plugin configuration
        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {
            "tokens": {"TOKEN_KEY1": "token1"},
            "ignore_ssl_warnings": True,
        }.get(key, default)

        # Mock connection error
        mock_requests_post.side_effect = RequestsConnectionError("Connection refused")

        with self.assertRaises(ValueError) as context:
            self.device_config_sync_status1.push_candidate_config(
                self.device_config_sync_status1.get_rendered_configuration()
            )

        self.assertIn(
            "Connection error occurred when connecting to Panorama",
            str(context.exception),
        )
        self.assertIn("Connection refused", str(context.exception))

    @patch(
        "netbox_panorama_configpump_plugin.device_config_sync_status.panorama.requests.post"
    )
    def test_push_configuration_timeout_error(
        self, mock_requests_post, mock_get_plugin_config
    ):
        """Test timeout error handling in push configuration."""
        # Mock the plugin configuration
        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {
            "tokens": {"TOKEN_KEY1": "token1"},
            "ignore_ssl_warnings": True,
        }.get(key, default)

        # Mock timeout error
        mock_requests_post.side_effect = Timeout("Request timed out")

        with self.assertRaises(ValueError) as context:
            self.device_config_sync_status1.push_candidate_config(
                self.device_config_sync_status1.get_rendered_configuration()
            )

        self.assertIn(
            "Request timeout occurred when connecting to Panorama",
            str(context.exception),
        )
        self.assertIn("Request timed out", str(context.exception))

    @patch(
        "netbox_panorama_configpump_plugin.device_config_sync_status.panorama.requests.post"
    )
    def test_push_configuration_http_error(
        self, mock_requests_post, mock_get_plugin_config
    ):
        """Test HTTP error handling in push configuration."""
        # Mock the plugin configuration
        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {
            "tokens": {"TOKEN_KEY1": "token1"},
            "ignore_ssl_warnings": True,
        }.get(key, default)

        # Mock HTTP error (e.g., 404, 500)
        mock_requests_post.side_effect = HTTPError(
            "500 Server Error: Internal Server Error"
        )

        with self.assertRaises(ValueError) as context:
            self.device_config_sync_status1.push_candidate_config(
                self.device_config_sync_status1.get_rendered_configuration()
            )

        self.assertIn(
            "HTTP error occurred when connecting to Panorama", str(context.exception)
        )
        self.assertIn("500 Server Error: Internal Server Error", str(context.exception))

    @patch(
        "netbox_panorama_configpump_plugin.device_config_sync_status.panorama.requests.post"
    )
    def test_push_configuration_general_request_error(
        self, mock_requests_post, mock_get_plugin_config
    ):
        """Test general request error handling in push configuration."""
        # Mock the plugin configuration
        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {
            "tokens": {"TOKEN_KEY1": "token1"},
            "ignore_ssl_warnings": True,
        }.get(key, default)

        # Mock general request error
        mock_requests_post.side_effect = RequestException("Unknown request error")

        with self.assertRaises(ValueError) as context:
            self.device_config_sync_status1.push_candidate_config(
                self.device_config_sync_status1.get_rendered_configuration()
            )

        self.assertIn(
            "Request error occurred when connecting to Panorama", str(context.exception)
        )
        self.assertIn("Unknown request error", str(context.exception))

    def test_list_item_names_in_xml(self, _):

        test_data_dir = os.path.join(os.path.dirname(__file__), "test_data")
        config1_path = os.path.join(test_data_dir, "panorama_config1.xml")
        with open(config1_path, "r", encoding="utf-8") as f:
            panorama_config1 = f.read()

        found_items = self.device_config_sync_status1.list_item_names_in_xml(
            panorama_config1, "template"
        )
        self.assertEqual(found_items, ["Netbox", "Netbox2"])

        found_items = self.device_config_sync_status1.list_item_names_in_xml(
            panorama_config1, "device-group"
        )
        self.assertEqual(found_items, ["Netbox", "Netbox2"])

        config1_path = os.path.join(test_data_dir, "panorama_config4.xml")
        with open(config1_path, "r", encoding="utf-8") as f:
            panorama_config1 = f.read()

        found_items = self.device_config_sync_status1.list_item_names_in_xml(
            panorama_config1, "template"
        )
        self.assertEqual(found_items, ["MyTemplate1", "MyTemplate2"])

        found_items = self.device_config_sync_status1.list_item_names_in_xml(
            panorama_config1, "device-group"
        )
        self.assertEqual(found_items, ["MyTemplate1", "MyTemplate2"])

    def test_list_item_names_in_xml_invalid_xml(self, _):
        """Test error handling for invalid XML."""
        invalid_xml = "<invalid><unclosed>tag"

        with self.assertRaises(ValueError) as context:
            self.device_config_sync_status1.list_item_names_in_xml(
                invalid_xml, "template"
            )

        self.assertIn("Error parsing XML config", str(context.exception))

    def test_list_item_names_in_xml_malformed_xml_structure(self, _):
        """Test error handling for malformed XML structure."""
        # XML that parses but has unexpected structure
        malformed_xml = """<?xml version="1.0"?>
        <config>
            <devices>
                <entry>
                    <template>
                        <!-- Missing 'name' attribute -->
                        <entry></entry>
                    </template>
                </entry>
            </devices>
        </config>"""

        # This should not raise an error since the method handles missing names gracefully
        found_items = self.device_config_sync_status1.list_item_names_in_xml(
            malformed_xml, "template"
        )
        self.assertEqual(found_items, [])

    def test_list_item_names_in_xml_empty_xml(self, _):
        """Test error handling for empty XML."""
        empty_xml = ""

        with self.assertRaises(ValueError) as context:
            self.device_config_sync_status1.list_item_names_in_xml(
                empty_xml, "template"
            )

        self.assertIn("Error parsing XML config", str(context.exception))

    def test_list_item_names_in_xml_non_xml_string(self, _):
        """Test error handling for non-XML string."""
        non_xml = "This is not XML at all"

        with self.assertRaises(ValueError) as context:
            self.device_config_sync_status1.list_item_names_in_xml(non_xml, "template")

        self.assertIn("Error parsing XML config", str(context.exception))

    def test_list_item_names_in_xml_missing_devices_section(self, _):
        """Test handling of XML without devices section."""
        xml_without_devices = """<?xml version="1.0"?>
        <config>
            <other-section>
                <entry name="test">value</entry>
            </other-section>
        </config>"""

        # Should return empty list, not raise error
        found_items = self.device_config_sync_status1.list_item_names_in_xml(
            xml_without_devices, "template"
        )
        self.assertEqual(found_items, [])

    def test_list_item_names_in_xml_missing_item_type_section(self, _):
        """Test handling of XML without the specified item type section."""
        xml_without_template = """<?xml version="1.0"?>
        <config>
            <devices>
                <entry>
                    <device-group>
                        <entry name="test-group">value</entry>
                    </device-group>
                </entry>
            </devices>
        </config>"""

        # Should return empty list when looking for 'template' but only 'device-group' exists
        found_items = self.device_config_sync_status1.list_item_names_in_xml(
            xml_without_template, "template"
        )
        self.assertEqual(found_items, [])

    def test_extract_templates_and_device_groups_from_config(self, _):
        """Test extract templates and device groups from config."""
        test_data_dir = os.path.join(os.path.dirname(__file__), "test_data")
        config1_path = os.path.join(test_data_dir, "panorama_config3.xml")
        with open(config1_path, "r", encoding="utf-8") as f:
            panorama_config1 = f.read()

        new_config = self.device_config_sync_status1.extract_templates_and_device_groups_from_config(
            panorama_config1, ["Netbox", "Netbox2"], ["Netbox", "Netbox2"]
        )

        self.assertNotIn("<readonly>", new_config)
        self.assertNotIn("</readonly>", new_config)

        self.assertIn("<template>", new_config)
        self.assertIn("<device-group>", new_config)
        self.assertIn('<entry name="Netbox">', new_config)
        self.assertIn('<entry name="Netbox2">', new_config)

        config1_path = os.path.join(test_data_dir, "panorama_config4.xml")
        with open(config1_path, "r", encoding="utf-8") as f:
            panorama_config1 = f.read()

        new_config = self.device_config_sync_status1.extract_templates_and_device_groups_from_config(
            panorama_config1,
            ["MyTemplate1", "MyTemplate2"],
            ["MyTemplate1", "MyTemplate2"],
        )

        self.assertNotIn("<readonly>", new_config)
        self.assertNotIn("</readonly>", new_config)

        self.assertIn("<template>", new_config)
        self.assertIn("<device-group>", new_config)
        self.assertIn('<entry name="MyTemplate1">', new_config)
        self.assertIn('<entry name="MyTemplate2">', new_config)

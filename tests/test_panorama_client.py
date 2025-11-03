"""Test panorama client."""

# pylint: disable=missing-function-docstring, missing-class-docstring, line-too-long


import os
import xml.etree.ElementTree as ET
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
from netbox_panorama_configpump_plugin.device_config_sync_status.panorama import (
    PanoramaLogger,
)
from netbox_panorama_configpump_plugin.utils.helpers import (
    extract_matching_xml_by_xpaths,
    list_item_names_in_xml,
    sanitize_nested_values,
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

    # pylint: disable=protected-access
    def test_get_connection_config_with_missing_token(self, mock_get_plugin_config):

        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {}.get(
            key, default
        )
        with self.assertRaises(ValueError) as context:
            self.device_config_sync_status1._get_connection_config()
        self.assertEqual(
            context.exception.args[0],
            "Token key 'TOKEN_KEY1' not found in plugin configuration.",
        )

    # pylint: disable=protected-access
    def test_get_connection_config(self, mock_get_plugin_config):

        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {
            "tokens": {
                "TOKEN_KEY1": "token1",
                "TOKEN_KEY2": "token2",
            },
            "ignore_ssl_warnings": True,
        }.get(key, default)

        config = self.device_config_sync_status1._get_connection_config()
        self.assertEqual(config["token"], "token1")
        self.assertEqual(config["request_timeout"], 1234)
        self.assertEqual(config["panorama_url"], "https://panorama.example.com")
        self.assertEqual(config["ignore_ssl_warnings"], True)

    @patch(
        "netbox_panorama_configpump_plugin.device_config_sync_status.models.DeviceConfigSyncStatus.get_rendered_configuration"
    )
    @patch(
        "netbox_panorama_configpump_plugin.device_config_sync_status.models.DeviceConfigSyncStatus.get_xpath_entries"
    )
    @patch(
        "netbox_panorama_configpump_plugin.device_config_sync_status.panorama.requests.get"
    )
    def test_pull_candidate_config(
        self,
        mock_requests_get,
        mock_get_xpath_entries,
        mock_get_rendered_configuration,
        mock_get_plugin_config,
    ):

        # Mock the rendered configuration to return valid XML
        mock_get_rendered_configuration.return_value = (
            "<config>rendered configs</config>"
        )

        # Mock the xpath entries to return whole document (no filtering)
        mock_get_xpath_entries.return_value = ["/config"]

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
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        self.device_config_sync_status1.pull(PanoramaLogger())
        self.device_config_sync_status1.refresh_from_db()

        # The XML is pretty-printed by etree.tostring with pretty_print=True
        expected_config = "<config>test configuration</config>\n"
        self.assertEqual(
            self.device_config_sync_status1.panorama_configuration,
            expected_config,
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

        message_logger = PanoramaLogger()
        self.device_config_sync_status1.pull(message_logger)

        self.assertEqual(
            message_logger.entries[0].response,
            "SSL error occurred when connecting to Panorama: SSL certificate verification failed",
        )

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

        message_logger = PanoramaLogger()
        self.device_config_sync_status1.pull(message_logger)

        self.assertEqual(
            message_logger.entries[0].response,
            "Connection error occurred when connecting to Panorama: Connection refused",
        )

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

        message_logger = PanoramaLogger()
        self.device_config_sync_status1.pull(message_logger)

        self.assertEqual(
            message_logger.entries[0].response,
            "Request timeout occurred when connecting to Panorama: Request timed out",
        )

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

        message_logger = PanoramaLogger()
        self.device_config_sync_status1.pull(message_logger)

        self.assertEqual(
            message_logger.entries[0].response,
            "HTTP error occurred when connecting to Panorama: 404 Client Error: Not Found",
        )

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

        message_logger = PanoramaLogger()
        self.device_config_sync_status1.pull(message_logger)

        self.assertEqual(
            message_logger.entries[0].response,
            "Request error occurred when connecting to Panorama: Unknown request error",
        )

    # pylint: disable=protected-access
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
            self.device_config_sync_status1._panorama_post(
                "import", "configuration", "<config>test</config>"
            )

        self.assertIn(
            "SSL error occurred when connecting to Panorama", str(context.exception)
        )
        self.assertIn("SSL certificate verification failed", str(context.exception))

    # pylint: disable=protected-access
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
            self.device_config_sync_status1._panorama_post(
                "import", "configuration", "<config>test</config>"
            )

        self.assertIn(
            "Connection error occurred when connecting to Panorama",
            str(context.exception),
        )
        self.assertIn("Connection refused", str(context.exception))

    # pylint: disable=protected-access
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
            self.device_config_sync_status1._panorama_post(
                "import", "configuration", "<config>test</config>"
            )

        self.assertIn(
            "Request timeout occurred when connecting to Panorama",
            str(context.exception),
        )
        self.assertIn("Request timed out", str(context.exception))

    # pylint: disable=protected-access
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
            self.device_config_sync_status1._panorama_post(
                "import", "configuration", "<config>test</config>"
            )

        self.assertIn(
            "HTTP error occurred when connecting to Panorama", str(context.exception)
        )
        self.assertIn("500 Server Error: Internal Server Error", str(context.exception))

    # pylint: disable=protected-access
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
            self.device_config_sync_status1._panorama_post(
                "import", "configuration", "<config>test</config>"
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

        found_items = list_item_names_in_xml(panorama_config1, "template")
        self.assertEqual(found_items, ["Netbox", "Netbox2"])

        found_items = list_item_names_in_xml(panorama_config1, "device-group")
        self.assertEqual(found_items, ["Netbox", "Netbox2"])

        config1_path = os.path.join(test_data_dir, "panorama_config4.xml")
        with open(config1_path, "r", encoding="utf-8") as f:
            panorama_config1 = f.read()

        found_items = list_item_names_in_xml(panorama_config1, "template")
        self.assertEqual(found_items, ["MyTemplate1", "MyTemplate2"])

        found_items = list_item_names_in_xml(panorama_config1, "device-group")
        self.assertEqual(found_items, ["MyTemplate1", "MyTemplate2"])

    def test_list_item_names_in_xml_invalid_xml(self, _):
        """Test error handling for invalid XML."""
        invalid_xml = "<invalid><unclosed>tag"

        with self.assertRaises(ValueError) as context:
            list_item_names_in_xml(invalid_xml, "template")

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
        found_items = list_item_names_in_xml(malformed_xml, "template")
        self.assertEqual(found_items, [])

    def test_list_item_names_in_xml_empty_xml(self, _):
        """Test error handling for empty XML."""
        empty_xml = ""

        with self.assertRaises(ValueError) as context:
            list_item_names_in_xml(empty_xml, "template")

        self.assertIn("Error parsing XML config", str(context.exception))

    def test_list_item_names_in_xml_non_xml_string(self, _):
        """Test error handling for non-XML string."""
        non_xml = "This is not XML at all"

        with self.assertRaises(ValueError) as context:
            list_item_names_in_xml(non_xml, "template")

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
        found_items = list_item_names_in_xml(xml_without_devices, "template")
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
        found_items = list_item_names_in_xml(xml_without_template, "template")
        self.assertEqual(found_items, [])

    # pylint: disable=line-too-long
    def test_extract_matching_xml_by_xpaths(self, _):
        self.maxDiff = 8192  # pylint: disable=invalid-name

        test_data_dir = os.path.join(os.path.dirname(__file__), "test_data")
        config1_path = os.path.join(test_data_dir, "panorama_config1.xml")
        with open(config1_path, "r", encoding="utf-8") as f:
            panorama_config1 = f.read()

        new_config = extract_matching_xml_by_xpaths(
            panorama_config1,
            [
                "/config/devices/entry[@name='localhost.localdomain']/template/entry[@name='Netbox']",
                "/config/devices/entry[@name='localhost.localdomain']/template/entry[@name='Netbox2']",
                "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='Netbox']",
                "/config/devices/entry[@name='localhost.localdomain']/device-group/entry[@name='Netbox2']",
            ],
        )
        self.assertEqual(new_config, panorama_config1)

        new_config = extract_matching_xml_by_xpaths(
            panorama_config1,
            [
                "/config/devices/entry[@name='localhost.localdomain']/template/entry[@name='Netbox']",
            ],
        )
        self.assertEqual(len(new_config), 2678)
        self.assertIn("Netbox", new_config)
        self.assertIn("ethernet1/1.222", new_config)
        self.assertNotIn("Netbox2", new_config)
        self.assertNotIn("ethernet1/3.222", new_config)

    def test_extract_matching_xml_by_xpaths_full_document_slash(self, _):
        """Selecting '/' should return the full document pretty-printed."""
        original = "<config><a><b/></a></config>"
        result = extract_matching_xml_by_xpaths(original, ["/"])

        # Canonicalize by removing whitespace-only text/tails
        def canon(xml: str) -> bytes:
            def strip_ws(e: ET.Element) -> None:
                if e.text and e.text.strip() == "":
                    e.text = ""
                if e.tail and e.tail.strip() == "":
                    e.tail = ""
                for c in list(e):
                    strip_ws(c)

            root = ET.fromstring(xml)
            strip_ws(root)
            return ET.tostring(root)

        self.assertEqual(canon(result), canon(original))

    def test_extract_matching_xml_by_xpaths_full_document_tag(self, _):
        """Selecting '/config' should return the full document pretty-printed."""
        original = "<config><x attr='1'/></config>"
        result = extract_matching_xml_by_xpaths(original, ["/config"])

        def canon(xml: str) -> bytes:
            def strip_ws(e: ET.Element) -> None:
                if e.text and e.text.strip() == "":
                    e.text = ""
                if e.tail and e.tail.strip() == "":
                    e.tail = ""
                for c in list(e):
                    strip_ws(c)

            root = ET.fromstring(xml)
            strip_ws(root)
            return ET.tostring(root)

        self.assertEqual(canon(result), canon(original))

    def test_extract_matching_xml_by_xpaths_trailing_slash_normalization(self, _):
        """Trailing slash in XPath should be treated the same as without it."""
        xml_doc = "<config><a><b/><c/></a></config>"
        with_slash = extract_matching_xml_by_xpaths(xml_doc, ["/config/a/"])
        without_slash = extract_matching_xml_by_xpaths(xml_doc, ["/config/a"])
        # Compare parsed structures
        self.assertEqual(
            ET.tostring(ET.fromstring(with_slash)),
            ET.tostring(ET.fromstring(without_slash)),
        )

    def test_extract_matching_xml_by_xpaths_invalid_xpath(self, _):
        """Invalid XPath should raise ValueError with 'Invalid XPath' in message."""
        xml_doc = "<config><a/></config>"
        with self.assertRaises(ValueError) as ctx:
            extract_matching_xml_by_xpaths(xml_doc, ["///bad["])
        self.assertIn("Invalid XPath", str(ctx.exception))

    def test_extract_matching_xml_by_xpaths_ignore_non_element_results(self, _):
        """Attribute/text XPath results should be ignored (no nodes copied)."""
        xml_doc = "<config><a name='n1'>text</a></config>"
        result = extract_matching_xml_by_xpaths(
            xml_doc, ["/config/a/@name", "/config/a/text()"]
        )
        root = ET.fromstring(result)
        self.assertEqual(root.tag, "config")
        self.assertEqual(list(root), [])

    # pylint: disable=protected-access
    def test_list_changes(self, _):
        """Test has pending changes."""
        message_logger = PanoramaLogger()
        response = (
            """<response status="success"><result><journal>"""
            """<entry><xpath>/config/devices/entry[@name=&#39;localhost.localdomain&#39;]/template/entry[@name=&#39;MyTemplate1&#39;]/config/devices/entry[@name=&#39;localhost.localdomain&#39;]/vsys/entry[@name=&#39;vsys1&#39;]/import/network/interface/member[text()=&#39;ethernet1/1.3&#39;]</xpath><owner>xxx</owner><action> CREATE</action><admin-history>xxx</admin-history><component-type>template</component-type></entry>"""
            """</journal></result></response>"""
        )
        pending_changes_found = self.device_config_sync_status1._list_changes(
            message_logger,
            200,
            response,
        )
        self.assertTrue(pending_changes_found)
        self.assertEqual(message_logger.entries[0].response, "pending changes found")

        message_logger = PanoramaLogger()
        response = """<response status="success"><result></result></response>"""
        pending_changes_found = self.device_config_sync_status1._list_changes(
            message_logger, 200, response
        )
        self.assertFalse(pending_changes_found)
        self.assertEqual(message_logger.entries[0].response, "no pending changes found")

        message_logger = PanoramaLogger()
        response = """<response><result></result></response>"""
        pending_changes_found = self.device_config_sync_status1._list_changes(
            message_logger, 200, response
        )
        self.assertTrue(pending_changes_found)
        self.assertEqual(message_logger.entries[0].response, "invalid status format")

        message_logger = PanoramaLogger()
        response = "broken message"
        nok = self.device_config_sync_status1._list_changes(
            message_logger, 200, response
        )
        self.assertTrue(nok)
        self.assertEqual(
            message_logger.entries[0].response,
            "Invalid XML: syntax error: line 1, column 0",
        )

    # pylint: disable=protected-access
    def test_parse_panorama_response(self, _):
        """Test parse panorama response."""
        response = """<response status="success"><result>Successfully acquired lock. Other administrators will not be able to commit configuration until lock is released by xxx.</result></response>"""
        message_logger = PanoramaLogger()
        result = self.device_config_sync_status1._parse_panorama_response(
            message_logger, "take lock", 200, response
        )
        self.assertTrue(result["status"])
        self.assertEqual(
            message_logger.entries[0].response,
            "Successfully acquired lock. Other administrators will not be able to commit configuration until lock is released by xxx.",
        )

        message_logger = PanoramaLogger()
        response = """<response status="error"><msg><line>Config for scope shared is currently locked by xxx</line></msg></response>"""
        result = self.device_config_sync_status1._parse_panorama_response(
            message_logger, "take lock", 200, response
        )
        self.assertFalse(result["status"])
        self.assertEqual(
            message_logger.entries[0].response,
            "Config for scope shared is currently locked by xxx",
        )

        message_logger = PanoramaLogger()
        response = "<response></response>"
        result = self.device_config_sync_status1._parse_panorama_response(
            message_logger, "take lock", 200, response
        )
        self.assertFalse(result["status"])
        self.assertEqual(
            message_logger.entries[0].response,
            "invalid status format",
        )

        message_logger = PanoramaLogger()
        response = """<response status="success"><result></result></response>"""
        result = self.device_config_sync_status1._parse_panorama_response(
            message_logger, "take lock", 200, response
        )
        self.assertTrue(result["status"])
        self.assertEqual(
            message_logger.entries[0].response,
            "empty message",
        )

        message_logger = PanoramaLogger()
        response = "broken message"
        result = self.device_config_sync_status1._parse_panorama_response(
            message_logger, "take lock", 200, response
        )
        self.assertFalse(result["status"])
        self.assertEqual(
            message_logger.entries[0].response,
            "Invalid XML: syntax error: line 1, column 0",
        )

        # Test nested result message structure
        message_logger = PanoramaLogger()
        response = """<response status="success"><result><msg><line><msg><line>Config loaded from nb-test_device_b.xml</line></msg></line></msg></result></response>"""
        result = self.device_config_sync_status1._parse_panorama_response(
            message_logger, "take lock", 200, response
        )
        self.assertTrue(result["status"])
        self.assertEqual(
            message_logger.entries[0].response,
            "Config loaded from nb-test_device_b.xml",
        )

        # Test plain string msg (not a dict)
        message_logger = PanoramaLogger()
        response = (
            """<response status="error"><msg>Simple error message</msg></response>"""
        )
        result = self.device_config_sync_status1._parse_panorama_response(
            message_logger, "take lock", 200, response
        )
        self.assertFalse(result["status"])
        self.assertEqual(
            message_logger.entries[0].response,
            "Simple error message",
        )

    def test_sanitize_nested_values(self, mock_get_plugin_config):

        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {
            "tokens": {
                "PANO1_TOKEN": "token1",
                "TOKEN_KEY2": "token2",
            },
            "ignore_ssl_warnings": True,
        }.get(key, default)

        nested_values = [
            {
                "call_type": "some key=abcd 0x1234567890 efg",
                "change_id": "some key=abcd 0x1234567890 efg",
                "http_status_code": "some key=abcd 0x1234567890 efg",
                "response": "some key=abcd 0x1234567890 efg",
                "status": "some key=abcd 0x1234567890 efg",
                "timestamp": "some key=abcd 0x1234567890 efg",
            },
        ]

        expected_values = [
            {
                "call_type": "some key=*** 0x*** efg",
                "change_id": "some key=*** 0x*** efg",
                "http_status_code": "some key=*** 0x*** efg",
                "response": "some key=*** 0x*** efg",
                "status": "some key=*** 0x*** efg",
                "timestamp": "some key=*** 0x*** efg",
            }
        ]

        sanitized_values = sanitize_nested_values(nested_values)
        self.assertEqual(sanitized_values, expected_values)

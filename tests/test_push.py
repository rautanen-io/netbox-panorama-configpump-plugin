from unittest.mock import patch

from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Platform, Site
from django.test import TestCase
from extras.models import ConfigContext, ConfigTemplate

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


class PanoramaPushTests(TestCase):

    def setUp(self):

        # Devices:
        self.device_role1 = DeviceRole.objects.create(name="Device Role A")
        self.manufacturer1 = Manufacturer.objects.create(name="Manufacturer A")
        self.device_type1 = DeviceType.objects.create(
            model="Device Type A", manufacturer=self.manufacturer1
        )
        self.site1 = Site.objects.create(name="Site A")
        self.config_template = ConfigTemplate.objects.create(
            name="Template A",
            template_code="some code {{ foo }}",
        )
        self.platform1 = Platform.objects.create(
            name="PanOS", config_template=self.config_template
        )
        context_data1 = ConfigContext.objects.create(
            name="Context A",
            data={"foo": "bar"},
        )
        self.device1 = Device.objects.create(
            name="Device A",
            role=self.device_role1,
            device_type=self.device_type1,
            site=self.site1,
            platform=self.platform1,
        )
        self.device1.local_context_data = context_data1.data
        self.device1.save()
        self.device2 = Device.objects.create(
            name="Device B",
            role=self.device_role1,
            device_type=self.device_type1,
            site=self.site1,
            platform=self.platform1,
        )

        # Connection template:
        self.connection_template1 = ConnectionTemplate.objects.create(
            name="Template A",
            panorama_url="https://panorama.example.com",
            token_key="TOKEN_KEY1",
        )
        # Connections:
        self.connection1 = Connection.objects.create(
            name="Connection A",
            connection_template=self.connection_template1,
        )

        # Device config sync status:
        self.device_config_sync_status = DeviceConfigSyncStatus.objects.create(
            device=self.device1,
            connection=self.connection1,
        )

        self.happy_day_side_effect = [
            (
                200,
                '<response status="success"><result>no</result><location>local</location></response>',
            ),
        ]

    # pylint: disable=protected-access
    def test_pending_changes_found(self):
        """Test pending changes found."""

        panorama_logger = PanoramaLogger()

        with patch.object(
            DeviceConfigSyncStatus,
            "_panorama_get",
            side_effect=[
                (
                    200,
                    '<response status="success"><result>yes</result><location>local</location></response>',
                ),
                (
                    200,
                    '<config version="11.1.0" urldb="paloaltonetworks" detail-version="11.1.6"></config>',
                ),
            ],
        ) as _:
            status = self.device_config_sync_status.push(panorama_logger)

        self.assertFalse(status)

        self.assertEqual(
            panorama_logger.entries[0].response,
            "pending changes found",
        )
        self.assertEqual(
            panorama_logger.entries[1].response,
            "Configuration exported successfully",
        )

    # pylint: disable=protected-access
    def test_commit_locks_exist(self):
        """Test commit locks exist."""

        panorama_logger = PanoramaLogger()

        with patch.object(
            DeviceConfigSyncStatus,
            "_panorama_get",
            side_effect=[self.happy_day_side_effect[0]],
        ) as _:
            status = self.device_config_sync_status.push(panorama_logger)

        # self.assertFalse(status)

        # self.assertEqual(
        #     panorama_logger.entries[0].response,
        #     "pending changes found",
        # )
        # self.assertEqual(
        #     panorama_logger.entries[1].response,
        #     "Configuration exported successfully",
        # )

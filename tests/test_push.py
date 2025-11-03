"""Tests for the Panorama push functionality."""

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
    """Tests for the Panorama push functionality."""

    def setUp(self):

        # Devices:
        self.device_role1 = DeviceRole.objects.create(name="Device Role A")
        self.manufacturer1 = Manufacturer.objects.create(name="Manufacturer A")
        self.device_type1 = DeviceType.objects.create(
            model="Device Type A", manufacturer=self.manufacturer1
        )
        self.site1 = Site.objects.create(name="Site A")
        # pylint: disable=line-too-long
        self.config_template = ConfigTemplate.objects.create(
            name="Template A",
            template_code=(
                '<config version="11.1.0" urldb="paloaltonetworks" detail-version="11.1.6">'
                "<devices>"
                ' <entry name="localhost.localdomain">'
                "<template>"
                '<entry name="Netbox"/>'
                "</template>"
                "</entry>"
                "</devices>"
                "</config>"
            ),
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

        # pylint: disable=line-too-long
        self.mocked_side_effects = {
            "pending_changes": (
                200,
                (
                    """<response status="success"><result><journal>"""
                    """<entry><xpath>/config/devices/entry[@name=&#39;localhost.localdomain&#39;]/template/entry[@name=&#39;MyTemplate1&#39;]/config/devices/entry[@name=&#39;localhost.localdomain&#39;]/vsys/entry[@name=&#39;vsys1&#39;]/import/network/interface/member[text()=&#39;ethernet1/1.3&#39;]</xpath><owner>xxx</owner><action> CREATE</action><admin-history>xxx</admin-history><component-type>template</component-type></entry>"""
                    """</journal></result></response>"""
                ),
            ),
            "no_pending_changes": (
                200,
                '<response status="success"><result></result></response>',
            ),
            "export_configuration_ok": (
                200,
                '<config version="11.1.0" urldb="paloaltonetworks" detail-version="11.1.6"></config>',
            ),
            "config_locks": (
                200,
                (
                    '<response status="success"><result>'
                    "<config-locks>"
                    '<entry name="xxx">'
                    "<type>shared</type>"
                    "<name>shared</name>"
                    "<created>2025/10/30 02:14:14</created>"
                    "<last-activity>2025/10/30 02:14:14</last-activity>"
                    "<loggedin>yes</loggedin>"
                    "<comment><![CDATA[(null)]]></comment>"
                    "</entry>"
                    "</config-locks>"
                    "</result></response>"
                ),
            ),
            "no_config_locks": (
                200,
                '<response status="success"><result><config-locks></config-locks></result></response>',
            ),
            "commit_locks": (
                200,
                (
                    '<response status="success"><result>'
                    "<commit-locks>"
                    '<entry name="xxx">'
                    "<type>shared</type>"
                    "<name>shared</name>"
                    "<created>2025/10/30 02:14:14</created>"
                    "<last-activity>2025/10/30 02:14:14</last-activity>"
                    "<loggedin>yes</loggedin>"
                    "<comment><![CDATA[(null)]]></comment>"
                    "</entry>"
                    "</commit-locks>"
                    "</result></response>"
                ),
            ),
            "no_commit_locks": (
                200,
                '<response status="success"><result><commit-locks></commit-locks></result></response>',
            ),
            "take_config_lock_ok": (
                200,
                (
                    '<response status="success"><result>'
                    "Successfully acquired lock. Other administrators will not be able to modify configuration until lock is released by xxx."
                    "</result></response>"
                ),
            ),
            "take_config_lock_nok": (
                200,
                '<response status="error"><msg><line>Config lock is already held by xxx</line></msg></response>',
            ),
            "remove_config_lock_ok": (
                200,
                '<response status="success"><result>Config lock released for xxx</result></response>',
            ),
            "remove_config_lock_nok": (
                200,
                '<response status="error"><msg><line>Config is not currently locked for scope shared</line></msg></response>',
            ),
            "take_commit_lock_ok": (
                200,
                (
                    '<response status="success"><result>'
                    "Successfully acquired lock. Other administrators will not be able to commit configuration until lock is released by xxx."
                    "</result></response>"
                ),
            ),
            "take_commit_lock_nok": (
                200,
                '<response status="error"><msg><line>Commit lock is already held by xxx</line></msg></response>',
            ),
            "remove_commit_lock_ok": (
                200,
                '<response status="success"><result>Commit lock released for xxx</result></response>',
            ),
            "remove_commit_lock_nok": (
                200,
                '<response status="error"><msg><line>Commit is not currently locked for scope shared</line></msg></response>',
            ),
            "import_configuration_nok": (
                200,
                (
                    '<response status="error"><msg><line>'
                    "cannot upload to reserved file name "
                    '"too-long-file-name-cannot-handle", which doesn\'t have expected extension ".xml"'
                    "</line></msg></response>"
                ),
            ),
            "import_configuration_ok": (
                200,
                '<response status="success"><msg><line>conf1.xml saved</line></msg></response>',
            ),
            "load_partial_config_nok": (
                200,
                (
                    '<response status="error"><msg><line><msg><line>'
                    "input file doesn't have anything at devices/entry[@name='localhost.localdomain']/device-group/entry[@name='Netbox']\n"
                    ".Failed to compose effective config to load."
                    "</line></msg></line></msg></response>"
                ),
            ),
            "load_partial_config_ok": (
                200,
                (
                    '<response status="success"><result>'
                    "<msg><line>"
                    "<msg><line>Config loaded from netbox-panorama_firewall1.xml</line></msg>"
                    "</line></msg>"
                    "</result></response>"
                ),
            ),
            "revert_nok": (
                200,
                '<response status="error"><result><msg><line>Failed to revert configuration.</line></msg></result></response>',
            ),
            "revert_ok": (
                200,
                '<response status="success"><result><msg><line>All changes were reverted from configuration</line></msg></result></response>',
            ),
            "commit_nok": (
                200,
                '<response status="error" code="14"><msg><line>Other administrators are holding device wide commit locks.</line></msg></response>',
            ),
            "commit_ok": (
                200,
                '<response status="success" code="19"><result><msg><line>Commit job enqueued with jobid 70</line></msg><job>70</job></result></response>',
            ),
            "show_jobs_nok": (
                200,
                '<response status="error" code="7"><msg><line>job 19 not found</line></msg></response>',
            ),
            "show_jobs_ok": (
                200,
                (
                    '<response status="success"><result><job>'
                    "<tenq>2025/10/30 06:20:25</tenq>"
                    "<tdeq>06:20:25</tdeq>"
                    "<id>70</id>"
                    "<user>xxx</user>"
                    "<type>Commit</type>"
                    "<status>FIN</status>"
                    "<queued>NO</queued>"
                    "<stoppable>no</stoppable>"
                    "<result>OK</result>"
                    "<tfin>2025/10/30 06:20:46</tfin>"
                    "<description>Netbox Panorama ConfigPump Plugin</description>"
                    "<positionInQ>0</positionInQ>"
                    "<progress>100</progress>"
                    "<details>"
                    "<line>Configuration committed successfully</line>"
                    "<line>Local configuration size: 9 KB</line>"
                    "<line>Predefined configuration size: 14 MB</line>"
                    "<line>Total configuration size(local, predefined): 14 MB</line>"
                    "<line>Maximum recommended configuration size: 120 MB (11% configured)</line>"
                    "</details>"
                    "<warnings>"
                    "<line>abc\n"
                    "</line>"
                    "</warnings>"
                    "</job></result></response>"
                ),
            ),
        }

    # pylint: disable=protected-access
    def test_pending_changes_found(self):
        """Test pending changes found."""

        panorama_logger = PanoramaLogger()

        with patch.object(
            DeviceConfigSyncStatus,
            "_panorama_get",
            side_effect=[
                self.mocked_side_effects.get("pending_changes"),
                self.mocked_side_effects.get("export_configuration_ok"),
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
    def test_config_locks_exist(self):
        """Test config locks exist."""

        panorama_logger = PanoramaLogger()

        with patch.object(
            DeviceConfigSyncStatus,
            "_panorama_get",
            side_effect=[
                self.mocked_side_effects.get("no_pending_changes"),
                self.mocked_side_effects.get("config_locks"),
                self.mocked_side_effects.get("export_configuration_ok"),
            ],
        ) as _:
            status = self.device_config_sync_status.push(panorama_logger)

        self.assertFalse(status)
        self.assertEqual(
            panorama_logger.entries[0].response,
            "no pending changes found",
        )
        self.assertEqual(
            panorama_logger.entries[1].response,
            "Locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[2].response,
            "Configuration exported successfully",
        )

    # pylint: disable=protected-access
    def test_commit_locks_exist(self):
        """Test commit locks exist."""

        panorama_logger = PanoramaLogger()

        with patch.object(
            DeviceConfigSyncStatus,
            "_panorama_get",
            side_effect=[
                self.mocked_side_effects.get("no_pending_changes"),
                self.mocked_side_effects.get("no_config_locks"),
                self.mocked_side_effects.get("commit_locks"),
                self.mocked_side_effects.get("export_configuration_ok"),
            ],
        ) as _:
            status = self.device_config_sync_status.push(panorama_logger)

        self.assertFalse(status)
        self.assertEqual(
            panorama_logger.entries[0].response,
            "no pending changes found",
        )
        self.assertEqual(
            panorama_logger.entries[1].response,
            "No locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[2].response,
            "Locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[3].response,
            "Configuration exported successfully",
        )

    # pylint: disable=protected-access
    def test_take_config_lock_fails(self):
        """Test take config lock."""

        panorama_logger = PanoramaLogger()

        with patch.object(
            DeviceConfigSyncStatus,
            "_panorama_get",
            side_effect=[
                self.mocked_side_effects.get("no_pending_changes"),
                self.mocked_side_effects.get("no_config_locks"),
                self.mocked_side_effects.get("no_commit_locks"),
                self.mocked_side_effects.get("take_config_lock_nok"),
                self.mocked_side_effects.get("remove_commit_lock_nok"),
                self.mocked_side_effects.get("remove_config_lock_nok"),
                self.mocked_side_effects.get("export_configuration_ok"),
            ],
        ) as _:
            status = self.device_config_sync_status.push(panorama_logger)

        self.assertFalse(status)
        self.assertEqual(
            panorama_logger.entries[0].response,
            "no pending changes found",
        )
        self.assertEqual(
            panorama_logger.entries[1].response,
            "No locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[2].response,
            "No locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[3].response,
            "Config lock is already held by xxx",
        )
        self.assertEqual(
            panorama_logger.entries[4].response,
            "Commit is not currently locked for scope shared",
        )
        self.assertEqual(
            panorama_logger.entries[5].response,
            "Config is not currently locked for scope shared",
        )
        self.assertEqual(
            panorama_logger.entries[6].response,
            "Configuration exported successfully",
        )

    # pylint: disable=protected-access
    def test_take_commit_lock_fails(self):
        """Test take commit lock."""

        panorama_logger = PanoramaLogger()

        with patch.object(
            DeviceConfigSyncStatus,
            "_panorama_get",
            side_effect=[
                self.mocked_side_effects.get("no_pending_changes"),
                self.mocked_side_effects.get("no_config_locks"),
                self.mocked_side_effects.get("no_commit_locks"),
                self.mocked_side_effects.get("take_config_lock_ok"),
                self.mocked_side_effects.get("take_commit_lock_nok"),
                self.mocked_side_effects.get("remove_commit_lock_nok"),
                self.mocked_side_effects.get("remove_config_lock_ok"),
                self.mocked_side_effects.get("export_configuration_ok"),
            ],
        ) as _:
            status = self.device_config_sync_status.push(panorama_logger)

        self.assertFalse(status)
        self.assertEqual(
            panorama_logger.entries[0].response,
            "no pending changes found",
        )
        self.assertEqual(
            panorama_logger.entries[1].response,
            "No locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[2].response,
            "No locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[3].response,
            (
                "Successfully acquired lock. Other administrators will not "
                "be able to modify configuration until lock is released by xxx."
            ),
        )
        self.assertEqual(
            panorama_logger.entries[4].response,
            "Commit lock is already held by xxx",
        )
        self.assertEqual(
            panorama_logger.entries[5].response,
            "Commit is not currently locked for scope shared",
        )
        self.assertEqual(
            panorama_logger.entries[6].response,
            "Config lock released for xxx",
        )
        self.assertEqual(
            panorama_logger.entries[7].response,
            "Configuration exported successfully",
        )

    # pylint: disable=protected-access
    def test_second_pending_changes_found(self):
        """Test take commit lock."""

        panorama_logger = PanoramaLogger()

        with patch.object(
            DeviceConfigSyncStatus,
            "_panorama_get",
            side_effect=[
                self.mocked_side_effects.get("no_pending_changes"),
                self.mocked_side_effects.get("no_config_locks"),
                self.mocked_side_effects.get("no_commit_locks"),
                self.mocked_side_effects.get("take_config_lock_ok"),
                self.mocked_side_effects.get("take_commit_lock_ok"),
                self.mocked_side_effects.get("pending_changes"),
                self.mocked_side_effects.get("remove_commit_lock_ok"),
                self.mocked_side_effects.get("remove_config_lock_ok"),
                self.mocked_side_effects.get("export_configuration_ok"),
            ],
        ) as _:
            status = self.device_config_sync_status.push(panorama_logger)

        self.assertFalse(status)
        self.assertEqual(
            panorama_logger.entries[0].response,
            "no pending changes found",
        )
        self.assertEqual(
            panorama_logger.entries[1].response,
            "No locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[2].response,
            "No locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[3].response,
            (
                "Successfully acquired lock. Other administrators will not "
                "be able to modify configuration until lock is released by xxx."
            ),
        )
        self.assertEqual(
            panorama_logger.entries[4].response,
            (
                "Successfully acquired lock. Other administrators will not "
                "be able to commit configuration until lock is released by xxx."
            ),
        )
        self.assertEqual(
            panorama_logger.entries[5].response,
            "pending changes found",
        )
        self.assertEqual(
            panorama_logger.entries[6].response,
            "Commit lock released for xxx",
        )
        self.assertEqual(
            panorama_logger.entries[7].response,
            "Config lock released for xxx",
        )
        self.assertEqual(
            panorama_logger.entries[8].response,
            "Configuration exported successfully",
        )

    # pylint: disable=protected-access
    def test_import_configuration_fails(self):
        """Test import configuration fails."""

        panorama_logger = PanoramaLogger()

        with patch.object(
            DeviceConfigSyncStatus,
            "_panorama_get",
            side_effect=[
                self.mocked_side_effects.get("no_pending_changes"),
                self.mocked_side_effects.get("no_config_locks"),
                self.mocked_side_effects.get("no_commit_locks"),
                self.mocked_side_effects.get("take_config_lock_ok"),
                self.mocked_side_effects.get("take_commit_lock_ok"),
                self.mocked_side_effects.get("no_pending_changes"),
                self.mocked_side_effects.get("remove_commit_lock_ok"),
                self.mocked_side_effects.get("remove_config_lock_ok"),
                self.mocked_side_effects.get("export_configuration_ok"),
            ],
        ) as _, patch.object(
            DeviceConfigSyncStatus,
            "_panorama_post",
            side_effect=[
                self.mocked_side_effects.get("import_configuration_nok"),
            ],
        ) as _:
            status = self.device_config_sync_status.push(panorama_logger)

        self.assertFalse(status)
        self.assertEqual(
            panorama_logger.entries[0].response,
            "no pending changes found",
        )
        self.assertEqual(
            panorama_logger.entries[1].response,
            "No locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[2].response,
            "No locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[3].response,
            (
                "Successfully acquired lock. Other administrators will not "
                "be able to modify configuration until lock is released by xxx."
            ),
        )
        self.assertEqual(
            panorama_logger.entries[4].response,
            (
                "Successfully acquired lock. Other administrators will not "
                "be able to commit configuration until lock is released by xxx."
            ),
        )
        self.assertEqual(
            panorama_logger.entries[5].response,
            "no pending changes found",
        )
        self.assertEqual(
            panorama_logger.entries[6].response,
            (
                "cannot upload to reserved file name "
                '"too-long-file-name-cannot-handle", '
                'which doesn\'t have expected extension ".xml"'
            ),
        )
        self.assertEqual(
            panorama_logger.entries[7].response,
            "Commit lock released for xxx",
        )
        self.assertEqual(
            panorama_logger.entries[8].response,
            "Config lock released for xxx",
        )
        self.assertEqual(
            panorama_logger.entries[9].response,
            "Configuration exported successfully",
        )

    # pylint: disable=protected-access
    def test_load_partial_config_fails(self):
        """Test load partial config fails."""

        panorama_logger = PanoramaLogger()

        with patch.object(
            DeviceConfigSyncStatus,
            "_panorama_get",
            side_effect=[
                self.mocked_side_effects.get("no_pending_changes"),
                self.mocked_side_effects.get("no_config_locks"),
                self.mocked_side_effects.get("no_commit_locks"),
                self.mocked_side_effects.get("take_config_lock_ok"),
                self.mocked_side_effects.get("take_commit_lock_ok"),
                self.mocked_side_effects.get("no_pending_changes"),
                self.mocked_side_effects.get("load_partial_config_nok"),
                self.mocked_side_effects.get("revert_ok"),
                self.mocked_side_effects.get("remove_commit_lock_ok"),
                self.mocked_side_effects.get("remove_config_lock_ok"),
                self.mocked_side_effects.get("export_configuration_ok"),
            ],
        ) as _, patch.object(
            DeviceConfigSyncStatus,
            "_panorama_post",
            side_effect=[
                self.mocked_side_effects.get("import_configuration_ok"),
            ],
        ) as _:
            status = self.device_config_sync_status.push(panorama_logger)

        self.assertFalse(status)
        self.assertEqual(
            panorama_logger.entries[0].response,
            "no pending changes found",
        )
        self.assertEqual(
            panorama_logger.entries[1].response,
            "No locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[2].response,
            "No locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[3].response,
            (
                "Successfully acquired lock. Other administrators will not "
                "be able to modify configuration until lock is released by xxx."
            ),
        )
        self.assertEqual(
            panorama_logger.entries[4].response,
            (
                "Successfully acquired lock. Other administrators will not "
                "be able to commit configuration until lock is released by xxx."
            ),
        )
        self.assertEqual(
            panorama_logger.entries[5].response,
            "no pending changes found",
        )
        self.assertEqual(
            panorama_logger.entries[6].response,
            "conf1.xml saved",
        )
        # pylint: disable=line-too-long
        self.assertEqual(
            panorama_logger.entries[7].response,
            (
                "input file doesn't have anything at devices/entry[@name='localhost.localdomain']/device-group/entry[@name='Netbox']\n"
                ".Failed to compose effective config to load. /config/devices/entry[@name='localhost.localdomain']/template/entry[@name='Netbox']"
            ),
        )
        self.assertEqual(
            panorama_logger.entries[8].response,
            "All changes were reverted from configuration",
        )
        self.assertEqual(
            panorama_logger.entries[9].response,
            "Commit lock released for xxx",
        )
        self.assertEqual(
            panorama_logger.entries[10].response,
            "Config lock released for xxx",
        )
        self.assertEqual(
            panorama_logger.entries[11].response,
            "Configuration exported successfully",
        )

    def test_commit_fails(self):
        """Test load partial config fails."""

        panorama_logger = PanoramaLogger()

        with patch.object(
            DeviceConfigSyncStatus,
            "_panorama_get",
            side_effect=[
                self.mocked_side_effects.get("no_pending_changes"),
                self.mocked_side_effects.get("no_config_locks"),
                self.mocked_side_effects.get("no_commit_locks"),
                self.mocked_side_effects.get("take_config_lock_ok"),
                self.mocked_side_effects.get("take_commit_lock_ok"),
                self.mocked_side_effects.get("no_pending_changes"),
                self.mocked_side_effects.get("load_partial_config_ok"),
                self.mocked_side_effects.get("commit_nok"),
                self.mocked_side_effects.get("revert_ok"),
                self.mocked_side_effects.get("remove_commit_lock_ok"),
                self.mocked_side_effects.get("remove_config_lock_ok"),
                self.mocked_side_effects.get("export_configuration_ok"),
            ],
        ) as _, patch.object(
            DeviceConfigSyncStatus,
            "_panorama_post",
            side_effect=[
                self.mocked_side_effects.get("import_configuration_ok"),
            ],
        ) as _:
            status = self.device_config_sync_status.push(panorama_logger)

        self.assertFalse(status)
        self.assertEqual(
            panorama_logger.entries[0].response,
            "no pending changes found",
        )
        self.assertEqual(
            panorama_logger.entries[1].response,
            "No locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[2].response,
            "No locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[3].response,
            (
                "Successfully acquired lock. Other administrators will not "
                "be able to modify configuration until lock is released by xxx."
            ),
        )
        self.assertEqual(
            panorama_logger.entries[4].response,
            (
                "Successfully acquired lock. Other administrators will not "
                "be able to commit configuration until lock is released by xxx."
            ),
        )
        self.assertEqual(
            panorama_logger.entries[5].response,
            "no pending changes found",
        )
        self.assertEqual(
            panorama_logger.entries[6].response,
            "conf1.xml saved",
        )
        # pylint: disable=line-too-long
        self.assertEqual(
            panorama_logger.entries[7].response,
            "Config loaded from netbox-panorama_firewall1.xml /config/devices/entry[@name='localhost.localdomain']/template/entry[@name='Netbox']",
        )
        self.assertEqual(
            panorama_logger.entries[8].response,
            "Other administrators are holding device wide commit locks.",
        )
        self.assertEqual(
            panorama_logger.entries[9].response,
            "All changes were reverted from configuration",
        )
        self.assertEqual(
            panorama_logger.entries[10].response,
            "Commit lock released for xxx",
        )
        self.assertEqual(
            panorama_logger.entries[11].response,
            "Config lock released for xxx",
        )
        self.assertEqual(
            panorama_logger.entries[12].response,
            "Configuration exported successfully",
        )

    def test_polling_pending_changes_fails(self):
        """Test load partial config fails."""

        panorama_logger = PanoramaLogger()

        with patch.object(
            DeviceConfigSyncStatus,
            "_panorama_get",
            side_effect=[
                self.mocked_side_effects.get("no_pending_changes"),
                self.mocked_side_effects.get("no_config_locks"),
                self.mocked_side_effects.get("no_commit_locks"),
                self.mocked_side_effects.get("take_config_lock_ok"),
                self.mocked_side_effects.get("take_commit_lock_ok"),
                self.mocked_side_effects.get("no_pending_changes"),
                self.mocked_side_effects.get("load_partial_config_ok"),
                self.mocked_side_effects.get("commit_ok"),
                self.mocked_side_effects.get("show_jobs_nok"),
                self.mocked_side_effects.get("revert_ok"),
                self.mocked_side_effects.get("remove_commit_lock_ok"),
                self.mocked_side_effects.get("remove_config_lock_ok"),
                self.mocked_side_effects.get("export_configuration_ok"),
            ],
        ) as _, patch.object(
            DeviceConfigSyncStatus,
            "_panorama_post",
            side_effect=[
                self.mocked_side_effects.get("import_configuration_ok"),
            ],
        ) as _:
            status = self.device_config_sync_status.push(panorama_logger)

        self.assertFalse(status)
        self.assertEqual(
            panorama_logger.entries[0].response,
            "no pending changes found",
        )
        self.assertEqual(
            panorama_logger.entries[1].response,
            "No locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[2].response,
            "No locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[3].response,
            (
                "Successfully acquired lock. Other administrators will not "
                "be able to modify configuration until lock is released by xxx."
            ),
        )
        self.assertEqual(
            panorama_logger.entries[4].response,
            (
                "Successfully acquired lock. Other administrators will not "
                "be able to commit configuration until lock is released by xxx."
            ),
        )
        self.assertEqual(
            panorama_logger.entries[5].response,
            "no pending changes found",
        )
        self.assertEqual(
            panorama_logger.entries[6].response,
            "conf1.xml saved",
        )
        # pylint: disable=line-too-long
        self.assertEqual(
            panorama_logger.entries[7].response,
            "Config loaded from netbox-panorama_firewall1.xml /config/devices/entry[@name='localhost.localdomain']/template/entry[@name='Netbox']",
        )
        self.assertEqual(
            panorama_logger.entries[8].response,
            "Commit job enqueued with jobid 70 70",
        )
        self.assertEqual(
            panorama_logger.entries[9].response,
            "Commit job '70' returned unknown status error",
        )
        self.assertEqual(
            panorama_logger.entries[10].response,
            "Job did not complete on time",
        )
        self.assertEqual(
            panorama_logger.entries[11].response,
            "All changes were reverted from configuration",
        )
        self.assertEqual(
            panorama_logger.entries[12].response,
            "Commit lock released for xxx",
        )
        self.assertEqual(
            panorama_logger.entries[13].response,
            "Config lock released for xxx",
        )
        self.assertEqual(
            panorama_logger.entries[14].response,
            "Configuration exported successfully",
        )

    def test_happy_day(self):
        """Test load partial config fails."""

        panorama_logger = PanoramaLogger()

        with patch.object(
            DeviceConfigSyncStatus,
            "_panorama_get",
            side_effect=[
                self.mocked_side_effects.get("no_pending_changes"),
                self.mocked_side_effects.get("no_config_locks"),
                self.mocked_side_effects.get("no_commit_locks"),
                self.mocked_side_effects.get("take_config_lock_ok"),
                self.mocked_side_effects.get("take_commit_lock_ok"),
                self.mocked_side_effects.get("no_pending_changes"),
                self.mocked_side_effects.get("load_partial_config_ok"),
                self.mocked_side_effects.get("commit_ok"),
                self.mocked_side_effects.get("show_jobs_ok"),
                self.mocked_side_effects.get("export_configuration_ok"),
            ],
        ) as _, patch.object(
            DeviceConfigSyncStatus,
            "_panorama_post",
            side_effect=[
                self.mocked_side_effects.get("import_configuration_ok"),
            ],
        ) as _:
            status = self.device_config_sync_status.push(panorama_logger)

        self.assertTrue(status)
        self.assertEqual(
            panorama_logger.entries[0].response,
            "no pending changes found",
        )
        self.assertEqual(
            panorama_logger.entries[1].response,
            "No locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[2].response,
            "No locks exist",
        )
        self.assertEqual(
            panorama_logger.entries[3].response,
            (
                "Successfully acquired lock. Other administrators will not "
                "be able to modify configuration until lock is released by xxx."
            ),
        )
        self.assertEqual(
            panorama_logger.entries[4].response,
            (
                "Successfully acquired lock. Other administrators will not "
                "be able to commit configuration until lock is released by xxx."
            ),
        )
        self.assertEqual(
            panorama_logger.entries[5].response,
            "no pending changes found",
        )
        self.assertEqual(
            panorama_logger.entries[6].response,
            "conf1.xml saved",
        )
        # pylint: disable=line-too-long
        self.assertEqual(
            panorama_logger.entries[7].response,
            "Config loaded from netbox-panorama_firewall1.xml /config/devices/entry[@name='localhost.localdomain']/template/entry[@name='Netbox']",
        )
        self.assertEqual(
            panorama_logger.entries[8].response,
            "Commit job enqueued with jobid 70 70",
        )
        self.assertEqual(
            panorama_logger.entries[9].response,
            "Commit job '70' completed successfully",
        )
        self.assertEqual(
            panorama_logger.entries[10].response,
            "Configuration exported successfully",
        )


# class PanoramaLivePushTests(TestCase):
#     """Tests for the Panorama push functionality against a live Panorama instance."""

#     def setUp(self):

#         # Devices:
#         self.device_role1 = DeviceRole.objects.create(name="Device Role A")
#         self.manufacturer1 = Manufacturer.objects.create(name="Manufacturer A")
#         self.device_type1 = DeviceType.objects.create(
#             model="Device Type A", manufacturer=self.manufacturer1
#         )
#         self.site1 = Site.objects.create(name="Site A")

#         config_string = (
#             Path(__file__).parent / "test_data" / "panorama_config1.xml"
#         ).read_text(encoding="utf-8")
#         # pylint: disable=line-too-long
#         self.config_template = ConfigTemplate.objects.create(
#             name="Template A",
#             template_code=config_string,
#         )
#         self.platform1 = Platform.objects.create(
#             name="PanOS", config_template=self.config_template
#         )
#         context_data1 = ConfigContext.objects.create(
#             name="Context A",
#             data={"foo": "bar"},
#         )
#         self.device1 = Device.objects.create(
#             name="Device A",
#             role=self.device_role1,
#             device_type=self.device_type1,
#             site=self.site1,
#             platform=self.platform1,
#         )
#         self.device1.local_context_data = context_data1.data
#         self.device1.save()

#         # Connection template:
#         self.connection_template1 = ConnectionTemplate.objects.create(
#             name="Template A",
#             panorama_url="https://< any panorama url >",
#             token_key="TOKEN_KEY1",
#         )
#         # Connections:
#         self.connection1 = Connection.objects.create(
#             name="Connection A",
#             connection_template=self.connection_template1,
#         )

#         # Device config sync status:
#         self.device_config_sync_status = DeviceConfigSyncStatus.objects.create(
#             device=self.device1,
#             connection=self.connection1,
#         )

#     def test_push_to_live_panorama(self):
#         """Test push to a live Panorama instance."""

#         panorama_logger = PanoramaLogger()
#         status = self.device_config_sync_status.push(panorama_logger)
#         print(status)
#         print(panorama_logger.to_sanitized_dict())

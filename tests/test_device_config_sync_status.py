"""Test device config sync status."""

# pylint: disable=missing-function-docstring, missing-class-docstring


import datetime
import uuid

from core.choices import JobStatusChoices
from core.models import Job
from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Platform, Site
from django.urls import reverse
from extras.models import ConfigContext, ConfigTemplate, Tag
from rest_framework.status import HTTP_200_OK, HTTP_302_FOUND
from rest_framework.test import APIClient
from users.models import User

from netbox_panorama_configpump_plugin.connection.models import Connection
from netbox_panorama_configpump_plugin.connection_template.models import (
    ConnectionTemplate,
)
from netbox_panorama_configpump_plugin.device_config_sync_status.filtersets import (
    DeviceConfigSyncStatusFilterSet,
)
from netbox_panorama_configpump_plugin.device_config_sync_status.forms import (
    DeviceConfigSyncStatusForm,
)
from netbox_panorama_configpump_plugin.device_config_sync_status.models import (
    DeviceConfigSyncStatus,
)
from tests import TestPanoramaConfigPumpMixing


class TestDeviceConfigSyncStatusMixing(TestPanoramaConfigPumpMixing):

    def setUp(self) -> None:
        super().setUp()

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

        # Connection templates:
        self.connection_template1 = ConnectionTemplate.objects.create(
            name="Template A",
            panorama_url="https://panorama.example.com",
            token_key="TOKEN_KEY1",
        )
        self.connection_template2 = ConnectionTemplate.objects.create(
            name="Template B",
            panorama_url="https://panorama.example.com",
            token_key="TOKEN_KEY1",
        )

        # Connections:
        self.connection1 = Connection.objects.create(
            name="Connection A",
            connection_template=self.connection_template1,
        )
        self.connection2 = Connection.objects.create(
            name="Connection B",
            connection_template=self.connection_template2,
        )

        # Tags:
        self.tag1 = Tag.objects.create(name="Tag A")

        # Jobs:
        self.job1 = Job.objects.create(
            name="Job A",
            job_id=uuid.uuid4(),
            status=JobStatusChoices.STATUS_COMPLETED,
        )


class DeviceConfigSyncStatusModelTests(TestDeviceConfigSyncStatusMixing):

    def test_connection_creation(self):
        obj = DeviceConfigSyncStatus.objects.create(
            device=self.device1,
            connection=self.connection1,
            panorama_configuration="abc",
            lines_added=0,
            lines_removed=0,
            lines_changed=0,
            last_pull=None,
            last_push=None,
            config_render_ok=False,
            sync_job=self.job1,
        )
        obj.tags.add(self.tag1)

        self.assertEqual(obj.device, self.device1)
        self.assertEqual(obj.connection, self.connection1)
        self.assertEqual(obj.panorama_configuration, "abc")
        self.assertEqual(obj.lines_added, 0)
        self.assertEqual(obj.lines_removed, 0)
        self.assertEqual(obj.lines_changed, 0)
        self.assertEqual(obj.last_pull, None)
        self.assertEqual(obj.last_push, None)
        self.assertEqual(obj.config_render_ok, False)
        self.assertEqual(obj.tags.first(), self.tag1)
        self.assertEqual(obj.sync_job, self.job1)

    def test_get_rendered_configuration(self):
        obj = DeviceConfigSyncStatus.objects.create(
            device=self.device1,
            connection=self.connection1,
        )
        self.assertEqual(obj.get_rendered_configuration(), "some code bar")

    def test_update_diffs(self):
        obj = DeviceConfigSyncStatus.objects.create(
            device=self.device1,
            connection=self.connection1,
            panorama_configuration="<root></root>",
        )
        self.assertEqual(obj.lines_added, 0)
        self.assertEqual(obj.lines_removed, 1)
        self.assertEqual(obj.lines_changed, 0)

    def test_check_if_rendered_configuration_is_valid(self):
        obj = DeviceConfigSyncStatus.objects.create(
            device=self.device1,
            connection=self.connection1,
        )

        self.config_template.template_code = "<root></root>"
        obj.save()
        self.assertTrue(obj.config_render_ok)

        self.config_template.template_code = "<root></rot>"
        obj.save()
        self.assertFalse(obj.config_render_ok)

    def test_signals_trigger_diffs_and_config_render_ok(self):
        obj = DeviceConfigSyncStatus.objects.create(
            device=self.device1,
            connection=self.connection1,
        )

        # Device change:
        self.config_template.template_code = "<root></root>"
        obj.save()
        self.assertTrue(obj.config_render_ok)

        # ConfigTemplate change:
        self.config_template.template_code = "<root></rot>"
        self.config_template.save()
        obj.refresh_from_db()
        self.assertFalse(obj.config_render_ok)


class ConnectionViewTests(TestDeviceConfigSyncStatusMixing):

    def test_list_view(self):
        DeviceConfigSyncStatus.objects.create(
            device=self.device1,
            connection=self.connection1,
        )
        response = self.get("deviceconfigsyncstatus_list")
        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertContains(response, self.device1.name)

    def test_add_view(self):
        response = self.get("deviceconfigsyncstatus_add")
        self.assertEqual(response.status_code, HTTP_200_OK)

    def test_standard_views(self):
        obj = DeviceConfigSyncStatus.objects.create(
            device=self.device1,
            connection=self.connection1,
        )
        for view in ["", "_edit", "_changelog", "_journal", "_delete"]:
            response = self.get(f"deviceconfigsyncstatus{view}", obj.pk)
            self.assertEqual(response.status_code, HTTP_200_OK)

    def test_confirm_push_config_view(self):
        obj = DeviceConfigSyncStatus.objects.create(
            device=self.device1,
            connection=self.connection1,
        )

        # Config render is not ok:
        response = self.get("deviceconfigsyncstatus_push_config", obj.pk)
        self.assertEqual(response.status_code, HTTP_302_FOUND)

        # Config render is ok (just setting the flag for the test):
        DeviceConfigSyncStatus.objects.filter(pk=obj.pk).update(config_render_ok=True)
        response = self.get("deviceconfigsyncstatus_push_config", obj.pk)
        self.assertEqual(response.status_code, HTTP_200_OK)

    def test_diff_view(self):
        DeviceConfigSyncStatus.objects.create(
            device=self.device1,
            connection=self.connection1,
        )
        response = self.get("device_panorama_diff", pk=self.device1.pk, app="dcim")
        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertContains(response, self.device1.name)


class DeviceConfigSyncStatusAPIViewTests(TestDeviceConfigSyncStatusMixing):

    def test_list(self):
        DeviceConfigSyncStatus.objects.create(
            device=self.device1,
            connection=self.connection1,
        )
        response = self.get("deviceconfigsyncstatus-list", api=True)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data.get("count", 0), 1)

    def test_retrieve(self):

        obj = DeviceConfigSyncStatus.objects.create(
            device=self.device1,
            connection=self.connection1,
            lines_added=123,
        )
        response = self.get("deviceconfigsyncstatus-detail", obj.pk, api=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], obj.pk)
        self.assertEqual(response.data["lines_added"], 0)  # calculated by save

    def test_filter_name(self):
        DeviceConfigSyncStatus.objects.create(
            device=self.device1,
            connection=self.connection1,
        )
        response = self.get("deviceconfigsyncstatus-list", api=True)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data.get("count", 0), 1)

    def test_create(self):
        response = self.post(
            "deviceconfigsyncstatus-list",
            payload={
                "device": self.device1.pk,
                "connection": self.connection1.pk,
                "panorama_configuration": "abc",
                "lines_added": 1,
                "lines_removed": 2,
                "lines_changed": 3,
                "last_pull": "2021-01-01T00:00:00Z",
                "last_push": "2021-01-01T00:00:00Z",
                "config_render_ok": False,
                "sync_job": self.job1.pk,
            },
            api=True,
        )
        self.assertEqual(response.status_code, 201)

        obj = DeviceConfigSyncStatus.objects.first()
        self.assertEqual(obj.device, self.device1)
        self.assertEqual(obj.connection, self.connection1)
        self.assertEqual(obj.panorama_configuration, "abc")
        self.assertEqual(obj.lines_added, 0)  # calculated by save
        self.assertEqual(obj.lines_removed, 0)  # calculated by save
        self.assertEqual(obj.lines_changed, 0)  # calculated by save
        expected_dt = datetime.datetime(
            2021, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc
        )
        self.assertEqual(obj.last_pull, expected_dt)
        self.assertEqual(obj.last_push, expected_dt)
        self.assertEqual(obj.config_render_ok, False)
        self.assertEqual(obj.sync_job, self.job1)


class DeviceConfigSyncStatusFormTests(TestDeviceConfigSyncStatusMixing):

    def test_form(self):

        form = DeviceConfigSyncStatusForm(
            data={
                "device": self.device1.pk,
                "connection": self.connection1.pk,
                "panorama_configuration": "abc",
                "lines_added": 1,
                "lines_removed": 2,
                "lines_changed": 3,
                "last_pull": "2021-01-01T00:00:00Z",
                "last_push": "2021-01-01T00:00:00Z",
                "config_render_ok": False,
                "tags": [self.tag1.pk],
                "sync_job": self.job1.pk,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        obj = DeviceConfigSyncStatus.objects.first()
        self.assertEqual(obj.device, self.device1)
        self.assertEqual(obj.connection, self.connection1)
        self.assertEqual(obj.panorama_configuration, "abc")
        self.assertEqual(obj.lines_added, 0)  # calculated by save
        self.assertEqual(obj.lines_removed, 0)  # calculated by save
        self.assertEqual(obj.lines_changed, 0)  # calculated by save
        expected_dt = datetime.datetime(
            2021, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc
        )
        self.assertEqual(obj.last_pull, expected_dt)
        self.assertEqual(obj.last_push, expected_dt)
        self.assertEqual(obj.config_render_ok, False)
        self.assertEqual(obj.tags.first(), self.tag1)
        self.assertEqual(obj.sync_job, self.job1)


class DeviceConfigSyncStatusFilterSetTests(TestDeviceConfigSyncStatusMixing):

    def setUp(self):
        super().setUp()

        self.device_config_sync_status1 = DeviceConfigSyncStatus.objects.create(
            device=self.device1,
            connection=self.connection1,
        )
        self.device_config_sync_status2 = DeviceConfigSyncStatus.objects.create(
            device=self.device2,
            connection=self.connection2,
            sync_job=self.job1,
        )

    def test_filter_by_connection_id(self):
        qs = DeviceConfigSyncStatusFilterSet(
            data={"connection_id": [self.connection1.id]},
            queryset=DeviceConfigSyncStatus.objects.all(),
        ).qs
        self.assertEqual(list(qs.order_by("id")), [self.device_config_sync_status1])

    def test_filter_by_connection_name(self):
        qs = DeviceConfigSyncStatusFilterSet(
            data={"connection": [self.connection2.name]},
            queryset=DeviceConfigSyncStatus.objects.all(),
        ).qs
        self.assertEqual(list(qs.order_by("id")), [self.device_config_sync_status2])

    def test_filter_by_device_id(self):
        qs = DeviceConfigSyncStatusFilterSet(
            data={"device_id": [self.device1.id]},
            queryset=DeviceConfigSyncStatus.objects.all(),
        ).qs
        self.assertEqual(list(qs.order_by("id")), [self.device_config_sync_status1])

    def test_filter_by_device_name(self):
        qs = DeviceConfigSyncStatusFilterSet(
            data={"device": [self.device2.name]},
            queryset=DeviceConfigSyncStatus.objects.all(),
        ).qs
        self.assertEqual(list(qs.order_by("id")), [self.device_config_sync_status2])

    def test_search(self):
        qs = DeviceConfigSyncStatusFilterSet(
            data={"q": "Device B"}, queryset=DeviceConfigSyncStatus.objects.all()
        ).qs
        self.assertEqual(list(qs.order_by("id")), [self.device_config_sync_status2])

    def test_filter_by_sync_job_id(self):
        qs = DeviceConfigSyncStatusFilterSet(
            data={"sync_job_id": [self.job1.id]},
            queryset=DeviceConfigSyncStatus.objects.all(),
        ).qs
        self.assertEqual(list(qs.order_by("id")), [self.device_config_sync_status2])

    def test_filter_by_sync_job_name(self):
        qs = DeviceConfigSyncStatusFilterSet(
            data={"sync_job": [self.job1.name]},
            queryset=DeviceConfigSyncStatus.objects.all(),
        ).qs
        self.assertEqual(list(qs.order_by("id")), [self.device_config_sync_status2])


class DeviceConfigSyncStatusPermissionsTests(TestDeviceConfigSyncStatusMixing):
    def setUp(self):
        super().setUp()

        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="password"
        )
        self.user = User.objects.create_user(
            username="user", email="user@example.com", password="password"
        )
        self.api = APIClient()

    def test_api_anonymous_denied(self):

        response = self.api.get(
            # pylint: disable=line-too-long
            reverse(
                "plugins-api:netbox_panorama_configpump_plugin-api:deviceconfigsyncstatus-list"
            )
        )
        self.assertIn(response.status_code, (401, 403))

    def test_api_non_staff_cannot_create(self):
        self.api.force_authenticate(self.user)
        resp = self.api.post(
            # pylint: disable=line-too-long
            reverse(
                "plugins-api:netbox_panorama_configpump_plugin-api:deviceconfigsyncstatus-list"
            ),
            {
                "device": self.device1.pk,
                "connection": self.connection1.pk,
            },
        )
        self.assertIn(resp.status_code, (401, 403))

    def test_ui_anonymous_redirect(self):
        client = self.client
        self.client.logout()
        resp = client.get(
            reverse(
                "plugins:netbox_panorama_configpump_plugin:deviceconfigsyncstatus_list"
            )
        )
        self.assertIn(resp.status_code, (302, 403))

"""Test connection."""

# pylint: disable=missing-function-docstring, missing-class-docstring, too-many-instance-attributes


from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Site
from django.urls import reverse
from extras.models import Tag
from rest_framework.status import HTTP_200_OK
from rest_framework.test import APIClient
from users.models import User

from netbox_panorama_configpump_plugin.connection.filtersets import ConnectionFilterSet
from netbox_panorama_configpump_plugin.connection.forms import ConnectionForm
from netbox_panorama_configpump_plugin.connection.models import Connection
from netbox_panorama_configpump_plugin.connection_template.models import (
    ConnectionTemplate,
)
from netbox_panorama_configpump_plugin.device_config_sync_status.models import (
    DeviceConfigSyncStatus,
)
from tests import TestPanoramaConfigPumpMixing


class TestConnectionMixing(TestPanoramaConfigPumpMixing):
    """Test connection model."""

    def setUp(self) -> None:
        super().setUp()
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
        self.device_role1 = DeviceRole.objects.create(name="Device Role A")
        self.manufacturer1 = Manufacturer.objects.create(name="Manufacturer A")
        self.device_type1 = DeviceType.objects.create(
            model="Device Type A", manufacturer=self.manufacturer1
        )
        self.site1 = Site.objects.create(name="Site A")
        self.device1 = Device.objects.create(
            name="Device A",
            role=self.device_role1,
            device_type=self.device_type1,
            site=self.site1,
        )
        self.tag1 = Tag.objects.create(name="Tag A")


class ConnectionModelTests(TestConnectionMixing):

    def test_connection_creation(self):
        obj = Connection.objects.create(
            name="Connection A",
            connection_template=self.connection_template1,
            description="Description A",
            comments="Comments A",
        )
        obj.tags.add(self.tag1)

        self.assertEqual(obj.name, "Connection A")
        self.assertEqual(obj.connection_template, self.connection_template1)
        self.assertEqual(obj.tags.first(), self.tag1)
        self.assertEqual(obj.description, "Description A")
        self.assertEqual(obj.comments, "Comments A")


class ConnectionViewTests(TestConnectionMixing):

    def test_list_view(self):
        Connection.objects.create(
            name="Connection A",
            connection_template=self.connection_template1,
        )
        response = self.get("connection_list")
        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertContains(response, "Connection A")

    def test_add_view(self):
        response = self.get("connection_add")
        self.assertEqual(response.status_code, HTTP_200_OK)

    def test_standard_views(self):
        obj = Connection.objects.create(
            name="Connection A",
            connection_template=self.connection_template1,
        )
        for view in ["", "_edit", "_changelog", "_journal", "_delete"]:
            response = self.get(f"connection{view}", obj.pk)
            self.assertEqual(response.status_code, HTTP_200_OK)

    def test_confirm_push_all_configs_view(self):
        obj = Connection.objects.create(
            name="Connection A",
            connection_template=self.connection_template1,
        )
        response = self.get("connection_push_all_configs", obj.pk)
        self.assertEqual(response.status_code, HTTP_200_OK)


class ConnectionAPIViewTests(TestConnectionMixing):

    def test_list(self):
        Connection.objects.create(
            name="Connection A",
            connection_template=self.connection_template1,
        )
        response = self.get("connection-list", api=True)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data.get("count", 0), 1)

    def test_retrieve(self):

        obj = Connection.objects.create(
            name="Connection A",
            connection_template=self.connection_template1,
        )
        response = self.get("connection-detail", obj.pk, api=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], obj.pk)
        self.assertEqual(response.data["name"], "Connection A")

    def test_filter_name(self):
        Connection.objects.create(
            name="Connection A",
            connection_template=self.connection_template1,
        )
        response = self.get("connection-list", api=True)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data.get("count", 0), 1)

    def test_create(self):
        response = self.post(
            "connection-list",
            payload={
                "name": "Connection A",
                "connection_template": self.connection_template1.pk,
                "tags": [self.tag1.pk],
                "description": "Description A",
                "comments": "Comments A",
            },
            api=True,
        )
        self.assertEqual(response.status_code, 201)

        obj = Connection.objects.get(name="Connection A")
        self.assertEqual(obj.name, "Connection A")
        self.assertEqual(obj.connection_template, self.connection_template1)
        self.assertEqual(obj.description, "Description A")
        self.assertEqual(obj.comments, "Comments A")
        self.assertEqual(obj.tags.first(), self.tag1)


class ConnectionFormTests(TestConnectionMixing):

    def test_form(self):
        form = ConnectionForm(
            data={
                "name": "Connection A",
                "connection_template": self.connection_template1.pk,
                "devices": [self.device1.pk],
                "tags": [self.tag1.pk],
                "description": "Description A",
                "comments": "Comments A",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        obj = Connection.objects.get(name="Connection A")
        self.assertEqual(obj.name, "Connection A")
        self.assertEqual(obj.connection_template, self.connection_template1)
        self.assertEqual(obj.tags.first(), self.tag1)
        self.assertEqual(obj.description, "Description A")
        self.assertEqual(obj.comments, "Comments A")
        self.assertEqual(obj.devices.first(), self.device1)

        # Should create a DeviceConfigSyncStatus object
        sync_status = DeviceConfigSyncStatus.objects.get(device=self.device1)
        self.assertEqual(sync_status.connection, obj)


class ConnectionFilterSetTests(TestConnectionMixing):

    def setUp(self):
        super().setUp()

        self.connection1 = Connection.objects.create(
            name="Connection A",
            connection_template=self.connection_template1,
        )
        self.connection2 = Connection.objects.create(
            name="Connection B",
            connection_template=self.connection_template2,
        )

    def test_filter_by_connection_template_id(self):
        qs = ConnectionFilterSet(
            data={"connection_template_id": [self.connection_template1.id]},
            queryset=Connection.objects.all(),
        ).qs
        self.assertEqual(list(qs.order_by("id")), [self.connection1])

    def test_filter_by_connection_template_name(self):
        qs = ConnectionFilterSet(
            data={"connection_template": [self.connection_template2.name]},
            queryset=Connection.objects.all(),
        ).qs
        self.assertEqual(list(qs.order_by("id")), [self.connection2])

    def test_search(self):
        qs = ConnectionFilterSet(
            data={"q": "Connection B"}, queryset=Connection.objects.all()
        ).qs
        self.assertEqual(list(qs.order_by("id")), [self.connection2])


class ConnectionPermissionsTests(TestConnectionMixing):
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
            reverse("plugins-api:netbox_panorama_configpump_plugin-api:connection-list")
        )
        self.assertIn(response.status_code, (401, 403))

    def test_api_non_staff_cannot_create(self):
        self.api.force_authenticate(self.user)
        resp = self.api.post(
            # pylint: disable=line-too-long
            reverse(
                "plugins-api:netbox_panorama_configpump_plugin-api:connection-list"
            ),
            {
                "name": "Connection A",
                "connection_template": self.connection_template1.pk,
            },
        )
        self.assertIn(resp.status_code, (401, 403))

    def test_ui_anonymous_redirect(self):
        client = self.client
        self.client.logout()
        resp = client.get(
            reverse("plugins:netbox_panorama_configpump_plugin:connection_list")
        )
        self.assertIn(resp.status_code, (302, 403))

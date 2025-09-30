"""Test connection template."""

# pylint: disable=missing-function-docstring, missing-class-docstring

from unittest.mock import patch

from dcim.models import Platform
from django.test import TestCase
from django.urls import reverse
from extras.models import Tag
from rest_framework.status import HTTP_200_OK
from rest_framework.test import APIClient
from users.models import User

from netbox_panorama_configpump_plugin.connection_template.filtersets import (
    ConnectionTemplateFilterSet,
)
from netbox_panorama_configpump_plugin.connection_template.models import (
    ConnectionTemplate,
)
from tests import TestPanoramaConfigPumpMixing


@patch("netbox_panorama_configpump_plugin.connection_template.models.get_plugin_config")
class ConnectionTemplateModelTests(TestCase):

    def setUp(self):
        self.valid_attrs = {
            "name": "Template A",
            "panorama_url": "https://panorama.example.com",
            "token_key": "TOKEN_KEY1",
        }

    def test_connection_template_creation(self, mock_get_plugin_config):
        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {
            "tokens": {"TOKEN_KEY1": "token1", "TOKEN_KEY2": "token2"},
            "default_request_timeout": 123,
            "default_filename_prefix": "test-prefix-1",
        }.get(key, default)

        obj = ConnectionTemplate.objects.create(**self.valid_attrs)

        self.assertEqual(obj.name, self.valid_attrs["name"])
        self.assertEqual(obj.panorama_url, self.valid_attrs["panorama_url"])
        self.assertEqual(obj.token_key, self.valid_attrs["token_key"])
        self.assertEqual(obj.request_timeout, 123)
        self.assertEqual(obj.file_name_prefix, "test-prefix-1")

    def test_connection_template_creation_with_explicit_values(
        self, mock_get_plugin_config
    ):
        mock_get_plugin_config.side_effect = lambda plugin, key, default=None: {
            "tokens": {"TOKEN_KEY1": "token1", "TOKEN_KEY2": "token2"},
            "default_request_timeout": 30,
            "default_filename_prefix": "test-prefix-2",
        }.get(key, default)

        attrs_with_explicit = {
            "name": "Template B",
            "panorama_url": "https://panorama.example.com",
            "token_key": "TOKEN_KEY2",
            "request_timeout": 120,
            "file_name_prefix": "custom-prefix",
        }

        obj = ConnectionTemplate.objects.create(**attrs_with_explicit)

        self.assertEqual(obj.name, attrs_with_explicit["name"])
        self.assertEqual(obj.panorama_url, attrs_with_explicit["panorama_url"])
        self.assertEqual(obj.token_key, attrs_with_explicit["token_key"])
        self.assertEqual(obj.request_timeout, 120)
        self.assertEqual(obj.file_name_prefix, "custom-prefix")


class ConnectionTemplateViewTests(TestPanoramaConfigPumpMixing):

    def test_list_view(self):
        ConnectionTemplate.objects.create(
            name="Template A",
            panorama_url="https://panorama.example.com",
            token_key="TOKEN_KEY1",
        )
        response = self.get("connectiontemplate_list")
        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertContains(response, "Template A")

    def test_add_view(self):
        response = self.get("connectiontemplate_add")
        self.assertEqual(response.status_code, HTTP_200_OK)

    def test_standard_views(self):
        obj = ConnectionTemplate.objects.create(
            name="Template A",
            panorama_url="https://panorama.example.com",
            token_key="TOKEN_KEY1",
        )
        for view in ["", "_edit", "_changelog", "_journal", "_delete"]:
            response = self.get(f"connectiontemplate{view}", obj.pk)
            self.assertEqual(response.status_code, HTTP_200_OK)


class ConnectionTemplateAPIViewTests(TestPanoramaConfigPumpMixing):

    def test_list(self):
        ConnectionTemplate.objects.create(
            name="Template A",
            panorama_url="https://panorama.example.com",
            token_key="TOKEN_KEY1",
        )
        response = self.get("connectiontemplate-list", api=True)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data.get("count", 0), 1)

    def test_retrieve(self):
        obj = ConnectionTemplate.objects.create(
            name="Template A",
            panorama_url="https://panorama.example.com",
            token_key="TOKEN_KEY1",
        )
        response = self.get("connectiontemplate-detail", obj.pk, api=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], obj.pk)
        self.assertEqual(response.data["name"], "Template A")

    def test_filter_name(self):
        ConnectionTemplate.objects.create(
            name="Template A",
            panorama_url="https://panorama.example.com",
            token_key="TOKEN_KEY1",
        )
        response = self.get("connectiontemplate-list", api=True)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data.get("count", 0), 1)

    def test_create(self):
        # pylint: disable=line-too-long
        with patch(
            "netbox_panorama_configpump_plugin.connection_template.models.get_plugin_config",
            side_effect=[45, "netbox-panorama123"],
        ):
            response = self.post(
                "connectiontemplate-list",
                payload={
                    "name": "Template A",
                    "panorama_url": "https://panorama.example.com",
                    "token_key": "API_SECRET",
                },
                api=True,
            )
        self.assertEqual(response.status_code, 201)

        obj = ConnectionTemplate.objects.get(name="Template A")
        self.assertEqual(obj.name, "Template A")
        self.assertEqual(obj.panorama_url, "https://panorama.example.com")
        self.assertEqual(obj.token_key, "API_SECRET")
        self.assertEqual(obj.file_name_prefix, "netbox-panorama123")
        self.assertEqual(obj.request_timeout, 45)


class ConnectionTemplateFormTests(TestCase):

    def test_form_with_minimal_fields_and_save_populates_defaults(self):
        with patch(
            # pylint: disable=line-too-long
            "netbox_panorama_configpump_plugin.connection_template.forms.get_plugin_config",
            new=lambda plugin, key=None, default=None: {
                "tokens": {"TOKEN_KEY1": "secret-token-value"},
                "default_request_timeout": 60,
                "default_filename_prefix": "netbox-panorama",
                "top_level_menu": True,
            }.get(key, default),
        ):
            # pylint: disable=import-outside-toplevel
            from netbox_panorama_configpump_plugin.connection_template.forms import (
                ConnectionTemplateForm,
            )

            form = ConnectionTemplateForm(
                data={
                    "name": "Template A",
                    "panorama_url": "https://panorama.example.com",
                    "token_key": "TOKEN_KEY1",
                }
            )
            self.assertTrue(form.is_valid(), form.errors)
            form.save()

            obj = ConnectionTemplate.objects.get(name="Template A")
            self.assertEqual(obj.name, "Template A")
            self.assertEqual(obj.panorama_url, "https://panorama.example.com")
            self.assertEqual(obj.token_key, "TOKEN_KEY1")
            self.assertEqual(obj.request_timeout, 60)
            self.assertEqual(obj.file_name_prefix, "netbox-panorama")

    def test_form_with_all_fields_filled(self):
        with patch(
            # pylint: disable=line-too-long
            "netbox_panorama_configpump_plugin.connection_template.forms.get_plugin_config",
            new=lambda plugin, key=None, default=None: {
                "tokens": {"TOKEN_KEY1": "secret-token-value"},
                "default_request_timeout": 60,
                "default_filename_prefix": "netbox-panorama",
                "top_level_menu": True,
            }.get(key, default),
        ):
            # pylint: disable=import-outside-toplevel
            from netbox_panorama_configpump_plugin.connection_template.forms import (
                ConnectionTemplateForm,
            )

            platform1 = Platform.objects.create(name="Platform A")
            tag1 = Tag.objects.create(name="Tag A")

            form = ConnectionTemplateForm(
                data={
                    "name": "Template A",
                    "panorama_url": "https://panorama.example.com",
                    "token_key": "TOKEN_KEY1",
                    "file_name_prefix": "netbox-panorama123",
                    "platforms": [platform1.pk],
                    "request_timeout": 100,
                    "description": "Description",
                    "tags": [tag1.pk],
                    "comments": "Comments",
                }
            )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        obj = ConnectionTemplate.objects.get(name="Template A")
        self.assertEqual(obj.name, "Template A")
        self.assertEqual(obj.panorama_url, "https://panorama.example.com")
        self.assertEqual(obj.token_key, "TOKEN_KEY1")
        self.assertEqual(obj.file_name_prefix, "netbox-panorama123")
        self.assertEqual(obj.platforms.first(), platform1)
        self.assertEqual(obj.request_timeout, 100)
        self.assertEqual(obj.description, "Description")
        self.assertEqual(obj.tags.first(), tag1)
        self.assertEqual(obj.comments, "Comments")


class ConnectionTemplateFilterSetTests(TestCase):

    def setUp(self):
        self.platform1 = Platform.objects.create(name="PAN-OS 10", slug="panos-10")
        self.platform2 = Platform.objects.create(name="PAN-OS 11", slug="panos-11")
        self.tag1 = Tag.objects.create(name="Tag A")
        self.tag2 = Tag.objects.create(name="Tag B")

        self.connection_template1 = ConnectionTemplate.objects.create(
            name="Template A",
            panorama_url="https://panorama1.example.com",
            token_key="TOKEN_KEY1",
            file_name_prefix="netbox-panorama123",
            request_timeout=100,
            description="Description A",
            comments="Comments A",
        )
        self.connection_template1.platforms.add(self.platform1)
        self.connection_template1.tags.add(self.tag1)

        self.connection_template2 = ConnectionTemplate.objects.create(
            name="Template B",
            panorama_url="https://panorama2.example.com",
            token_key="TOKEN_KEY1",
            file_name_prefix="netbox-panorama456",
            request_timeout=200,
            description="Description B",
            comments="Comments B",
        )
        self.connection_template2.platforms.add(self.platform2)
        self.connection_template2.tags.add(self.tag2)

    def test_filter_by_platform_id(self):
        qs = ConnectionTemplateFilterSet(
            data={"platform_id": [self.platform1.id]},
            queryset=ConnectionTemplate.objects.all(),
        ).qs
        self.assertEqual(list(qs.order_by("id")), [self.connection_template1])

    def test_filter_by_platform_slug(self):
        qs = ConnectionTemplateFilterSet(
            data={"platform": [self.platform2.slug]},
            queryset=ConnectionTemplate.objects.all(),
        ).qs
        self.assertEqual(list(qs.order_by("id")), [self.connection_template2])

    def test_search(self):
        qs = ConnectionTemplateFilterSet(
            data={"q": "Template B"}, queryset=ConnectionTemplate.objects.all()
        ).qs
        self.assertEqual(list(qs.order_by("id")), [self.connection_template2])


class ConnectionTemplatePermissionsTests(TestCase):
    def setUp(self):
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
                "plugins-api:netbox_panorama_configpump_plugin-api:connectiontemplate-list"
            )
        )
        self.assertIn(response.status_code, (401, 403))

    def test_api_non_staff_cannot_create(self):
        self.api.force_authenticate(self.user)
        response = self.api.post(
            # pylint: disable=line-too-long
            reverse(
                "plugins-api:netbox_panorama_configpump_plugin-api:connectiontemplate-list"
            ),
            {
                "name": "Template A",
                "panorama_url": "https://panorama.example.com",
                "token_key": "TOKEN_KEY1",
            },
        )
        self.assertIn(response.status_code, (401, 403))

    def test_ui_anonymous_redirect(self):
        client = self.client
        self.client.logout()
        response = client.get(
            reverse("plugins:netbox_panorama_configpump_plugin:connectiontemplate_list")
        )
        self.assertIn(response.status_code, (302, 403))

"""Test Panorama Config Pump Mixing."""

# pylint: disable=missing-function-docstring

from django.http import HttpResponse
from django.test import Client, TestCase
from django.urls import reverse
from users.models import User


class TestPanoramaConfigPumpMixing(TestCase):
    """Test Panorama Config Pump Mixing."""

    def get(
        self,
        url_name: str,
        pk: int = 0,
        api: bool = False,
        app: str = "plugins:netbox_panorama_configpump_plugin",
    ) -> HttpResponse:
        url = reverse(
            (
                f"{app}:{url_name}"
                if not api
                else f"plugins-api:netbox_panorama_configpump_plugin-api:{url_name}"
            ),
            kwargs={"pk": pk} if pk else {},
        )
        return self.client.get(url)

    def post(
        self,
        url_name: str,
        payload: dict | None,
        pk: int = 0,
        api: bool = False,
        app: str = "plugins:netbox_panorama_configpump_plugin",
    ) -> HttpResponse:
        url_params = {"pk": pk} if pk else {}
        url = reverse(
            (
                f"{app}:{url_name}"
                if not api
                else f"plugins-api:netbox_panorama_configpump_plugin-api:{url_name}"
            ),
            kwargs=url_params,
        )
        response: HttpResponse = self.client.post(
            url, payload, content_type="application/json"
        )

        return response

    def setUp(self) -> None:
        User.objects.create_superuser("panorama", "panorama@rautanen.io", "panorama")
        self.client = Client()
        self.client.login(username="panorama", password="panorama")

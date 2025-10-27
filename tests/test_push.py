"""Test push functionality."""

# pylint: disable=missing-function-docstring, missing-class-docstring

from unittest.mock import Mock, call

from django.test import TestCase

from netbox_panorama_configpump_plugin.device_config_sync_status import (
    panorama as panorama_mod,
)
from netbox_panorama_configpump_plugin.device_config_sync_status.panorama import (
    PanoramaLogger,
    PanoramaMixin,
    Status,
)


class FakeConnTemplate:
    token_key = "dummy"
    request_timeout = 1
    panorama_url = "https://panorama.local"
    file_name_prefix = "nb"


class FakeConnection:
    connection_template = FakeConnTemplate()


class FakeDevice:
    name = "Device-1"


# pylint: disable=line-too-long
class FakeModel(PanoramaMixin):
    def __init__(self):
        self.device = FakeDevice()
        self.connection = FakeConnection()
        self.panorama_configuration = ""

    def get_xpath_entries(self):
        return [
            "/config/devices/entry[@name='localhost.localdomain']/template/entry[@name='t']"
        ]

    def get_rendered_configuration(self):
        return "<config/>"

    def save(self):
        # No-op for tests
        pass


# pylint: disable=protected-access
class PushTests(TestCase):
    """Test push functionality."""

    def setUp(self):
        self.model = FakeModel()
        self.logger = PanoramaLogger()

    def _common_mocks_for_success(self):
        """Set up mocks for successful push operations."""
        self.model._panorama_get = Mock(return_value=(200, "<response/>"))
        self.model._panorama_post = Mock(return_value=(200, "<response/>"))
        self.model._check_pending_changes = Mock(return_value=False)
        self.model._locks_exist = Mock(return_value=False)
        self.model._parse_panorama_response = Mock(
            side_effect=[
                {"status": True},  # add config lock
                {"status": True},  # add commit lock
                {"status": True},  # import configuration
                {"status": True, "commit_job_id": "123"},  # commit
            ]
        )
        # Mock normalize_xml at module level
        original_normalize = panorama_mod.normalize_xml
        self.addCleanup(setattr, panorama_mod, "normalize_xml", original_normalize)
        panorama_mod.normalize_xml = lambda x: (x, True)

    def test_push_happy_path(self):
        self._common_mocks_for_success()
        self.model._load_partial_config = Mock(return_value=True)
        self.model._poll_show_jobs = Mock(return_value=True)
        self.model._export_configuration = Mock(return_value=True)

        result = self.model.push(self.logger)

        self.assertTrue(result)
        self.assertEqual(self.model._check_pending_changes.call_count, 2)
        self.assertEqual(
            self.model._locks_exist.call_args_list,
            [
                call(self.logger, "commit"),
                call(self.logger, "config"),
            ],
        )
        self.assertEqual(self.model._export_configuration.call_count, 1)

    def test_push_returns_false_when_pending_changes_first(self):
        self.model._panorama_get = Mock(return_value=(200, "<response/>"))
        self.model._check_pending_changes = Mock(return_value=True)
        export = Mock(return_value=True)
        self.model._export_configuration = export

        result = self.model.push(self.logger)

        self.assertFalse(result)
        export.assert_called_once_with(self.logger)

    def test_push_returns_false_when_locks_exist_commit(self):
        self.model._panorama_get = Mock(return_value=(200, "<response/>"))
        self.model._check_pending_changes = Mock(return_value=False)
        self.model._locks_exist = Mock(side_effect=[True, False])
        export = Mock(return_value=True)
        self.model._export_configuration = export

        result = self.model.push(self.logger)

        self.assertFalse(result)
        export.assert_called_once_with(self.logger)

    def test_push_returns_false_when_locks_exist_config(self):
        self.model._panorama_get = Mock(return_value=(200, "<response/>"))
        self.model._check_pending_changes = Mock(return_value=False)
        self.model._locks_exist = Mock(side_effect=[False, True])
        export = Mock(return_value=True)
        self.model._export_configuration = export

        result = self.model.push(self.logger)

        self.assertFalse(result)
        export.assert_called_once_with(self.logger)

    def test_push_returns_false_when_config_lock_add_fails(self):
        self.model._panorama_get = Mock(return_value=(200, "<response/>"))
        self.model._check_pending_changes = Mock(return_value=False)
        self.model._locks_exist = Mock(return_value=False)
        self.model._parse_panorama_response = Mock(return_value={"status": False})
        rml = Mock(return_value=True)
        self.model._remove_locks_and_export = rml

        result = self.model.push(self.logger)

        self.assertFalse(result)
        rml.assert_called_once_with(self.logger)

    def test_push_returns_false_when_commit_lock_add_fails(self):
        self.model._panorama_get = Mock(return_value=(200, "<response/>"))
        self.model._check_pending_changes = Mock(return_value=False)
        self.model._locks_exist = Mock(return_value=False)
        self.model._parse_panorama_response = Mock(
            side_effect=[{"status": True}, {"status": False}]
        )
        rml = Mock(return_value=True)
        self.model._remove_locks_and_export = rml

        result = self.model.push(self.logger)

        self.assertFalse(result)
        rml.assert_called_once_with(self.logger)

    def test_push_returns_false_when_rendered_config_empty(self):
        self.model._panorama_get = Mock(return_value=(200, "<response/>"))
        self.model._check_pending_changes = Mock(return_value=False)
        self.model._locks_exist = Mock(return_value=False)
        self.model._parse_panorama_response = Mock(return_value={"status": True})
        self.model.get_rendered_configuration = lambda: ""
        rml = Mock(return_value=True)
        self.model._remove_locks_and_export = rml

        result = self.model.push(self.logger)

        self.assertFalse(result)
        rml.assert_called_once_with(self.logger)
        self.assertTrue(any(e.status == Status.FAILURE for e in self.logger.entries))

    def test_push_returns_false_when_normalized_invalid(self):
        self.model._panorama_get = Mock(return_value=(200, "<response/>"))
        self.model._check_pending_changes = Mock(return_value=False)
        self.model._locks_exist = Mock(return_value=False)
        self.model._parse_panorama_response = Mock(return_value={"status": True})
        original_normalize = panorama_mod.normalize_xml
        self.addCleanup(setattr, panorama_mod, "normalize_xml", original_normalize)
        panorama_mod.normalize_xml = lambda x: (x, False)
        rml = Mock(return_value=True)
        self.model._remove_locks_and_export = rml

        result = self.model.push(self.logger)

        self.assertFalse(result)
        rml.assert_called_once_with(self.logger)

    def test_push_returns_false_when_import_fails(self):
        self.model._panorama_get = Mock(return_value=(200, "<response/>"))
        self.model._check_pending_changes = Mock(return_value=False)
        self.model._locks_exist = Mock(return_value=False)
        original_normalize = panorama_mod.normalize_xml
        self.addCleanup(setattr, panorama_mod, "normalize_xml", original_normalize)
        panorama_mod.normalize_xml = lambda x: (x, True)
        self.model._parse_panorama_response = Mock(
            side_effect=[
                {"status": True},  # config lock
                {"status": True},  # commit lock
                {"status": False},  # import fails
            ]
        )
        rml = Mock(return_value=True)
        self.model._remove_locks_and_export = rml

        result = self.model.push(self.logger)

        self.assertFalse(result)
        rml.assert_called_once_with(self.logger)

    def test_push_returns_false_when_load_partial_config_fails(self):
        self._common_mocks_for_success()
        self.model._load_partial_config = Mock(return_value=False)
        rre = Mock(return_value=False)
        self.model._revert_remove_locks_and_export = rre

        result = self.model.push(self.logger)

        self.assertFalse(result)
        rre.assert_called_once_with(self.logger)

    def test_push_returns_false_when_commit_has_no_jobid(self):
        self._common_mocks_for_success()
        self.model._load_partial_config = Mock(return_value=True)
        self.model._parse_panorama_response = Mock(
            side_effect=[
                {"status": True},  # config lock
                {"status": True},  # commit lock
                {"status": True},  # import
                {"status": True},  # commit without job id
            ]
        )
        rre = Mock(return_value=False)
        self.model._revert_remove_locks_and_export = rre

        result = self.model.push(self.logger)

        self.assertFalse(result)
        rre.assert_called_once_with(self.logger)

    def test_push_returns_false_when_poll_fails(self):
        self._common_mocks_for_success()
        self.model._load_partial_config = Mock(return_value=True)
        self.model._parse_panorama_response = Mock(
            side_effect=[
                {"status": True},  # config lock
                {"status": True},  # commit lock
                {"status": True},  # import
                {"status": True, "commit_job_id": "123"},  # commit with job id
            ]
        )
        self.model._poll_show_jobs = Mock(return_value=False)
        rre = Mock(return_value=False)
        self.model._revert_remove_locks_and_export = rre

        result = self.model.push(self.logger)

        self.assertFalse(result)
        rre.assert_called_once_with(self.logger)

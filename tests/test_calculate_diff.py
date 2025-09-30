"""Test diff calculator."""

# pylint: disable=missing-function-docstring, missing-class-docstring

import os

from django.test import TestCase

from netbox_panorama_configpump_plugin.utils.helpers import calculate_diff


class DiffCalculatorTests(TestCase):

    def test_diff_calculator(self):

        test_data_dir = os.path.join(os.path.dirname(__file__), "test_data")

        config1_path = os.path.join(test_data_dir, "panorama_config1.xml")
        with open(config1_path, "r", encoding="utf-8") as f:
            panorama_config1 = f.read()

        config2_path = os.path.join(test_data_dir, "panorama_config2.xml")
        with open(config2_path, "r", encoding="utf-8") as f:
            panorama_config2 = f.read()

        diff = calculate_diff(
            panorama_config1,
            panorama_config2,
        )
        self.assertEqual(diff["added"], 2)
        self.assertEqual(diff["removed"], 1)
        self.assertEqual(diff["changed"], 1)

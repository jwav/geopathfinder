"""Tests for local, file-based secret loading."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from geopathfinder.configuration import load_ors_api_key
from geopathfinder.exceptions import ConfigurationError


class ConfigurationTests(unittest.TestCase):
    def test_loads_and_strips_key_file(self) -> None:
        with TemporaryDirectory() as directory:
            key_file = Path(directory) / "ORS_API_KEY.key"
            key_file.write_text("  test-key-value\n", encoding="utf-8")

            self.assertEqual(load_ors_api_key(key_file), "test-key-value")

    def test_missing_key_file_raises_safe_error(self) -> None:
        with TemporaryDirectory() as directory:
            missing_file = Path(directory) / "missing.key"

            with self.assertRaises(ConfigurationError) as raised:
                load_ors_api_key(missing_file)

        self.assertIn("not found", str(raised.exception))

    def test_empty_or_multiline_key_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            key_file = Path(directory) / "ORS_API_KEY.key"
            key_file.write_text("first\nsecond", encoding="utf-8")

            with self.assertRaises(ConfigurationError) as raised:
                load_ors_api_key(key_file)

        self.assertIn("one non-empty key", str(raised.exception))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

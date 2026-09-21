"""Tests for output path helpers."""

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from tldr_recap.paths import default_output_dir, slugify


class PathTests(unittest.TestCase):
    def test_slugify(self) -> None:
        self.assertEqual(slugify("Security Meeting #4"), "security-meeting-4")

    def test_default_output_dir_avoids_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            now = datetime(2026, 9, 20, 16, 30, tzinfo=UTC)
            first = default_output_dir([Path("Meeting.mp4")], root, now)
            first.mkdir()
            second = default_output_dir([Path("Meeting.mp4")], root, now)
            self.assertEqual(first.name, "2026-09-20_16-30-meeting")
            self.assertEqual(second.name, "2026-09-20_16-30-meeting-2")


if __name__ == "__main__":
    unittest.main()

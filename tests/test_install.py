"""Tests for portable skill installation."""

import importlib.util
import tempfile
import unittest
from pathlib import Path


INSTALL_PATH = Path(__file__).parents[1] / "scripts" / "install.py"
SPEC = importlib.util.spec_from_file_location("tldr_recap_install", INSTALL_PATH)
INSTALL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALL)


class InstallTests(unittest.TestCase):
    def test_link_skill_targets_canonical_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            target = root / ".agents" / "skills" / "tldr-recap"
            INSTALL.link_skill(source, target)
            self.assertTrue(target.is_symlink())
            self.assertEqual(target.resolve(), source.resolve())

    def test_link_skill_does_not_replace_existing_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            target = root / "target"
            target.mkdir()
            with self.assertRaisesRegex(RuntimeError, "Refusing to replace"):
                INSTALL.link_skill(source, target)

    def test_link_skill_replaces_broken_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old_source = root / "old"
            old_source.mkdir()
            source = root / "source"
            source.mkdir()
            target = root / "target"
            target.symlink_to(old_source, target_is_directory=True)
            old_source.rmdir()
            INSTALL.link_skill(source, target)
            self.assertEqual(target.resolve(), source.resolve())

    def test_link_skill_repoints_working_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            other = root / "other"
            other.mkdir()
            source = root / "source"
            source.mkdir()
            target = root / "target"
            target.symlink_to(other, target_is_directory=True)
            INSTALL.link_skill(source, target)
            self.assertEqual(target.resolve(), source.resolve())
            self.assertTrue(other.is_dir())

    def test_link_skill_is_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            target = root / "target"
            INSTALL.link_skill(source, target)
            INSTALL.link_skill(source, target)
            self.assertEqual(target.resolve(), source.resolve())


if __name__ == "__main__":
    unittest.main()

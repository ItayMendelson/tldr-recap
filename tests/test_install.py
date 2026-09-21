"""Tests for portable skill installation."""

import contextlib
import importlib.util
import io
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

    def test_link_harnesses_skips_missing_harness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            (home / ".claude").mkdir(parents=True)
            source = Path(temporary) / "source"
            source.mkdir()
            with contextlib.redirect_stdout(io.StringIO()) as output:
                INSTALL.link_harnesses(source, home)
            link = home / ".claude" / "skills" / "tldr-recap"
            self.assertEqual(link.resolve(), source.resolve())
            self.assertFalse((home / ".agents").exists())
            self.assertIn("Skipped Codex", output.getvalue())

    def test_link_harnesses_reports_when_none_found(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            home.mkdir()
            source = Path(temporary) / "source"
            source.mkdir()
            with contextlib.redirect_stdout(io.StringIO()) as output:
                INSTALL.link_harnesses(source, home)
            self.assertEqual(list(home.iterdir()), [])
            self.assertIn("No fitting harness found", output.getvalue())


if __name__ == "__main__":
    unittest.main()

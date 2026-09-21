"""Install the TLDR Recap CLI and skill links."""

import argparse
import subprocess
from pathlib import Path

HARNESSES = {"Claude Code": ".claude", "Codex": ".agents"}


def link_skill(source: Path, target: Path) -> None:
    """Point a skill symlink at the source, never replacing real files."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        target.unlink()
    elif target.exists():
        raise RuntimeError(f"Refusing to replace existing path: {target}")
    target.symlink_to(source, target_is_directory=True)
    print(f"Linked: {target} -> {source}")


def link_harnesses(skill: Path, home: Path) -> None:
    """Link the skill into each harness directory that already exists."""
    linked = False
    for name, directory in HARNESSES.items():
        root = home / directory
        if root.is_dir():
            link_skill(skill, root / "skills" / "tldr-recap")
            linked = True
        else:
            print(f"Skipped {name}: {root} not found")
    if not linked:
        print("No fitting harness found, the skill was not linked")


def main() -> None:
    """Install the command and expose the shared skill to installed harnesses."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--links-only", action="store_true")
    args = parser.parse_args()

    project = Path(__file__).resolve().parents[1]
    skill = project / "skill" / "tldr-recap"
    if not args.links_only:
        subprocess.run(
            ["uv", "tool", "install", "--editable", str(project)], check=True
        )

    link_harnesses(skill, args.home)


if __name__ == "__main__":
    main()

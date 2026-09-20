"""Output path helpers."""

import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path


def slugify(value: str) -> str:
    """Return a short filesystem-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "meeting"


def default_output_dir(
    media_paths: Iterable[Path],
    base_dir: Path | None = None,
    now: datetime | None = None,
) -> Path:
    """Build a timestamped output directory from the first media filename."""
    first = next(iter(media_paths))
    timestamp = (now or datetime.now()).strftime("%Y-%m-%d_%H-%M")
    root = base_dir or Path.cwd() / "meetings"
    candidate = root / f"{timestamp}-{slugify(first.stem)}"
    suffix = 2
    while candidate.exists():
        candidate = root / f"{timestamp}-{slugify(first.stem)}-{suffix}"
        suffix += 1
    return candidate

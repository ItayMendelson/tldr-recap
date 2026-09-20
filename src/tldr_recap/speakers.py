"""Apply user-provided names to speaker-labeled transcripts."""

import json
from collections.abc import Iterable
from pathlib import Path

from .remote_transcribe import write_transcript_markdown


def parse_speaker_mappings(values: Iterable[str]) -> dict[str, str]:
    """Parse LABEL=name arguments such as SPEAKER_00=Alice."""
    mappings = {}
    for value in values:
        label, separator, name = value.partition("=")
        label = label.strip()
        name = name.strip()
        if not separator or not label or not name:
            raise ValueError(
                f"Invalid speaker mapping '{value}'. Use LABEL=Name."
            )
        if label in mappings:
            raise ValueError(f"Duplicate speaker mapping: {label}")
        mappings[label] = name
    return mappings


def rename_speakers(output_dir: Path, mappings: dict[str, str]) -> Path:
    """Rename speakers in transcript JSON and regenerate its Markdown view."""
    output_dir = output_dir.expanduser().resolve()
    transcript_path = output_dir / "transcript.json"
    if not transcript_path.is_file():
        raise ValueError(f"Transcript not found: {transcript_path}")

    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    known_labels = {
        str(word["speaker"])
        for part in transcript["parts"]
        for segment in part["segments"]
        for word in segment["words"]
        if word.get("speaker")
    }
    known_labels.update(
        str(segment["speaker"])
        for part in transcript["parts"]
        for segment in part["segments"]
        if segment.get("speaker")
    )
    unknown = sorted(set(mappings) - known_labels)
    if unknown:
        available = ", ".join(sorted(known_labels)) or "none"
        raise ValueError(
            f"Unknown speaker label(s): {', '.join(unknown)}. "
            f"Available labels: {available}."
        )

    for part in transcript["parts"]:
        for segment in part["segments"]:
            speaker = segment.get("speaker")
            if speaker in mappings:
                segment["speaker"] = mappings[speaker]
            for word in segment["words"]:
                speaker = word.get("speaker")
                if speaker in mappings:
                    word["speaker"] = mappings[speaker]

    transcript_path.write_text(
        json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_transcript_markdown(
        transcript["parts"], output_dir / "transcript.md"
    )
    return output_dir

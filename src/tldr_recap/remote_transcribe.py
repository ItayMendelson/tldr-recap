"""Remote Colab worker for transcription and speaker diarization.

This file runs on the Colab runtime through `colab exec -f` and is also
imported locally by `speakers.py`, so its top-level imports must stay in
the standard library.
"""

import gc
import json
import os
import shutil
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONFIG_PATH = Path("/content/tldr-recap/job.json")
STATUS_PATH = Path("/content/tldr-recap/stage-status.json")


def transcribe_inputs(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Transcribe every configured input with word-level timestamps."""
    print("Loading Whisper libraries...", flush=True)
    from faster_whisper import WhisperModel

    token_path = Path(config["hf_token_path"])
    if token_path.is_file():
        os.environ["HF_TOKEN"] = token_path.read_text(encoding="utf-8").strip()
    print(f"Loading Whisper model {config['model']}...", flush=True)
    model = WhisperModel(config["model"], device="cuda", compute_type="float16")
    print("Whisper model ready.", flush=True)
    requested_language = config["language"]
    language = None if requested_language == "auto" else requested_language
    parts = []

    for item in config["inputs"]:
        print(f"Transcribing {item['name']}...", flush=True)
        segments, info = model.transcribe(
            item["path"],
            language=language,
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        segment_data = []
        for segment in segments:
            words = [
                {
                    "start": word.start,
                    "end": word.end,
                    "text": word.word,
                    "probability": word.probability,
                    "speaker": None,
                }
                for word in (segment.words or [])
            ]
            segment_data.append(
                {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                    "speaker": None,
                    "words": words,
                }
            )

        parts.append(
            {
                "name": item["name"],
                "path": item["path"],
                "duration": info.duration,
                "language": info.language,
                "language_probability": info.language_probability,
                "segments": segment_data,
            }
        )
        print(
            f"Transcribed {item['name']} into {len(segment_data)} segments.",
            flush=True,
        )

    del model
    gc.collect()
    print("Whisper transcription complete.", flush=True)
    return parts


def diarize_inputs(
    parts: list[dict[str, Any]], config: dict[str, Any]
) -> None:
    """Attach pyannote speaker labels to words and segments."""
    print("Loading speaker diarization libraries...", flush=True)
    import torch
    from pyannote.audio import Pipeline

    token_path = Path(config["hf_token_path"])
    token = token_path.read_text(encoding="utf-8").strip()
    token_path.unlink()
    print("Loading the speaker diarization model...", flush=True)
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-community-1", token=token
    )
    pipeline.to(torch.device("cuda"))
    print("Speaker diarization model ready.", flush=True)

    for number, part in enumerate(parts, start=1):
        print(f"Identifying speakers in {part['name']}...", flush=True)
        options = {}
        if config.get("num_speakers"):
            options["num_speakers"] = config["num_speakers"]
        output = pipeline(part["path"], **options)
        annotation = output.exclusive_speaker_diarization
        prefix = f"PART{number}_" if len(parts) > 1 else ""
        intervals = _speaker_intervals(
            annotation.itertracks(yield_label=True), prefix
        )
        _assign_speakers(part["segments"], intervals)
        print(f"Speaker labels complete for {part['name']}.", flush=True)


def _speaker_intervals(
    tracks: Iterable[Any], prefix: str = ""
) -> list[dict[str, Any]]:
    """Normalize pyannote tracks into anonymous labels for one recording.

    Speakers are identified separately in each recording, so labels are only
    comparable within it. The prefix keeps them distinct across parts.
    """
    labels: dict[str, str] = {}
    intervals = []
    for turn, _, raw_label in tracks:
        label = str(raw_label)
        if label not in labels:
            labels[label] = f"{prefix}SPEAKER_{len(labels):02d}"
        intervals.append(
            {"start": turn.start, "end": turn.end, "speaker": labels[label]}
        )
    return intervals


def _speaker_for(
    start: float, end: float, intervals: list[dict[str, Any]]
) -> str | None:
    """Choose the speaker interval with the greatest time overlap."""
    overlaps = []
    for interval in intervals:
        overlap = max(
            0.0,
            min(end, interval["end"]) - max(start, interval["start"]),
        )
        if overlap:
            overlaps.append((overlap, interval["speaker"]))
    return max(overlaps, default=(0.0, None))[1]


def _assign_speakers(
    segments: list[dict[str, Any]], intervals: list[dict[str, Any]]
) -> None:
    """Assign speakers to words, then use the word majority for segments."""
    for segment in segments:
        speakers = []
        for word in segment["words"]:
            speaker = _speaker_for(word["start"], word["end"], intervals)
            word["speaker"] = speaker
            if speaker:
                speakers.append(speaker)
        if speakers:
            segment["speaker"] = Counter(speakers).most_common(1)[0][0]
        else:
            segment["speaker"] = _speaker_for(
                segment["start"], segment["end"], intervals
            )


def transcript_turns(part: dict[str, Any]) -> list[dict[str, Any]]:
    """Group adjacent words from the same speaker into readable turns."""
    turns = []
    current = None
    for segment in part["segments"]:
        words = segment["words"]
        if not words:
            words = [
                {
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": " " + segment["text"],
                    "speaker": segment["speaker"],
                }
            ]
        for word in words:
            speaker = word.get("speaker") or "SPEAKER_UNKNOWN"
            starts_new_turn = (
                current is None
                or current["speaker"] != speaker
                or word["start"] - current["end"] > 2.0
            )
            if starts_new_turn:
                current = {
                    "start": word["start"],
                    "end": word["end"],
                    "speaker": speaker,
                    "text": word["text"],
                }
                turns.append(current)
            else:
                current["end"] = word["end"]
                current["text"] += word["text"]
    for turn in turns:
        turn["text"] = turn["text"].strip()
    return turns


def _timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def write_transcript_markdown(
    parts: list[dict[str, Any]], output_path: Path
) -> None:
    """Write a readable transcript from structured transcript parts."""
    markdown = ["# Meeting transcript", ""]
    for part in parts:
        markdown.extend(
            [
                f"## {part['name']}",
                "",
                f"Language: {part['language']}",
                "",
            ]
        )
        for turn in transcript_turns(part):
            markdown.extend(
                [
                    f"[{_timestamp(turn['start'])}] {turn['speaker']}",
                    turn["text"],
                    "",
                ]
            )
    output_path.write_text(
        "\n".join(markdown).rstrip() + "\n", encoding="utf-8"
    )


def write_artifacts(
    parts: list[dict[str, Any]],
    config: dict[str, Any],
    diarization: bool,
) -> None:
    """Write transcript and metadata artifacts, then create a zip bundle."""
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    transcript = {
        "model": config["model"],
        "requested_language": config["language"],
        "diarization": diarization,
        "parts": parts,
    }
    (output_dir / "transcript.json").write_text(
        json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    write_transcript_markdown(parts, output_dir / "transcript.md")

    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": config["model"],
        "device": "cuda",
        "requested_language": config["language"],
        "detected_languages": [
            {
                "input": part["name"],
                "language": part["language"],
                "probability": part["language_probability"],
            }
            for part in parts
        ],
        "diarization": diarization,
        "inputs": [part["name"] for part in parts],
        "total_duration_seconds": sum(part["duration"] for part in parts),
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    archive = Path(config["archive_path"])
    shutil.make_archive(str(archive.with_suffix("")), "zip", output_dir)


def load_transcribed_parts(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Load the transcript checkpoint produced by the transcription stage."""
    transcript_path = Path(config["output_dir"]) / "transcript.json"
    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    parts = transcript["parts"]
    inputs = config["inputs"]
    if len(parts) != len(inputs):
        raise ValueError(
            "Transcript part count does not match the supplied recordings"
        )
    for part, item in zip(parts, inputs):
        part["path"] = item["path"]
    return parts


def write_stage_status(
    stage: str, status: str, error: Exception | None = None
) -> None:
    """Write a machine-readable result for the local orchestrator."""
    result = {"stage": stage, "status": status}
    if error is not None:
        result.update(
            {
                "error_type": type(error).__name__,
                "message": str(error),
            }
        )
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(result), encoding="utf-8")


def main() -> None:
    """Run one configured remote processing stage."""
    stage = "unknown"
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        stage = config.get("stage", "transcribe")
        if stage == "transcribe":
            parts = transcribe_inputs(config)
            print("Writing the transcript checkpoint...", flush=True)
            write_artifacts(parts, config, diarization=False)
        elif stage == "diarize":
            print("Loading the transcript checkpoint...", flush=True)
            parts = load_transcribed_parts(config)
            diarize_inputs(parts, config)
            print("Writing speaker-labeled artifacts...", flush=True)
            write_artifacts(parts, config, diarization=True)
        else:
            raise ValueError(f"Unknown processing stage: {stage}")
        write_stage_status(stage, "success")
        print(f"Created {config['archive_path']}", flush=True)
    except Exception as error:
        write_stage_status(stage, "error", error)
        print(f"{stage} failed: {type(error).__name__}: {error}", flush=True)
        raise


if __name__ == "__main__":
    main()

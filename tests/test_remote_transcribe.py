"""Tests for transcript speaker alignment and formatting."""

import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tldr_recap.remote_transcribe import (
    _assign_speakers,
    _speaker_for,
    _speaker_intervals,
    diarize_inputs,
    load_transcribed_parts,
    transcribe_inputs,
    transcript_turns,
    write_artifacts,
)


class RemoteTranscribeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.intervals = [
            {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
            {"start": 2.0, "end": 4.0, "speaker": "SPEAKER_01"},
        ]

    def test_speaker_for_uses_greatest_overlap(self) -> None:
        self.assertEqual(_speaker_for(1.8, 2.6, self.intervals), "SPEAKER_01")

    def test_assign_speakers_uses_word_majority(self) -> None:
        segments = [
            {
                "start": 0.5,
                "end": 3.0,
                "text": "hello there yes",
                "speaker": None,
                "words": [
                    {
                        "start": 0.5,
                        "end": 1.0,
                        "text": " hello",
                        "speaker": None,
                    },
                    {
                        "start": 2.1,
                        "end": 2.4,
                        "text": " there",
                        "speaker": None,
                    },
                    {
                        "start": 2.5,
                        "end": 2.8,
                        "text": " yes",
                        "speaker": None,
                    },
                ],
            }
        ]
        _assign_speakers(segments, self.intervals)
        self.assertEqual(segments[0]["speaker"], "SPEAKER_01")

    def test_speaker_intervals_prefix_labels(self) -> None:
        turn = SimpleNamespace(start=0.0, end=1.0)
        tracks = [(turn, None, "A"), (turn, None, "B"), (turn, None, "A")]
        plain = _speaker_intervals(tracks)
        prefixed = _speaker_intervals(tracks, "PART2_")
        self.assertEqual(
            [item["speaker"] for item in plain],
            ["SPEAKER_00", "SPEAKER_01", "SPEAKER_00"],
        )
        self.assertEqual(prefixed[0]["speaker"], "PART2_SPEAKER_00")

    def test_diarization_labels_are_distinct_across_parts(self) -> None:
        def part(name):
            word = {"start": 0.0, "end": 1.0, "text": " hi", "speaker": None}
            return {
                "name": name,
                "path": f"/content/{name}",
                "segments": [
                    {"start": 0.0, "end": 1.0, "text": "hi", "speaker": None,
                     "words": [dict(word)]}
                ],
            }

        class FakePipeline:
            @classmethod
            def from_pretrained(cls, name, token):
                return cls()

            def to(self, device):
                pass

            def __call__(self, path):
                turn = SimpleNamespace(start=0.0, end=1.0)
                tracks = [(turn, None, "X")]
                annotation = SimpleNamespace(
                    itertracks=lambda yield_label: iter(tracks)
                )
                return SimpleNamespace(exclusive_speaker_diarization=annotation)

        modules = {
            "torch": SimpleNamespace(device=lambda name: name),
            "pyannote": SimpleNamespace(),
            "pyannote.audio": SimpleNamespace(Pipeline=FakePipeline),
        }
        with tempfile.TemporaryDirectory() as temporary:
            token_path = Path(temporary) / "hf_token"
            token_path.write_text("token", encoding="utf-8")
            config = {"hf_token_path": str(token_path)}
            single = [part("one.mp4")]
            multiple = [part("one.mp4"), part("two.mp4")]
            with patch.dict(sys.modules, modules):
                diarize_inputs(single, config)
                token_path.write_text("token", encoding="utf-8")
                diarize_inputs(multiple, config)

        self.assertEqual(single[0]["segments"][0]["speaker"], "SPEAKER_00")
        self.assertEqual(
            [item["segments"][0]["speaker"] for item in multiple],
            ["PART1_SPEAKER_00", "PART2_SPEAKER_00"],
        )

    def test_transcript_turns_groups_adjacent_words(self) -> None:
        part = {
            "segments": [
                {
                    "start": 0.0,
                    "end": 2.0,
                    "text": "Hello there",
                    "speaker": "SPEAKER_00",
                    "words": [
                        {
                            "start": 0.0,
                            "end": 0.5,
                            "text": " Hello",
                            "speaker": "SPEAKER_00",
                        },
                        {
                            "start": 0.5,
                            "end": 1.0,
                            "text": " there",
                            "speaker": "SPEAKER_00",
                        },
                    ],
                }
            ]
        }
        self.assertEqual(transcript_turns(part)[0]["text"], "Hello there")

    def test_write_artifacts_creates_expected_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            part = {
                "name": "meeting.mp4",
                "path": "/content/meeting.mp4",
                "duration": 2.0,
                "language": "en",
                "language_probability": 0.99,
                "segments": [],
            }
            config = {
                "model": "large-v3",
                "language": "auto",
                "output_dir": str(root / "output"),
                "archive_path": str(root / "artifacts.zip"),
            }
            write_artifacts([part], config, diarization=False)
            with zipfile.ZipFile(root / "artifacts.zip") as bundle:
                self.assertEqual(
                    sorted(bundle.namelist()),
                    ["metadata.json", "transcript.json", "transcript.md"],
                )

    def test_checkpoint_can_be_loaded_for_diarization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            part = {
                "name": "meeting.mp4",
                "path": "/content/meeting.mp4",
                "duration": 2.0,
                "language": "en",
                "language_probability": 0.99,
                "segments": [],
            }
            config = {
                "model": "large-v3",
                "language": "auto",
                "inputs": [
                    {
                        "name": "meeting.mp4",
                        "path": "/content/new-session/meeting.mp4",
                    }
                ],
                "output_dir": str(root / "output"),
                "archive_path": str(root / "transcription.zip"),
            }
            write_artifacts([part], config, diarization=False)
            loaded = load_transcribed_parts(config)
            self.assertEqual(
                loaded[0]["path"], "/content/new-session/meeting.mp4"
            )

    def test_whisper_download_uses_hugging_face_token(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            token_path = Path(temporary) / "hf_token"
            token_path.write_text("secret-token", encoding="utf-8")
            observed = {}

            class FakeWhisperModel:
                def __init__(self, *args, **kwargs):
                    observed["token"] = os.environ.get("HF_TOKEN")

            fake_module = SimpleNamespace(WhisperModel=FakeWhisperModel)
            config = {
                "model": "large-v3",
                "language": "auto",
                "inputs": [],
                "hf_token_path": str(token_path),
            }
            with patch.dict(sys.modules, {"faster_whisper": fake_module}), patch.dict(
                os.environ, {}, clear=True
            ):
                transcribe_inputs(config)

            self.assertEqual(observed["token"], "secret-token")

    def test_transcribe_accepts_any_detected_language(self) -> None:
        info = SimpleNamespace(
            language="fr", duration=1.0, language_probability=0.9
        )

        class FakeWhisperModel:
            def __init__(self, *args, **kwargs):
                pass

            def transcribe(self, path, **kwargs):
                return iter([]), info

        fake_module = SimpleNamespace(WhisperModel=FakeWhisperModel)
        config = {
            "model": "large-v3",
            "language": "auto",
            "inputs": [{"name": "meeting.mp4", "path": "/content/meeting.mp4"}],
            "hf_token_path": "/nonexistent/hf_token",
        }
        with patch.dict(sys.modules, {"faster_whisper": fake_module}):
            parts = transcribe_inputs(config)

        self.assertEqual(parts[0]["language"], "fr")


if __name__ == "__main__":
    unittest.main()

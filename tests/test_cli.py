"""Tests for command-line validation."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tldr_recap.cli import (
    build_parser,
    huggingface_token_path,
    load_hf_token,
    run,
    validate_media,
)


def write_transcript(output_dir: Path) -> None:
    """Write a one-speaker transcript checkpoint."""
    word = {"start": 0.0, "end": 1.0, "text": " Hello", "speaker": "SPEAKER_00"}
    segment = {
        "start": 0.0,
        "end": 1.0,
        "text": "Hello",
        "speaker": "SPEAKER_00",
        "words": [word],
    }
    part = {"name": "meeting.mp4", "language": "en", "segments": [segment]}
    (output_dir / "transcript.json").write_text(
        json.dumps({"parts": [part]}), encoding="utf-8"
    )


class CliTests(unittest.TestCase):
    def test_validate_media_resolves_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            media = Path(temporary) / "meeting.mp4"
            media.touch()
            self.assertEqual(validate_media([media]), [media.resolve()])

    def test_validate_media_rejects_missing_file(self) -> None:
        with self.assertRaisesRegex(ValueError, "Media file not found"):
            validate_media([Path("missing.mp4")])

    @patch.dict("os.environ", {"HF_TOKEN": "token-from-env"})
    def test_load_hf_token_prefers_environment(self) -> None:
        self.assertEqual(load_hf_token(), "token-from-env")

    @patch.dict("os.environ", {}, clear=True)
    def test_load_hf_token_reads_standard_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            token_path = Path(temporary) / "hf_token"
            token_path.write_text("token-from-file\n", encoding="utf-8")
            with patch.dict("os.environ", {"HF_TOKEN_PATH": str(token_path)}):
                self.assertEqual(load_hf_token(), "token-from-file")

    @patch.dict(
        "os.environ", {"HF_HOME": "/tmp/hf-home", "HF_TOKEN_PATH": ""}, clear=True
    )
    def test_huggingface_token_path_honors_hf_home(self) -> None:
        self.assertEqual(huggingface_token_path(), Path("/tmp/hf-home/token"))

    def test_speakers_command_updates_both_transcript_formats(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            write_transcript(output_dir)

            run(["speakers", str(output_dir), "SPEAKER_00=Alice"])

            updated_json = (output_dir / "transcript.json").read_text(encoding="utf-8")
            updated_markdown = (output_dir / "transcript.md").read_text(
                encoding="utf-8"
            )
            self.assertIn('"speaker": "Alice"', updated_json)
            self.assertIn("] Alice", updated_markdown)

    def test_speakers_command_can_correct_a_name_later(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            write_transcript(output_dir)

            run(["speakers", str(output_dir), "SPEAKER_00=Dan"])
            run(["speakers", str(output_dir), "Dan=Dana"])

            markdown = (output_dir / "transcript.md").read_text(encoding="utf-8")
            self.assertIn("] Dana", markdown)
            self.assertNotIn("] Dan\n", markdown)

    @patch("tldr_recap.cli.load_hf_token", return_value="token")
    @patch("tldr_recap.cli.ColabJob")
    def test_diarize_command_retries_existing_output(
        self, job_class, _load_token
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = root / "meeting.mp4"
            media.touch()
            output_dir = root / "output"
            output_dir.mkdir()

            result = run(
                [
                    "diarize",
                    str(media),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(result, output_dir.resolve())
            job_class.return_value.run_diarization.assert_called_once_with()

    def test_language_accepts_any_whisper_code(self) -> None:
        args = build_parser().parse_args(["meeting.mp4", "--language", "fr"])
        self.assertEqual(args.language, "fr")

    @patch.dict("os.environ", {"HF_TOKEN": "secret"})
    @patch("tldr_recap.cli.ColabJob")
    def test_no_diarization_does_not_forward_token(self, job_class) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = root / "meeting.mp4"
            media.touch()

            run([str(media), "--no-diarization", "--output-dir", str(root / "out")])

            self.assertIsNone(job_class.call_args.kwargs["hf_token"])


if __name__ == "__main__":
    unittest.main()

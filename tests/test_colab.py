"""Tests for Colab job lifecycle behavior."""

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tldr_recap.colab import (
    REMOTE_STAGE_STATUS,
    ColabJob,
    ColabUnavailable,
    CommandFailed,
)


class FakeColabJob(ColabJob):
    """Colab job that records commands and synthesizes a result archive."""

    def __post_init__(self) -> None:
        self.commands = []

    def _run(self, command, input_text=None, check=True):
        self.commands.append(command)
        if "upload" in command and command[-1].endswith("job.json"):
            config = json.loads(Path(command[-2]).read_text(encoding="utf-8"))
            self.stage = config["stage"]
        if "download" in command:
            destination = Path(command[-1])
            if command[-2] == REMOTE_STAGE_STATUS:
                destination.write_text(
                    json.dumps({"stage": self.stage, "status": "success"}),
                    encoding="utf-8",
                )
            else:
                with zipfile.ZipFile(destination, "w") as bundle:
                    bundle.writestr("transcript.md", "# Meeting transcript\n")
                    bundle.writestr("transcript.json", "{}")
                    bundle.writestr("metadata.json", "{}")
        return ""


class FailingDiarizationJob(FakeColabJob):
    """Colab job whose diarization stage reports its original exception."""

    def _run(self, command, input_text=None, check=True):
        if (
            "download" in command
            and command[-2] == REMOTE_STAGE_STATUS
            and self.stage == "diarize"
        ):
            self.commands.append(command)
            Path(command[-1]).write_text(
                json.dumps(
                    {
                        "stage": "diarize",
                        "status": "error",
                        "error_type": "ImportError",
                        "message": "broken numpy",
                    }
                ),
                encoding="utf-8",
            )
            return ""
        return super()._run(command, input_text, check)


class ColabJobTests(unittest.TestCase):
    @patch("tldr_recap.colab.shutil.which", return_value="/usr/local/bin/colab")
    def test_job_downloads_artifacts_and_stops_session(self, _which) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = root / "meeting.mp4"
            media.touch()
            job = FakeColabJob(
                media=[media],
                output_dir=root / "output",
                language="auto",
                model="large-v3",
                gpu="T4",
                diarize=False,
                num_speakers=None,
                hf_token=None,
            )
            job.commands = []
            job.run()
            self.assertTrue((job.output_dir / "transcript.md").is_file())
            install_index = next(
                index
                for index, command in enumerate(job.commands)
                if "install" in command
            )
            restart_index = next(
                index
                for index, command in enumerate(job.commands)
                if "restart-kernel" in command
            )
            upload_index = next(
                index
                for index, command in enumerate(job.commands)
                if "upload" in command
            )
            self.assertLess(install_index, restart_index)
            self.assertLess(restart_index, upload_index)
            self.assertIn("stop", job.commands[-1])

    @patch("tldr_recap.colab.shutil.which", return_value="/usr/local/bin/colab")
    def test_diarization_downloads_transcript_before_second_stage(self, _which) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = root / "meeting.mp4"
            media.touch()
            job = FakeColabJob(
                media=[media],
                output_dir=root / "output",
                language="auto",
                model="large-v3",
                gpu="T4",
                diarize=True,
                num_speakers=None,
                hf_token="token",
            )
            job.commands = []
            job.run()
            workers = [
                index
                for index, command in enumerate(job.commands)
                if "exec" in command and "-f" in command
            ]
            downloads = [
                index
                for index, command in enumerate(job.commands)
                if "download" in command and command[-2].endswith(".zip")
            ]
            self.assertEqual(len(workers), 2)
            self.assertEqual(len(downloads), 2)
            self.assertLess(workers[0], downloads[0])
            self.assertLess(downloads[0], workers[1])
            self.assertLess(workers[1], downloads[1])

    @patch("tldr_recap.colab.shutil.which", return_value="/usr/local/bin/colab")
    def test_diarization_failure_preserves_transcript_checkpoint(self, _which) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = root / "meeting.mp4"
            media.touch()
            job = FailingDiarizationJob(
                media=[media],
                output_dir=root / "output",
                language="auto",
                model="large-v3",
                gpu="T4",
                diarize=True,
                num_speakers=None,
                hf_token="token",
            )
            job.commands = []
            with self.assertRaisesRegex(
                CommandFailed,
                "diarize failed: ImportError: broken numpy",
            ):
                job.run()
            self.assertTrue((job.output_dir / "transcript.md").is_file())
            self.assertTrue((job.output_dir / "transcription.log").is_file())

    @patch("tldr_recap.colab.shutil.which", return_value="/usr/local/bin/colab")
    def test_diarization_retry_uses_existing_checkpoint(self, _which) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = root / "meeting.mp4"
            media.touch()
            output_dir = root / "output"
            output_dir.mkdir()
            transcript_path = output_dir / "transcript.json"
            transcript_path.write_text(
                json.dumps(
                    {
                        "model": "large-v3",
                        "requested_language": "auto",
                        "parts": [{"name": "meeting.mp4"}],
                    }
                ),
                encoding="utf-8",
            )
            job = FakeColabJob(
                media=[media],
                output_dir=output_dir,
                language="auto",
                model="large-v3",
                gpu="T4",
                diarize=True,
                num_speakers=None,
                hf_token="token",
            )
            job.commands = []

            job.run_diarization()

            install = next(command for command in job.commands if "install" in command)
            self.assertIn("pyannote.audio>=4,<5", install)
            self.assertNotIn("faster-whisper", install)
            self.assertTrue(
                any(
                    "upload" in command
                    and command[-2] == str(transcript_path)
                    and command[-1].endswith("output/transcript.json")
                    for command in job.commands
                )
            )
            workers = [
                command
                for command in job.commands
                if "exec" in command and "-f" in command
            ]
            self.assertEqual(len(workers), 1)

    @patch("tldr_recap.colab.shutil.which", return_value=None)
    def test_missing_colab_cli_points_to_readme(self, _which) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job = FakeColabJob(
                media=[root / "meeting.mp4"],
                output_dir=root / "output",
                language="auto",
                model="large-v3",
                gpu="T4",
                diarize=False,
                num_speakers=None,
                hf_token=None,
            )
            with self.assertRaisesRegex(ColabUnavailable, "README"):
                job.run()
            self.assertFalse(job.output_dir.exists())


if __name__ == "__main__":
    unittest.main()

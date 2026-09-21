"""Google Colab job orchestration."""

import json
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

REMOTE_ROOT = "/content/tldr-recap"
REMOTE_TRANSCRIPT_ARCHIVE = f"{REMOTE_ROOT}/transcription.zip"
REMOTE_FINAL_ARCHIVE = f"{REMOTE_ROOT}/artifacts.zip"
REMOTE_STAGE_STATUS = f"{REMOTE_ROOT}/stage-status.json"


class ColabUnavailable(RuntimeError):
    """Raised when the Colab CLI is unavailable."""


class CommandFailed(RuntimeError):
    """Raised when a Colab command fails."""


def _require_colab() -> None:
    """Fail early when the Colab CLI is not installed."""
    if shutil.which("colab") is None:
        raise ColabUnavailable(
            "Google Colab CLI was not found. Install it as described in the README."
        )


@dataclass
class ColabJob:
    """Run one remote transcription job and retrieve its artifacts."""

    media: list[Path]
    output_dir: Path
    language: str
    model: str
    gpu: str
    diarize: bool
    num_speakers: int | None
    hf_token: str | None
    history: list[str] = field(default_factory=list, init=False)

    def run(self) -> None:
        """Execute the remote transcription workflow."""
        _require_colab()
        if self.output_dir.exists():
            raise ValueError(f"Output directory already exists: {self.output_dir}")

        self.output_dir.mkdir(parents=True)
        with self._session() as session:
            self._progress("Preparing the Colab runtime...")
            self._prepare_runtime(session)
            self._progress(f"Uploading {len(self.media)} recording(s)...")
            inputs = self._upload_inputs(session)
            self._upload_config(session, inputs, "transcribe")
            self._progress(f"Transcribing with Whisper {self.model}...")
            self._execute_worker(session, "transcribe")
            transcript_archive = (
                REMOTE_TRANSCRIPT_ARCHIVE if self.diarize else REMOTE_FINAL_ARCHIVE
            )
            self._progress("Downloading the transcript checkpoint...")
            self._download_artifacts(session, transcript_archive)
            self._progress("Transcript checkpoint saved locally.")

            if self.diarize:
                self._upload_config(session, inputs, "diarize")
                self._progress("Identifying speakers...")
                self._execute_worker(session, "diarize")
                self._progress("Downloading speaker-labeled artifacts...")
                self._download_artifacts(session, REMOTE_FINAL_ARCHIVE)
            self._progress("Remote processing complete.")

    def run_diarization(self) -> None:
        """Retry speaker diarization from a local transcript checkpoint."""
        _require_colab()
        transcript_path = self.output_dir / "transcript.json"
        if not transcript_path.is_file():
            raise ValueError(f"Transcript checkpoint not found: {transcript_path}")
        transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
        self.model = str(transcript["model"])
        self.language = str(transcript["requested_language"])
        if len(transcript["parts"]) != len(self.media):
            raise ValueError(
                "Transcript part count does not match the supplied recordings"
            )

        with self._session() as session:
            self._progress("Preparing speaker diarization...")
            self._prepare_runtime(session, transcribe=False)
            self._progress(f"Uploading {len(self.media)} recording(s)...")
            inputs = self._upload_inputs(session)
            self._upload_transcript_checkpoint(session, transcript_path)
            self._upload_config(session, inputs, "diarize")
            self._progress("Identifying speakers...")
            self._execute_worker(session, "diarize")
            self._progress("Downloading speaker-labeled artifacts...")
            self._download_artifacts(session, REMOTE_FINAL_ARCHIVE)
            self._progress("Speaker diarization complete.")

    @contextmanager
    def _session(self):
        """Allocate a temporary Colab runtime and always stop it on exit."""
        session = f"tldr-recap-{uuid.uuid4().hex[:8]}"
        try:
            self._progress(f"Allocating a {self.gpu} Colab runtime...")
            self._run(["colab", "new", "-s", session, "--gpu", self.gpu])
            yield session
        except (CommandFailed, OSError, zipfile.BadZipFile):
            self._write_failure_log()
            raise
        finally:
            self._progress("Stopping the temporary Colab runtime...")
            self._run(["colab", "stop", "-s", session], check=False)

    def _prepare_runtime(self, session: str, transcribe: bool = True) -> None:
        setup = (
            "from pathlib import Path; "
            f"Path('{REMOTE_ROOT}/input').mkdir(parents=True, exist_ok=True); "
            f"Path('{REMOTE_ROOT}/output').mkdir(parents=True, exist_ok=True)"
        )
        self._run(["colab", "exec", "-s", session], input_text=setup)
        packages = []
        if transcribe:
            packages.append("faster-whisper")
        if self.diarize:
            packages.append("pyannote.audio>=4,<5")
        self._run(["colab", "install", "-s", session, *packages])
        self._run(["colab", "restart-kernel", "-s", session])

    def _upload_inputs(self, session: str) -> list[dict[str, str]]:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_dir = Path(temporary)
            inputs = []
            for index, path in enumerate(self.media, start=1):
                remote_name = f"{index:03d}-{path.name}"
                remote_path = f"{REMOTE_ROOT}/input/{remote_name}"
                self._run(["colab", "upload", "-s", session, str(path), remote_path])
                inputs.append({"name": path.name, "path": remote_path})

            if self.hf_token:
                token_path = temporary_dir / "hf_token"
                token_path.write_text(self.hf_token, encoding="utf-8")
                self._run(
                    [
                        "colab",
                        "upload",
                        "-s",
                        session,
                        str(token_path),
                        f"{REMOTE_ROOT}/hf_token",
                    ]
                )
        return inputs

    def _upload_transcript_checkpoint(
        self, session: str, transcript_path: Path
    ) -> None:
        """Upload a local transcript for a diarization-only retry."""
        self._run(
            [
                "colab",
                "upload",
                "-s",
                session,
                str(transcript_path),
                f"{REMOTE_ROOT}/output/transcript.json",
            ]
        )

    def _upload_config(
        self, session: str, inputs: list[dict[str, str]], stage: str
    ) -> None:
        """Upload the job configuration for one remote processing stage."""
        archive_path = (
            REMOTE_TRANSCRIPT_ARCHIVE
            if stage == "transcribe" and self.diarize
            else REMOTE_FINAL_ARCHIVE
        )
        config = {
            "stage": stage,
            "inputs": inputs,
            "model": self.model,
            "language": self.language,
            "num_speakers": self.num_speakers,
            "hf_token_path": f"{REMOTE_ROOT}/hf_token",
            "output_dir": f"{REMOTE_ROOT}/output",
            "archive_path": archive_path,
        }
        with tempfile.TemporaryDirectory() as temporary:
            config_path = Path(temporary) / "job.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            self._run(
                [
                    "colab",
                    "upload",
                    "-s",
                    session,
                    str(config_path),
                    f"{REMOTE_ROOT}/job.json",
                ]
            )

    def _execute_worker(self, session: str, stage: str) -> None:
        worker = Path(__file__).with_name("remote_transcribe.py")
        clear_status = (
            "from pathlib import Path; "
            f"Path('{REMOTE_STAGE_STATUS}').unlink(missing_ok=True)"
        )
        self._run(["colab", "exec", "-s", session], input_text=clear_status)
        self._run(
            [
                "colab",
                "exec",
                "-s",
                session,
                "--timeout",
                "21600",
                "-f",
                str(worker),
            ],
            check=False,
        )
        with tempfile.TemporaryDirectory() as temporary:
            status_path = Path(temporary) / "stage-status.json"
            self._run(
                [
                    "colab",
                    "download",
                    "-s",
                    session,
                    REMOTE_STAGE_STATUS,
                    str(status_path),
                ],
                check=False,
            )
            if not status_path.is_file():
                raise CommandFailed(f"{stage} stage did not report status")
            try:
                status = json.loads(status_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                raise CommandFailed(f"{stage} stage returned invalid status") from error
        if status.get("stage") != stage:
            raise CommandFailed(
                f"Expected {stage} status, received {status.get('stage')}"
            )
        if status.get("status") != "success":
            error_type = status.get("error_type", "RemoteError")
            message = status.get("message", "Unknown remote error")
            raise CommandFailed(f"{stage} failed: {error_type}: {message}")

    def _download_artifacts(self, session: str, remote_archive: str) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "artifacts.zip"
            self._run(
                [
                    "colab",
                    "download",
                    "-s",
                    session,
                    remote_archive,
                    str(archive),
                ]
            )
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(self.output_dir)

    def _write_failure_log(self) -> None:
        log = self.output_dir / "transcription.log"
        log.write_text("\n".join(self.history), encoding="utf-8")

    def _run(
        self,
        command: list[str],
        input_text: str | None = None,
        check: bool = True,
    ) -> str:
        printable = " ".join(command)
        print(f"$ {printable}", flush=True)
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE if input_text is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if input_text is not None and process.stdin is not None:
            process.stdin.write(input_text)
            process.stdin.close()

        lines = []
        if process.stdout is not None:
            for line in process.stdout:
                print(line, end="", flush=True)
                lines.append(line.rstrip())
        return_code = process.wait()
        output = "\n".join(lines)
        self.history.append(f"$ {printable}\n{output}")
        if check and return_code != 0:
            raise CommandFailed(
                f"Command failed with exit code {return_code}: {printable}"
            )
        return output

    @staticmethod
    def _progress(message: str) -> None:
        """Print a visible workflow milestone."""
        print(f"[recap] {message}", flush=True)

"""Command-line interface for TLDR Recap."""

import argparse
import os
import sys
from pathlib import Path

from .colab import ColabJob, ColabUnavailable, CommandFailed
from .paths import default_output_dir
from .speakers import parse_speaker_mappings, rename_speakers


NO_TOKEN_MESSAGE = (
    "No Hugging Face token found. Run `hf auth login` or set HF_TOKEN "
    "(see the README)."
)


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="recap",
        description="Transcribe recorded meetings on a Colab GPU.",
    )
    parser.add_argument("media", nargs="+", type=Path, help="Audio or video file")
    parser.add_argument(
        "--language",
        default="auto",
        help="Whisper language code such as en or fr (default: auto-detect)",
    )
    parser.add_argument("--model", default="large-v3", help="Whisper model")
    parser.add_argument("--gpu", default="T4", help="Colab GPU type")
    parser.add_argument("--output-dir", type=Path, help="Local artifact directory")
    parser.add_argument(
        "--no-diarization",
        action="store_true",
        help="Skip speaker labeling",
    )
    parser.add_argument("--num-speakers", type=int, help="Known speaker count")
    return parser


def build_speaker_parser() -> argparse.ArgumentParser:
    """Create the parser for transcript speaker names."""
    parser = argparse.ArgumentParser(
        prog="recap speakers",
        description="Replace anonymous transcript labels with names or roles.",
    )
    parser.add_argument("output_dir", type=Path, help="Meeting artifact directory")
    parser.add_argument(
        "mapping",
        nargs="+",
        help="Speaker mapping such as SPEAKER_00=Alice",
    )
    return parser


def build_diarization_parser() -> argparse.ArgumentParser:
    """Create the parser for retrying speaker diarization."""
    parser = argparse.ArgumentParser(
        prog="recap diarize",
        description="Add speaker labels to an existing transcript checkpoint.",
    )
    parser.add_argument("media", nargs="+", type=Path, help="Audio or video file")
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Existing meeting artifact directory",
    )
    parser.add_argument("--gpu", default="T4", help="Colab GPU type")
    parser.add_argument("--num-speakers", type=int, help="Known speaker count")
    return parser


def validate_media(paths: list[Path]) -> list[Path]:
    """Resolve media paths and reject missing files."""
    resolved = [path.expanduser().resolve() for path in paths]
    missing = [str(path) for path in resolved if not path.is_file()]
    if missing:
        raise ValueError("Media file not found: " + ", ".join(missing))
    return resolved


def huggingface_token_path() -> Path:
    """Return the token path used by huggingface_hub."""
    configured = os.environ.get("HF_TOKEN_PATH")
    if configured:
        return Path(configured).expanduser()
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        return Path(hf_home).expanduser() / "token"
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache).expanduser() / "huggingface" / "token"
    return Path.home() / ".cache" / "huggingface" / "token"


def load_hf_token() -> str | None:
    """Load a Hugging Face token using standard authentication precedence."""
    token = os.environ.get("HF_TOKEN")
    if token:
        return token.strip()
    path = huggingface_token_path()
    if path.is_file():
        return path.read_text(encoding="utf-8").strip() or None
    return None


def run(argv: list[str] | None = None) -> Path:
    """Run the requested command and return its artifact directory."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "speakers":
        return run_speakers(arguments[1:])
    if arguments and arguments[0] == "diarize":
        return run_diarize(arguments[1:])
    return run_transcribe(arguments)


def run_speakers(arguments: list[str]) -> Path:
    """Replace anonymous speaker labels in an existing transcript."""
    args = build_speaker_parser().parse_args(arguments)
    mappings = parse_speaker_mappings(args.mapping)
    return rename_speakers(args.output_dir, mappings)


def run_diarize(arguments: list[str]) -> Path:
    """Retry speaker diarization for an existing transcript checkpoint."""
    args = build_diarization_parser().parse_args(arguments)
    media = validate_media(args.media)
    output_dir = args.output_dir.expanduser().resolve()
    token = load_hf_token()
    if not token:
        raise ValueError(NO_TOKEN_MESSAGE)
    job = ColabJob(
        media=media,
        output_dir=output_dir,
        language="auto",  # replaced from the transcript checkpoint
        model="large-v3",  # replaced from the transcript checkpoint
        gpu=args.gpu,
        diarize=True,
        num_speakers=args.num_speakers,
        hf_token=token,
    )
    job.run_diarization()
    return output_dir


def run_transcribe(arguments: list[str]) -> Path:
    """Transcribe recordings on a Colab GPU."""
    args = build_parser().parse_args(arguments)
    media = validate_media(args.media)
    output_dir = (
        args.output_dir.expanduser().resolve()
        if args.output_dir
        else default_output_dir(media)
    )
    token = load_hf_token()
    if not args.no_diarization and not token:
        raise ValueError(f"{NO_TOKEN_MESSAGE} Or use --no-diarization.")

    job = ColabJob(
        media=media,
        output_dir=output_dir,
        language=args.language,
        model=args.model,
        gpu=args.gpu,
        diarize=not args.no_diarization,
        num_speakers=args.num_speakers,
        hf_token=None if args.no_diarization else token,
    )
    job.run()
    return output_dir


def main() -> None:
    """CLI entry point."""
    try:
        output_dir = run()
    except (ColabUnavailable, CommandFailed, ValueError) as error:
        print(f"recap: {error}", file=sys.stderr)
        raise SystemExit(2)
    print(f"Artifacts saved to: {output_dir}")


if __name__ == "__main__":
    main()

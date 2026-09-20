# TLDR Recap

TLDR Recap turns recorded meetings into timestamped, speaker-labeled transcripts on a temporary Google Colab GPU. An agent skill then writes concise English meeting notes locally. Meetings can be in any language Whisper supports.

## Requirements

- [`uv`](https://docs.astral.sh/uv/)
- The [Google Colab CLI](https://pypi.org/project/google-colab-cli/) (`colab`), installed in step 1 below
- A Google account that can allocate a Colab GPU runtime, and a Hugging Face account for speaker labels
- macOS or Linux.

## Install

1. Install the Google Colab CLI:

   ```text
   uv tool install --with 'jupyter-kernel-client==0.9.0' 'google-colab-cli==0.6.0'
   ```

   Then run `colab sessions` once in an interactive terminal and complete Google's one-time authorization flow. Do this before the first `recap` run, because the prompt needs an interactive terminal.

2. Accept the conditions for `pyannote/speaker-diarization-community-1`, then authenticate with Hugging Face:

   ```text
   uvx --from huggingface_hub hf auth login
   ```

   Speaker labels can be skipped with `--no-diarization`.

3. From this checkout, install the `recap` command and link the shared skill into Codex and Claude:

   ```text
   uv run --no-project scripts/install.py
   ```

   The installer links to this folder instead of copying it, so keep the checkout in place. If you move it, run the installer again from the new location.

## Use

```text
recap /path/to/meeting.mp4
recap part-1.mp4 part-2.mp4 --language he
recap meeting.mp4 --output-dir /path/to/meeting-summary
recap diarize meeting.mp4 --output-dir /path/to/existing-meeting-summary
```

The spoken language is detected automatically. Pass `--language` with a Whisper language code such as `en` or `he` to override it.

Without `--output-dir`, artifacts are written under `./meetings/` in the directory where the command is started.

The normal transcription outputs are `transcript.md`, `transcript.json`, and `metadata.json`.

Speakers are identified separately in each recording. With several recordings the labels are numbered per part (`PART1_SPEAKER_00`, `PART2_SPEAKER_00`), and the same person usually has a different label in each part. Rename them with `recap speakers <output-dir> PART1_SPEAKER_00=Alice PART2_SPEAKER_01=Alice`.

`transcription.log` is created only when the Colab workflow fails. The command reports the original remote stage error when Colab provides one, while the log retains the full command output. The invoking agent writes `meeting-notes.md` after reading the transcript.

## Privacy

Recordings are uploaded to a temporary Google Colab runtime that is stopped when the job ends. When speaker labels are enabled, your Hugging Face token is uploaded to the same runtime and deleted once the model loads. With `--no-diarization` no token is uploaded.

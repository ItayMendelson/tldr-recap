---
name: tldr-recap
description: Transcribe recorded Zoom, Google Meet, Teams, or other audio/video meetings on a Colab GPU and create speaker-labeled English meeting notes. Use when the user wants a meeting recap, transcript, decisions, action items, or follow-ups from a local recording. Do not use for live meeting capture.
---

# TLDR Recap

Turn one or more local meeting recordings into a timestamped transcript and concise English notes. The `recap` command performs transcription and speaker diarization on a temporary Google Colab GPU. The current agent writes the notes locally.

## Before transcription

1. If the user did not supply a recording path, ask for it and stop. Resolve every supplied path; if one does not exist, report its resolved path and stop. Multiple paths represent consecutive parts of one meeting.
2. If the user did not choose an output location, ask whether to use the default under `./meetings/` in the directory where the agent was started or a different path. Pass a chosen path with `--output-dir`; the folder must not exist yet, so ask for a different path if it does.
3. Preserve any user instruction about what the notes should emphasize.
4. Read [setup](references/setup.md) only when `recap` is unavailable, Colab authentication fails, or speaker diarization reports an access-token error.

## Transcribe

Run:

```text
recap <recording-path> [additional-parts...] [--output-dir <path>]
```

The defaults are Whisper `large-v3`, automatic language detection, a T4 GPU, and speaker diarization. Use `--language <code>` with a Whisper language code such as `en` or `fr` only when the user requests it or automatic detection is wrong. Use `--no-diarization` only when the user asks to skip speaker labels or cannot provide the required model access. Use `--num-speakers <n>` when the user says how many people spoke, and `--model` or `--gpu` only when the user asks for a different Whisper model or GPU type. The command downloads an unlabeled transcript checkpoint before starting diarization.

If the command fails, surface the actual error and point to `transcription.log` when it exists. If `transcript.md` and `transcript.json` also exist, transcription succeeded but a later stage failed. Offer to create notes without speaker labels or retry only diarization with:

```text
recap diarize <recording-path> [additional-parts...] --output-dir <existing-folder>
```

The retry requires the original recordings because speaker timing is computed from the audio, but it reuses `transcript.json` and does not rerun Whisper. Do not retry GPU allocation or a failed transcription repeatedly without user direction. Colab cleanup is handled by the command.

## Create notes

1. Read all of `transcript.md`. For a long transcript, read it incrementally and preserve coverage across the entire meeting before synthesizing the notes. Use `transcript.json` when word-level timing or speaker attribution needs verification.
2. Inspect speaker attribution before trusting it. If diarization appears to merge people, split one person across labels, or misattribute a substantial passage, warn the user and preserve that uncertainty in the notes.
3. If anonymous labels are present and identity matters, show a short substantive excerpt for each label and ask the user to map it to a name or role. Allow several labels to map to the same person, and offer to keep any label anonymous. With several recordings, speakers are identified separately in each one and labeled `PART1_SPEAKER_00`, `PART2_SPEAKER_00`, and so on, so one person usually has a different label in every part. Ask which labels are the same person.
4. Apply supplied names to both transcript formats with `recap speakers <output-dir> SPEAKER_00="Name" [SPEAKER_01="Role" ...]`. A wrong name can be corrected by running the command again with the current name, for example `Dan="Dana"`. Skip this step when the user keeps every label anonymous.
5. Read [summary guidelines](references/summary-guidelines.md). If project-aware notes would help, inspect the relevant agent instructions, `README.md`, and focused material under `docs/`; do not pull in unrelated project context.
6. Apply the user's emphasis instruction when supplied.
7. Write `meeting-notes.md` in the selected output directory. Notes are always in English; the transcript remains in the spoken language.
8. Confirm that `meeting-notes.md`, `transcript.md`, `transcript.json`, and `metadata.json` exist before reporting success.
9. Report back in one or two sentences with a one-line summary of the meeting and paths to all four files.

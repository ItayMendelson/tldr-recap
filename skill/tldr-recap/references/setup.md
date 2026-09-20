# Setup and recovery

TLDR Recap requires `uv`, the `recap` command, and Google's `colab` CLI on the local machine.

From the TLDR Recap checkout (the folder that contains `pyproject.toml`; this skill lives at `skill/tldr-recap` inside it), install the project command:

```text
uv tool install --editable .
```

Install the Colab CLI with the pinned command in step 1 of `README.md` in that folder. A plain `uv tool install google-colab-cli` pulls in a `jupyter-kernel-client` release that `colab` cannot use.

Run `colab sessions` in an interactive terminal and complete Google's one-time authorization flow before the first meeting. GPU allocation depends on the user's current Colab quota and may fail when no free accelerator is available.

Speaker diarization uses `pyannote/speaker-diarization-community-1`. The user must accept that model's conditions on Hugging Face, then authenticate with `hf auth login`. If the CLI is not installed, run `uvx --from huggingface_hub hf auth login`. TLDR Recap automatically reads Hugging Face's standard token cache, including `HF_TOKEN_PATH` and `HF_HOME`. The `HF_TOKEN` environment variable also works. The token is uploaded only to the temporary Colab runtime, and only when speaker labels are requested. The remote token file is deleted after the model loads. Use `--no-diarization` when speaker labels are not needed.

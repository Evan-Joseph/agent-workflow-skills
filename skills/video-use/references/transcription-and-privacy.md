# Transcription And Privacy

## When To Transcribe

Use transcription when the edit depends on speech, quotes, speaker turns,
subtitle timing, interview cleanup, voiceover extraction, or content search.
Skip it for pure visual montages, silent clips, or one-command conversions.

## Consent And Sensitivity

ElevenLabs Scribe receives uploaded audio. Confirm before cloud transcription
when material is private, unpublished, course/project confidential, contains
personal conversations, includes identifiable third parties, or may have usage
restrictions.

For sensitive work, prefer one of these paths:

- local-only edit without transcript;
- offline transcription if an approved local tool is available;
- user-confirmed cloud transcription with the minimum necessary files.

## Credential Lookup

The helper uses this order:

1. current process environment: `ELEVENLABS_API_KEY`;
2. private env file: `~/.config/elevenlabs/elevenlabs.env`.

The file can also contain `ELEVENLABS_TEMP_API_KEY`, but helpers do not use it
automatically. Switch to it only when the user explicitly wants the temporary
key used.

Do not write raw keys into Skill docs, project repos, committed `.env` files,
logs, transcripts, or final answers.

## Batch Defaults

- Start with `--workers 2` unless there is a clear reason to raise concurrency.
- Use `--language zh` or `--language en` only when known; otherwise let Scribe
  detect language.
- Use `--num-speakers` when the speaker count is known and diarization matters.
- Reuse cached transcript JSON when present.

## Transcript Handling

Treat transcript JSON as derived project material. Keep it with the edit output
unless the user asks to archive it elsewhere. Avoid pasting full transcripts
into chat; summarize or cite short snippets only when needed.

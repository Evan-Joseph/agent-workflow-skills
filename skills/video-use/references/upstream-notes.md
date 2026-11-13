# Upstream Notes

Source: `https://github.com/browser-use/video-use`

Imported from upstream commit: `92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66`

License: MIT. A copy is kept in `references/upstream-LICENSE-MIT.txt`.

## What Was Imported

Bundled helper scripts from upstream `helpers/`:

- `scripts/render.py`: render an EDL to preview/final video with ffmpeg.
- `scripts/transcribe.py`: extract audio and transcribe with ElevenLabs Scribe.
- `scripts/transcribe_batch.py`: batch transcription wrapper.
- `scripts/grade.py`: automatic or preset color grade support.
- `scripts/timeline_view.py`: inspect timeline structure.
- `scripts/pack_transcripts.py`: package transcript material for editing.

The local Skill keeps the Browser Use workflow but adapts credential handling to
the user's local machine policy: secrets live outside the Skill directory.

## Upstream Workflow To Preserve

1. Put raw footage in a task directory.
2. Inspect footage before deciding the edit.
3. Transcribe when speech content matters.
4. Build an EDL rather than issuing one-off ffmpeg commands.
5. Render previews before expensive full exports.
6. Self-check the final result with media metadata and visual inspection.

## Local Adaptations

- Use `~/.config/elevenlabs/elevenlabs.env` for ElevenLabs keys.
- Use project-local `video-use-output/<slug>/` unless a project convention says
  otherwise.
- Keep `ffmpeg-usage` as the first choice for simple media transformations.

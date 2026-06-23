# AGENTS.md

## Project Context

EchoLab is a hardware-independent audio evaluation toolkit for voice AI input
systems. The primary real-world target is GeePi on Raspberry Pi 5, but EchoLab
itself must remain reusable for other microphones, arrays, speakerphones, wake
word engines, ASR engines, and future audio frontends.

The project goal is not only to record audio. EchoLab should produce objective,
repeatable measurements that answer household UX questions:

- Which microphone or capture mode works best?
- How far can people speak naturally?
- Can a child wake the device?
- Does angle or placement matter?
- Does TV, conversation, or device playback cause false wakes?
- Which GeePi installation is practically best?

## Architecture Rules

- Keep benchmark runners hardware-independent.
- Keep GeePi-specific assumptions out of core logic.
- Keep ReSpeaker-specific assumptions out of core logic.
- Wake Word, ASR, DOA, speaker, and future analyzers must be plugins.
- Benchmark runners should execute enabled plugins and consume generic
  `PluginResult` data.
- Do not hardcode concrete engines such as openWakeWord, Porcupine, Whisper,
  SenseVoice, or cloud ASR into benchmark runners.
- Engine-specific behavior belongs in plugin implementations or external command
  adapters.
- Every benchmark should generate CSV, JSON, and Markdown when practical.
- Reports should preserve raw structured data and provide household-readable
  answers.

## Current Implemented Commands

```bash
echolab inspect
echolab inspect --json
echolab inspect --out reports/inspect
```

```bash
echolab analyze channels \
  --device hw:2,0 \
  --sample-rate 16000 \
  --channels 6 \
  --out reports/channels-respeaker
```

```bash
echolab benchmark wake-asr --interactive
```

```bash
echolab benchmark wake-asr \
  --mic "ReSpeaker mono=plughw:2,0" \
  --distances "0.5,1,2,3" \
  --angles "front,left,right" \
  --trials 5 \
  --condition quiet \
  --phrase "Hey GeePi" \
  --out reports/wake-asr
```

```bash
echolab benchmark placement \
  --mic "ReSpeaker mono=plughw:2,0" \
  --placements "beside GeePi,behind GeePi,under GeePi / raised platform,stand base area" \
  --condition quiet \
  --phrase "Hey GeePi" \
  --out reports/placement
```

## Known Raspberry Pi / ReSpeaker Observations

These are observed facts from one GeePi Raspberry Pi 5 setup. They are useful
examples, not assumptions to hardcode.

- Device: ReSpeaker USB Mic Array v2.1
- ALSA card: `ReSpeaker 4 Mic Array (UAC1.0)`
- Native device: `hw:2,0`
- Mono compatibility device: `plughw:2,0`
- Native capture: `16000 Hz`, `S16_LE`, `6 channels`
- Mixer controls: unavailable on the tested setup
- `plughw:2,0`, `16000 Hz`, `1 channel` works for GeePi mono use
- `hw:2,0`, `16000 Hz`, `6 channels` works for native EchoLab analysis
- Observed channel pattern:
  - CH1 about 18 dB louder than CH2-5
  - CH2-5 similar lower-level speech activity
  - CH6 silent

Do not label those channels as beamformed, raw, or reference unless a plugin or
controlled test provides evidence. Current channel role hints must remain
cautious, such as `likely processed/beamformed or mixed output`,
`likely raw/reference microphone channel`, `likely inactive/silent`, or
`unknown`.

## Plugin Contract

Plugins expose:

- `initialize()`
- `run(context)`
- `metadata()`
- `shutdown()`

The runner passes a `PluginContext` and receives a `PluginResult`. Command
adapters currently support external scripts for Wake Word and ASR:

```bash
--wake-command "python scripts/score_wake.py {wav_path}"
--asr-command "python scripts/run_asr.py {wav_path}"
```

Expected Wake Word JSON:

```json
{"detected": true, "confidence": 0.92, "latency_ms": 430}
```

Expected ASR JSON:

```json
{"text": "hey geepi what is the weather", "latency_ms": 1180}
```

## Development Rules

- Python target is `>=3.11` for Raspberry Pi compatibility.
- Prefer standard library unless a dependency is clearly justified.
- Keep modules small and typed.
- Add or update tests for behavior changes.
- Run tests before finalizing code changes:

```bash
env PYTHONPATH=src python -B -m unittest discover -s tests
```

- Do not read or create secret files.
- Do not require `.env` for current features.
- Do not commit generated reports, WAV files, or local benchmark output unless
  explicitly requested.
- Do not add dashboards yet unless explicitly requested.

## Key Docs

- `README.md`: project overview and quick start
- `docs/raspberry_pi_quickstart.md`: Raspberry Pi workflow
- `docs/commands.md`: CLI reference
- `docs/benchmark_spec.md`: long-term benchmark methodology
- `docs/plugin_architecture.md`: plugin design


# EchoLab Plugin Architecture

EchoLab benchmark runners capture audio, then execute enabled plugins. Runners
do not depend on specific Wake Word, ASR, DOA, speaker, or future analyzer
implementations.

```text
Recorder
  -> AudioPlugin
  -> PluginResult
  -> report writers
```

## Plugin Lifecycle

Every plugin exposes:

- `initialize()`
- `run(context)`
- `metadata()`
- `shutdown()`

`run(context)` receives a `PluginContext` containing:

- `wav_path`
- `trial_id`
- benchmark metadata such as microphone, distance, angle, speaker label, and
  condition

It returns a generic `PluginResult`:

- `plugin_name`
- `plugin_type`
- `data`
- `error`

## Built-In Adapters

EchoLab currently provides command adapters:

- `CommandWakeWordPlugin`
- `CommandAsrPlugin`

These wrap external commands such as:

```bash
python scripts/score_wake.py {wav_path}
python scripts/run_asr.py {wav_path}
```

The command should print JSON. Plain text is accepted for simple ASR scripts.

Wake Word example:

```json
{"detected": true, "confidence": 0.92, "latency_ms": 430}
```

ASR example:

```json
{"text": "hey geepi what is the weather", "latency_ms": 1180}
```

## Rules

- Plugins must not contain GeePi-specific assumptions.
- Benchmarks must not know about concrete engines such as openWakeWord or
  SenseVoice.
- Engine-specific code belongs in plugin implementations or command scripts.
- Reports consume `PluginResult` plus benchmark-level derived fields.


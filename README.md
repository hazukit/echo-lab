# EchoLab

EchoLab is a reusable toolkit for scientifically evaluating microphones and
audio frontends for voice AI systems.

The initial implementation focuses on reproducible benchmark outputs:

- structured benchmark records
- CSV, JSON, and Markdown reports
- hardware-agnostic device abstractions
- WAV-based audio quality metrics

## Benchmark Standard

The long-term evaluation methodology is defined in
[`docs/benchmark_spec.md`](docs/benchmark_spec.md).

## Run An Audio Quality Benchmark

```bash
PYTHONPATH=src python -m echolab audio-quality path/to/sample.wav --out reports/audio-quality
```

This writes:

- `reports/audio-quality.csv`
- `reports/audio-quality.json`
- `reports/audio-quality.md`

## Run A Wake Word + ASR Baseline

On Raspberry Pi, identify ALSA device names first:

```bash
arecord -l
```

Then run a quiet-room household baseline:

```bash
PYTHONPATH=src python -m echolab benchmark wake-asr \
  --mic SunFounder=plughw:1,0 \
  --mic ReSpeaker=plughw:2,0 \
  --speaker-label adult \
  --condition quiet \
  --utterance "Hey GeePi, what time is it?" \
  --expected-text "Hey GeePi what time is it" \
  --out reports/wake-asr
```

This records each microphone at 0.5 m, 1 m, 2 m, and 3 m from front, left, and
right angles. By default EchoLab records WAV files with `arecord`. Wake word and
ASR scoring are optional and can be plugged in with external commands:

```bash
PYTHONPATH=src python -m echolab benchmark wake-asr \
  --mic SunFounder=plughw:1,0 \
  --mic ReSpeaker=plughw:2,0 \
  --wake-command "python scripts/score_wake.py {wav_path}" \
  --asr-command "python scripts/run_asr.py {wav_path}" \
  --expected-text "Hey GeePi what time is it"
```

Expected wake scorer JSON:

```json
{"detected": true, "confidence": 0.92, "latency_ms": 430}
```

Expected ASR JSON:

```json
{"text": "hey geepi what time is it", "latency_ms": 1180}
```

Outputs:

- `reports/wake-asr/wake_asr_results.json`
- `reports/wake-asr/wake_asr_results.csv`
- `reports/wake-asr/wake_asr_report.md`
- `reports/wake-asr/audio/*.wav`

## Run A GeePi Placement Benchmark

Use the placement benchmark to compare physical microphone locations while
reusing the same Wake Word + ASR flow:

```bash
PYTHONPATH=src python -m echolab benchmark placement \
  --mic ReSpeaker=plughw:2,0 \
  --placements "beside GeePi,behind GeePi,under GeePi / raised platform,stand base area" \
  --placement-acceptability "beside GeePi=good" \
  --placement-acceptability "behind GeePi=poor" \
  --placement-acceptability "under GeePi / raised platform=ok" \
  --placement-acceptability "stand base area=good" \
  --speaker-label adult \
  --condition quiet \
  --utterance "Hey GeePi, what time is it?" \
  --expected-text "Hey GeePi what time is it" \
  --out reports/placement
```

The report ranks placements by household usability rather than raw audio level
alone. It answers which placement works best, which fails at distance, whether
under-display placement hurts recognition, and whether the placement is
acceptable for GeePi's physical design.

Outputs:

- `reports/placement/placement_results.json`
- `reports/placement/placement_results.csv`
- `reports/placement/placement_report.md`
- `reports/placement/audio/*.wav`

## Project Layout

```text
src/echolab/
  analysis/
  benchmark/
  devices/
  reporting/
  visualization/
scripts/
datasets/
reports/
tests/
```

EchoLab avoids microphone-specific assumptions. Device-specific integrations
should implement the shared interfaces under `echolab.devices`.

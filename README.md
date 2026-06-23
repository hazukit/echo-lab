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

EchoLab can also inspect capture devices directly:

```bash
PYTHONPATH=src python -m echolab inspect
PYTHONPATH=src python -m echolab inspect --json
PYTHONPATH=src python -m echolab inspect --out reports/inspect
```

The inspect command reports ALSA card/device IDs, likely USB-facing names,
native capture format, sample rate, channel count, mixer availability, and
recommended GeePi mono and EchoLab native-analysis capture modes.

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

To compare GeePi ReSpeaker mono mode against native channel extraction, use an
extended microphone spec. EchoLab records native 6-channel audio from `hw:2,0`
and scores the extracted mono channel:

```bash
PYTHONPATH=src python -m echolab benchmark wake-asr \
  --mic "ReSpeaker mono=plughw:2,0" \
  --mic "ReSpeaker native CH1=hw:2,0;channels=6;extract_channel=1" \
  --mic "SunFounder=plughw:1,0" \
  --distances "0.5,1,2,3" \
  --angles "front,left,right" \
  --trials 5 \
  --speaker-label adult \
  --condition quiet \
  --utterance "Hey GeePi" \
  --wake-command "python scripts/score_wake.py {wav_path}" \
  --out reports/wake-asr-geepi
```

The report compares wake detection rate, false negatives, confidence, latency,
audio RMS/peak, distance drop-off, angle effects, and the recommended GeePi
capture configuration.

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

## Analyze Multi-Channel Capture

Use channel analysis to verify whether a device exposes useful multi-channel
data. For a microphone array, use the native mode recommended by `inspect`:

```bash
PYTHONPATH=src python -m echolab analyze channels \
  --device hw:2,0 \
  --sample-rate 16000 \
  --channels 6 \
  --out reports/channels
```

For normal mono USB microphones, use `--channels 1`. EchoLab reports channel
roles as `unknown` unless a later hardware-specific plugin can prove otherwise.

Outputs:

- `reports/channels/channel_analysis.json`
- `reports/channels/channel_analysis.csv`
- `reports/channels/channel_analysis.md`
- `reports/channels/channel_capture.wav`

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

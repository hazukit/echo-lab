# EchoLab

EchoLab is a reusable toolkit for evaluating microphones and audio frontends for
voice AI systems. The current focus is GeePi household usability, but the core
tooling is hardware-independent.

EchoLab answers practical questions:

- Which microphone or capture mode works best?
- Does wake-word performance drop with distance or angle?
- Does a microphone array expose useful multi-channel data?
- Which physical placement is best for everyday household interaction?
- Which plugins produced each Wake Word, ASR, DOA, or analysis result?

## Current Capabilities

- ALSA device inspection for Raspberry Pi and Linux capture devices
- WAV audio-quality metrics
- Multi-channel analysis with cautious role hints
- Wake Word + ASR benchmark runner
- Interactive repeated Wake Word + ASR trials
- GeePi placement benchmark
- Generic plugin architecture for Wake Word, ASR, DOA, speaker, and future analyzers
- CSV, JSON, and Markdown outputs

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Inspect capture devices:

```bash
echolab inspect
```

Analyze ReSpeaker native 6-channel capture:

```bash
echolab analyze channels \
  --device hw:2,0 \
  --sample-rate 16000 \
  --channels 6 \
  --out reports/channels-respeaker
```

Run interactive Wake Word + ASR trials:

```bash
echolab benchmark wake-asr --interactive
```

Run a focused ReSpeaker mono trial set:

```bash
echolab benchmark wake-asr \
  --mic "ReSpeaker mono=plughw:2,0" \
  --sample-rate 16000 \
  --channels 1 \
  --distances 0.5 \
  --angles front \
  --condition quiet \
  --speaker-label mama \
  --trials 5 \
  --phrase "ジーピー、今日の天気教えて" \
  --out reports/wake-asr-respeaker-05m-front
```

## Documentation

- [Raspberry Pi Quickstart](docs/raspberry_pi_quickstart.md)
- [Command Reference](docs/commands.md)
- [Benchmark Specification](docs/benchmark_spec.md)
- [Plugin Architecture](docs/plugin_architecture.md)

## Project Layout

```text
src/echolab/
  analysis/
  benchmark/
  devices/
  plugins/
  reporting/
  visualization/
docs/
scripts/
datasets/
reports/
tests/
```

EchoLab avoids microphone-specific assumptions. Hardware-specific behavior
should live in optional plugins or adapters, not in benchmark methodology.


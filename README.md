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

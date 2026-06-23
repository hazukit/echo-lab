# Raspberry Pi Quickstart

This guide is for running EchoLab on Raspberry Pi 5 with USB microphones or
microphone arrays such as ReSpeaker USB Mic Array v2.1.

## 1. Install System Tools

```bash
sudo apt update
sudo apt install alsa-utils python3-venv
```

## 2. Set Up Python

From the EchoLab repository:

```bash
cd ~/echo-lab
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Check that the command is installed:

```bash
echolab --help
```

## 3. Inspect Devices

```bash
echolab inspect
```

Expected ReSpeaker-style result:

```text
Native capture: 16000 Hz, S16_LE, 6 channels
Recommended:
- GeePi mono mode: plughw:2,0, 16000 Hz, 1 channel
- EchoLab native analysis mode: hw:2,0, 16000 Hz, 6 channels
```

Save inspection artifacts:

```bash
echolab inspect --out reports/inspect
```

Outputs:

- `reports/inspect/inspect_devices.json`
- `reports/inspect/inspect_devices.csv`
- `reports/inspect/inspect_devices.md`

## 4. Analyze ReSpeaker Channels

Native 6-channel capture:

```bash
echolab analyze channels \
  --device hw:2,0 \
  --sample-rate 16000 \
  --channels 6 \
  --out reports/channels-respeaker
```

GeePi mono compatibility:

```bash
echolab analyze channels \
  --device plughw:2,0 \
  --sample-rate 16000 \
  --channels 1 \
  --out reports/channels-respeaker-mono
```

Outputs:

- `channel_capture.wav`
- `channel_analysis.json`
- `channel_analysis.csv`
- `channel_analysis.md`

Channel role hints are cautious. EchoLab may report hints such as:

- `likely inactive/silent`
- `likely processed/beamformed or mixed output`
- `likely raw/reference microphone channel`
- `unknown`

These are level-based hints, not confirmed hardware roles.

## 5. Run Interactive Wake Trials

```bash
echolab benchmark wake-asr --interactive
```

During each trial:

- Press Enter to record.
- Press Enter again to keep the recording.
- Type `r` to retry.
- Type `s` to skip.
- Type `q` to quit and save results collected so far.
- Type any note to save it with the trial.

Focused non-interactive example:

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

Without a Wake Word plugin, the report includes recording and audio metrics but
Wake detection, confidence, and latency remain `n/a`.

## 6. Add Wake Word Or ASR Scoring

Use command plugins:

```bash
echolab benchmark wake-asr \
  --mic "ReSpeaker mono=plughw:2,0" \
  --distances "0.5,1,2,3" \
  --angles "front,left,right" \
  --trials 5 \
  --wake-command "python scripts/score_wake.py {wav_path}" \
  --asr-command "python scripts/run_asr.py {wav_path}" \
  --out reports/wake-asr-geepi
```

Wake scorer JSON:

```json
{"detected": true, "confidence": 0.92, "latency_ms": 430}
```

ASR JSON:

```json
{"text": "ジーピー 今日の天気 教えて", "latency_ms": 1180}
```

## 7. Recommended GeePi Capture Modes

For current ReSpeaker observations:

```text
GeePi runtime:
  plughw:2,0 / 16000 Hz / 1 channel

EchoLab native analysis:
  hw:2,0 / 16000 Hz / 6 channels
```

Use EchoLab reports to verify this for your actual hardware, room, and placement.


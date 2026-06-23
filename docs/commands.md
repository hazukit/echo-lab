# EchoLab Command Reference

## Device Inspection

```bash
echolab inspect
echolab inspect --json
echolab inspect --markdown
echolab inspect --out reports/inspect
```

Reports:

- ALSA card/device ID
- device name
- likely USB-facing name
- native format
- native sample rate
- native channel count
- mixer availability
- recommended mono and native-analysis capture modes

## Audio Quality

```bash
echolab audio-quality path/to/sample.wav --out reports/audio-quality
```

Outputs:

- `reports/audio-quality.csv`
- `reports/audio-quality.json`
- `reports/audio-quality.md`

## Channel Analysis

```bash
echolab analyze channels \
  --device hw:2,0 \
  --sample-rate 16000 \
  --channels 6 \
  --out reports/channels
```

Options:

- `--device`: ALSA capture device such as `hw:2,0` or `plughw:2,0`
- `--sample-rate`: capture sample rate
- `--channels`: channel count
- `--duration`: recording duration in seconds
- `--format`: ALSA sample format, default `S16_LE`
- `--record-command`: custom recorder command template

Outputs:

- `channel_capture.wav`
- `channel_analysis.json`
- `channel_analysis.csv`
- `channel_analysis.md`

## Wake Word + ASR Benchmark

Interactive:

```bash
echolab benchmark wake-asr --interactive
```

Single microphone:

```bash
echolab benchmark wake-asr \
  --mic "ReSpeaker mono=plughw:2,0" \
  --distances "0.5,1,2,3" \
  --angles "front,left,right" \
  --trials 5 \
  --condition quiet \
  --speaker-label adult \
  --phrase "Hey GeePi" \
  --out reports/wake-asr
```

Compare ReSpeaker mono, ReSpeaker native CH1, and SunFounder:

```bash
echolab benchmark wake-asr \
  --mic "ReSpeaker mono=plughw:2,0" \
  --mic "ReSpeaker native CH1=hw:2,0;channels=6;extract_channel=1" \
  --mic "SunFounder=plughw:1,0" \
  --distances "0.5,1,2,3" \
  --angles "front,left,right" \
  --trials 5 \
  --condition quiet \
  --wake-command "python scripts/score_wake.py {wav_path}" \
  --asr-command "python scripts/run_asr.py {wav_path}" \
  --out reports/wake-asr-geepi
```

Microphone spec:

```text
NAME=DEVICE
NAME=DEVICE;channels=N;extract_channel=M
```

Examples:

```text
ReSpeaker mono=plughw:2,0
ReSpeaker native CH1=hw:2,0;channels=6;extract_channel=1
SunFounder=plughw:1,0
```

Outputs:

- `wake_asr_results.json`
- `wake_asr_results.csv`
- `wake_asr_report.md`
- `audio/*.wav`

## Placement Benchmark

```bash
echolab benchmark placement \
  --mic "ReSpeaker mono=plughw:2,0" \
  --placements "beside GeePi,behind GeePi,under GeePi / raised platform,stand base area" \
  --placement-acceptability "beside GeePi=good" \
  --placement-acceptability "behind GeePi=poor" \
  --condition quiet \
  --phrase "Hey GeePi" \
  --out reports/placement
```

Outputs:

- `placement_results.json`
- `placement_results.csv`
- `placement_report.md`
- `audio/*.wav`

## Plugin Commands

Wake Word command plugins should print JSON:

```json
{"detected": true, "confidence": 0.92, "latency_ms": 430}
```

ASR command plugins should print JSON or plain text:

```json
{"text": "hey geepi what is the weather", "latency_ms": 1180}
```

Command templates support:

- `{wav_path}`
- `{trial_id}`

Example:

```bash
--wake-command "python scripts/score_wake.py {wav_path}"
```


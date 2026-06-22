# EchoLab Benchmark Specification

Version: 0.1  
Status: Draft standard  
Scope: Hardware-independent evaluation of voice AI microphones and audio frontends

## 1. Purpose

EchoLab benchmarks evaluate how well voice AI hardware works in real household
conditions. The goal is not to rank microphones by laboratory audio quality
alone. The goal is to predict and improve day-to-day usability for devices such
as GeePi:

- Can a child wake the device naturally?
- Can an adult speak from across the room?
- Does TV, music, or family conversation cause false wakes?
- Does the device react to its own voice?
- Does installation position improve or harm usability?

Every benchmark must produce structured data so results are reproducible,
comparable across hardware, and useful for future regression tracking.

## 2. Benchmark Principles

1. Measure real user outcomes before synthetic quality.
2. Keep hardware-specific behavior behind adapters.
3. Record all test variables, not just metric values.
4. Use the same scenario definitions across devices.
5. Separate raw capability from household UX performance.
6. Prefer repeatable playback tests, but include human trials for child and
   household behavior when playback is insufficient.
7. Report confidence and uncertainty when trials are limited.
8. Treat pass/fail thresholds as product targets, not universal truths.

## 3. Standard Test Metadata

Every benchmark record must include:

- `run_id`
- `benchmark_name`
- `device_id`
- `device_name`
- `frontend_name`
- `frontend_version`
- `host_platform`
- `os_version`
- `capture_sample_rate_hz`
- `capture_channels`
- `capture_format`
- `room_id`
- `room_description`
- `placement_id`
- `distance_m`
- `angle_deg`
- `speaker_type`
- `background_condition`
- `playback_level_dba`
- `ambient_level_dba`
- `trial_id`
- `timestamp_utc`
- `operator`
- `notes`

Recommended room fields:

- room dimensions
- floor type
- wall materials
- soft furnishings
- reverberation estimate, if available
- device height
- speaker height
- distance from display or speaker

## 4. Standard Report Outputs

Each benchmark must generate:

- CSV: one row per trial or observation
- JSON: complete structured run metadata and metrics
- Markdown: human-readable summary, findings, and limitations

Recommended optional outputs:

- WAV snippets for failed or borderline cases
- charts as PNG or SVG
- HTML dashboard
- historical comparison report

Markdown reports should include:

1. Executive summary
2. Device and frontend configuration
3. Test environment
4. Scenario matrix
5. Aggregate results
6. Pass/fail table, when applicable
7. Notable failures
8. Household UX interpretation
9. Raw artifact links
10. Limitations and follow-up tests

## 5. Standard Scenario Variables

Distances:

- 0.5 m: close interaction
- 1.0 m: normal counter or desk use
- 2.0 m: across a small room
- 3.0 m: across a living room
- 5.0 m: large room or edge case

Angles:

- 0 degrees: front
- 45 degrees
- 90 degrees: side
- 135 degrees
- 180 degrees: rear

Background conditions:

- quiet room
- TV speech
- TV music or mixed content
- music playback
- kitchen noise
- family conversation
- device TTS playback

Speaker types:

- adult female
- adult male
- child
- synthetic playback of adult voice
- synthetic playback of child voice

Placement examples:

- beside display
- behind display
- under display
- elevated display
- raised platform
- shelf
- table surface

## 6. Scoring Model

EchoLab should report raw metrics and a household UX score. The UX score is a
summary, not a replacement for raw results.

Recommended top-level score:

- Wake reliability: 25%
- Speech recognition usability: 25%
- False activation resistance: 20%
- Self voice resistance: 15%
- Installation practicality: 10%
- DOA usefulness: 5%

Each score should be normalized from 0 to 100 and accompanied by the raw
metrics that produced it. If a hardware class does not support DOA, the DOA
weight should be reported as not applicable and excluded from the total rather
than treated as zero.

## 7. Benchmark Category: Device Capability

### Purpose

Measure the static and runtime capabilities of the audio device and frontend.

### Why It Matters

Device capability determines what later benchmarks mean. A microphone array with
six channels, onboard DSP, and DOA metadata is not directly equivalent to a
single-channel USB microphone. Capturing capabilities prevents misleading
comparisons.

### Test Procedure

1. Connect exactly one device under test unless testing interaction with other
   audio devices.
2. Record USB or system audio identity.
3. Enumerate supported sample rates, channel counts, formats, and bit depths.
4. Record default OS-selected format.
5. Measure capture startup time.
6. Measure end-to-end input latency using a repeatable click or impulse test
   when equipment is available.
7. Record whether the frontend exposes DSP features such as AEC, AGC, noise
   suppression, beamforming, VAD, wake word, or DOA.
8. Repeat after reboot for devices that may change enumeration order.

### Required Equipment

- Host machine
- Device under test
- USB cable or required interface
- Optional loopback cable or speaker and measurement microphone for latency
- Audio enumeration tools available on the host OS

### Metrics Collected

- USB vendor ID and product ID
- USB device name
- serial number, if available and non-sensitive
- supported sample rates
- supported channel counts
- bit depth
- sample format
- default sample rate
- default channels
- measured startup time_ms
- measured input latency_ms
- latency standard deviation_ms
- supported DSP features
- driver or firmware version, if available

### Pass/Fail Criteria

This benchmark is primarily descriptive. Suggested minimum for voice AI:

- Pass: stable enumeration across 3 reconnects
- Pass: can capture at 16 kHz mono or better
- Pass: no capture failure in a 10 minute continuous recording
- Warning: input latency above 250 ms
- Fail: device cannot be opened reliably by the benchmark host

### Report Format

CSV rows should represent one observed format or capability. JSON should include
the full device capability tree. Markdown should summarize compatibility risks
and recommended capture settings.

## 8. Benchmark Category: Raw Audio Quality

### Purpose

Measure basic signal quality of captured audio under controlled but realistic
household conditions.

### Why It Matters

Raw audio quality affects wake word, ASR, and speaker analysis. It does not
fully predict UX, but it helps explain failures and compare frontends.

### Test Procedure

1. Place the device in the selected installation position.
2. Record 30 seconds of room tone for each background condition.
3. Play a calibrated speech sample at fixed distance and angle.
4. Record at least 10 seconds per sample.
5. Repeat for target distances and angles.
6. Include a loud near-field utterance to test clipping.
7. Preserve raw WAV files for later analysis.

### Required Equipment

- Device under test
- Playback speaker with stable level
- SPL meter or calibrated phone SPL app
- Fixed test phrases
- Quiet room and household noise sources
- Tape measure
- Angle markers

### Metrics Collected

- RMS level
- peak level
- peak dBFS
- noise floor dBFS
- dynamic range estimate
- signal-to-noise ratio
- clipping ratio
- silent dropout count
- channel balance
- spectral centroid
- optional frequency response estimate

### Pass/Fail Criteria

Suggested minimums:

- Pass: clipping ratio below 0.1% for normal speech
- Pass: no silent dropouts in 10 minute capture
- Warning: SNR below 15 dB for 1 m quiet speech
- Warning: strong channel imbalance on microphone arrays
- Fail: repeated clipping during normal conversation level

### Report Format

CSV rows should represent one recording condition. JSON should include raw
recording artifact references. Markdown should identify whether audio quality is
likely to limit downstream benchmarks.

## 9. Benchmark Category: Wake Word

### Purpose

Evaluate whether the device reliably wakes when intended and avoids waking when
not intended.

### Why It Matters

Wake word behavior strongly shapes trust. Missed wakes make the device feel
unresponsive. False wakes make it feel intrusive or unreliable.

### Test Procedure

1. Select the wake engine and fixed configuration.
2. Calibrate playback or human speech level.
3. For each scenario, run at least 20 positive wake trials.
4. Record distance, angle, speaker type, and background condition.
5. For false positive tests, play or record non-wake household audio for at
   least 30 minutes per condition.
6. For latency, measure from wake word end time to detection event.
7. For child tests, include natural phrasing and imperfect pronunciation when
   possible.
8. Log every detection event, including confidence and timestamp.

### Required Equipment

- Device under test
- Wake word engine
- Playback speaker or human participants
- Wake phrase recordings
- Non-wake household recordings
- SPL meter
- Timing source or synchronized logs

### Metrics Collected

- detection rate
- miss rate
- false positive count_per_hour
- false negative count
- confidence score
- maximum confidence
- mean confidence
- detection latency_ms
- latency p50_ms
- latency p95_ms
- distance_m
- angle_deg
- background condition
- speaker type
- child success rate

### Pass/Fail Criteria

Suggested household targets:

- Pass: 95% detection at 1 m quiet adult speech
- Pass: 90% detection at 2 m quiet adult speech
- Pass: 85% detection at 1 m child speech
- Pass: false positives below 0.1 per hour in TV and conversation conditions
- Warning: p95 latency above 1000 ms
- Fail: any repeatable self-trigger loop

### Report Format

CSV rows should represent one wake trial or one false-positive window. JSON
should include event timelines. Markdown should report a scenario matrix with
detection rate, false positive rate, and latency distribution.

## 10. Benchmark Category: Speech Recognition

### Purpose

Evaluate whether recognized speech is useful for household voice interaction.

### Why It Matters

Users judge the system by whether it understands intent. Perfect audio quality
is irrelevant if ASR returns empty or wrong text in real rooms.

### Test Procedure

1. Fix ASR engine, model, language, and endpointing settings.
2. Define a phrase set representing household commands and open-ended speech.
3. Run trials across speaker types, distances, and background conditions.
4. Include short child commands and across-room adult commands.
5. Measure from speech end to transcript availability.
6. Store expected transcript, actual transcript, and timing.
7. Mark empty recognitions separately from incorrect recognitions.
8. For cloud ASR, record network condition but do not include credentials.

### Required Equipment

- Device under test
- ASR engine
- Phrase list
- Playback speaker or human participants
- SPL meter
- Background noise sources
- Timing logs

### Metrics Collected

- exact match rate
- normalized text match rate
- word error rate, when available
- character error rate, optional
- empty recognition rate
- partial transcript count
- latency_ms
- latency p50_ms
- latency p95_ms
- command success rate
- child recognition rate
- across-room recognition rate

### Pass/Fail Criteria

Suggested household targets:

- Pass: 90% normalized command accuracy at 1 m quiet adult speech
- Pass: 80% normalized command accuracy at 2 m quiet adult speech
- Pass: 75% normalized command accuracy at 1 m child speech
- Pass: empty recognition below 5% in quiet 1 m tests
- Warning: p95 latency above 2500 ms for command use
- Fail: consistent empty results in normal 1 m quiet speech

### Report Format

CSV rows should represent one utterance. JSON should preserve expected and
actual transcripts. Markdown should show confusion examples, empty recognition
patterns, and whether errors would break real commands.

## 11. Benchmark Category: Direction of Arrival

### Purpose

Evaluate whether DOA estimates are accurate and stable enough for practical
home use.

### Why It Matters

DOA can help turn a display, choose a beam, select the active speaker, or
disambiguate where speech came from. Inaccurate DOA can make the device feel
confused.

### Test Procedure

1. Use hardware or frontend that exposes DOA.
2. Place the device with a defined zero-degree reference.
3. Play or speak test phrases at known angles and distances.
4. Record DOA estimates during speech and during silence.
5. Repeat for front, side, rear, and diagonal positions.
6. Include TV and family conversation backgrounds.
7. Measure update frequency and estimate jitter over time.
8. Mark cases where no stable DOA is emitted.

### Required Equipment

- Microphone array or frontend with DOA
- Angle markers
- Tape measure
- Playback speaker or human speaker
- Timing logs
- Optional rotating platform

### Metrics Collected

- estimated angle_deg
- actual angle_deg
- absolute error_deg
- signed error_deg
- median error_deg
- p95 error_deg
- stability_deg
- jitter_deg_per_s
- update_rate_hz
- no_estimate_rate
- wrong_quadrant_rate

### Pass/Fail Criteria

DOA is not required for all devices. When supported:

- Pass: median error below 20 degrees at 1 m quiet speech
- Pass: wrong quadrant below 5% for 0, 90, 180, and 270 degree tests
- Warning: unstable estimates during silence
- Warning: update rate below 2 Hz for interactive use
- Fail: DOA values are not correlated with actual angle

### Report Format

CSV rows should represent one DOA sample or one utterance aggregate. JSON should
include time series when available. Markdown should include polar summary tables
and state which practical uses are supported:

- display orientation
- beam steering
- active speaker hint
- room analytics
- not reliable enough for UX decisions

## 12. Benchmark Category: Speaker Characteristics

### Purpose

Measure observable voice characteristics and estimate whether two consecutive
utterances likely came from the same speaker.

### Why It Matters

Household assistants often need conversational continuity. Full speaker
identification may be inappropriate or unreliable, but short-term speaker
continuity can improve turn-taking and context handling.

### Test Procedure

1. Record or play paired utterances from the same and different speakers.
2. Include adult and child speakers.
3. Extract acoustic features from each utterance.
4. Compare feature distance between consecutive utterances.
5. Evaluate same-speaker versus different-speaker separation.
6. Do not assign real identity labels beyond test participant IDs.
7. Report uncertainty and avoid biometric claims.

### Required Equipment

- Device under test
- Speech recordings or participants
- Feature extraction implementation
- Phrase list
- Consent process for human recordings, when applicable

### Metrics Collected

- pitch mean_hz
- pitch range_hz
- energy mean
- energy variance
- MFCC summary
- embedding vector reference, when available
- speech rate_words_per_minute
- utterance duration_ms
- same-speaker similarity score
- different-speaker similarity score
- equal error rate, optional
- same-speaker decision accuracy, optional

### Pass/Fail Criteria

This benchmark is experimental and should not use strict pass/fail by default.
Suggested interpretation:

- Useful: same-speaker pairs separate from different-speaker pairs in most
  tested conditions
- Warning: child/adult differences dominate all other features
- Warning: background noise changes similarity more than speaker changes
- Fail: system claims identity rather than short-term similarity

### Report Format

CSV rows should represent one utterance or utterance pair. JSON may include
feature vectors by artifact reference rather than inline large arrays. Markdown
must state that this is not speaker identification.

## 13. Benchmark Category: Self Voice Resistance

### Purpose

Evaluate whether the device resists triggering on its own TTS or contaminating
ASR with playback audio.

### Why It Matters

Self-triggering creates loops, interrupts users, and makes a home assistant feel
uncontrolled. Recovery after playback is critical for natural conversation.

### Test Procedure

1. Configure the device speaker and microphone placement exactly as installed.
2. Play representative TTS responses at normal and loud volume.
3. Include TTS containing wake-word-like sounds and normal responses.
4. Measure wake events during playback.
5. Measure wake events in the first 5 seconds after playback.
6. Run ASR while TTS is playing and immediately after.
7. If AEC is available, run tests with AEC on and off.
8. Test user interruption during TTS at 1 m and 2 m.

### Required Equipment

- Device under test
- Playback speaker or built-in speaker
- TTS engine or fixed TTS recordings
- Wake word engine
- ASR engine
- Timing logs
- SPL meter

### Metrics Collected

- wake during TTS count
- wake after TTS count
- false wake rate_per_hour
- ASR contamination rate
- transcript contamination tokens
- recovery time_ms
- barge-in success rate
- AEC suppression estimate_dB
- TTS volume_dba
- user speech SNR during playback

### Pass/Fail Criteria

Suggested household targets:

- Pass: zero self-trigger loops in standard TTS set
- Pass: wake during TTS below 0.05 per hour
- Pass: recovery time below 1000 ms after TTS ends
- Pass: barge-in success above 80% at 1 m normal speech, if barge-in is a goal
- Fail: repeated wake-response-wake loop
- Fail: ASR frequently transcribes the device's own speech as user input

### Report Format

CSV rows should represent one playback or interruption trial. JSON should
include event timelines. Markdown should explicitly state whether the device can
be safely used near its own speaker.

## 14. Benchmark Category: Installation

### Purpose

Compare microphone placement options and determine which installation gives the
best household UX.

### Why It Matters

The same microphone can perform very differently depending on placement. A
technically strong device may fail if hidden behind a display or placed too low.

### Test Procedure

1. Define placement candidates before testing.
2. Keep device, frontend, wake engine, ASR engine, and room constant.
3. For each placement, run a reduced but representative scenario suite:
   wake word, ASR, self voice resistance, and raw audio.
4. Test near-field, across-room, child, and TV conditions.
5. Record physical constraints and visual acceptability.
6. Rank placements by household UX score and failure severity.

### Required Equipment

- Device under test
- Mounts or stands
- Display or target installation object
- Tape measure
- SPL meter
- Wake word and ASR test suite
- Background noise sources

### Metrics Collected

- wake detection rate
- ASR command accuracy
- false positive rate
- self voice trigger rate
- SNR
- clipping ratio
- DOA error, if applicable
- cable practicality score
- visual obstruction score
- installation repeatability score
- total household UX score

### Pass/Fail Criteria

Suggested interpretation:

- Pass: placement meets wake and ASR thresholds for primary household scenarios
- Warning: placement performs well only in quiet conditions
- Warning: placement is acoustically good but mechanically impractical
- Fail: placement causes self-triggering or blocks normal speech pickup

### Report Format

CSV rows should represent one scenario per placement. JSON should include
placement metadata. Markdown should include a ranked recommendation and explain
tradeoffs, not just scores.

## 15. Benchmark Category: Household UX

### Purpose

Measure whether the complete audio input system supports natural household
interaction.

### Why It Matters

This is EchoLab's most important benchmark. A device that scores well on raw
audio may still fail in real life if children cannot wake it, TV causes false
activations, or it hears itself.

### Test Procedure

Run the complete household scenario suite using the final intended installation.
Each scenario should include multiple trials and record both technical metrics
and user-impact labels.

Scenario A: Child Natural Wake

1. Child says the wake phrase naturally from 0.5 m, 1 m, and 2 m.
2. Include imperfect pronunciation and normal household volume.
3. Measure detection, confidence, and latency.
4. Mark whether the child needed to repeat.

Scenario B: Adult Across Room

1. Adult speaks wake phrase and commands from 3 m.
2. Test front and side angles.
3. Include quiet and TV background.
4. Measure wake success, ASR command success, and latency.

Scenario C: TV False Wake

1. Play TV speech and mixed TV content for at least 60 minutes.
2. Include content with wake-word-like phonetics.
3. Count false wakes and ASR activations.

Scenario D: Family Conversation False Wake

1. Record or play non-command household conversation.
2. Include overlapping speech if possible.
3. Count false wakes and accidental command captures.

Scenario E: Device Hears Itself

1. Play normal TTS responses.
2. Include long responses and responses with wake-word-like sounds.
3. Test wake and ASR during and immediately after playback.

Scenario F: Everyday Command Flow

1. Run realistic command sequences, such as weather, timer, reminder, and
   follow-up question.
2. Include adult and child turns.
3. Measure whether the interaction completes without repeated wake attempts.

Scenario G: Placement Comparison

1. Repeat a reduced UX scenario suite for each candidate placement.
2. Rank placements by total task success and failure severity.

### Required Equipment

- Final candidate device and frontend
- Wake word engine
- ASR engine
- TTS or playback speaker
- Display or installation target
- SPL meter
- Household background recordings or live sources
- Adult participant
- Child participant or approved child voice recording
- Scenario script

### Metrics Collected

- child wake success rate
- child repeat rate
- adult across-room wake success rate
- adult across-room ASR success rate
- TV false wakes_per_hour
- conversation false wakes_per_hour
- self-trigger count
- ASR contamination rate
- command completion rate
- total interaction latency_ms
- user repeat count
- recovery time after failure_ms
- household UX score
- failure severity label

Failure severity labels:

- S0: no user-visible issue
- S1: minor delay
- S2: user repeats once
- S3: user repeats multiple times or command fails
- S4: false wake captures unrelated household audio
- S5: self-trigger loop or persistent malfunction

### Pass/Fail Criteria

Suggested GeePi household target:

- Pass: child natural wake success above 85% at 1 m
- Pass: adult across-room command success above 80% at 3 m quiet
- Pass: TV false wakes below 0.1 per hour
- Pass: family conversation false wakes below 0.1 per hour
- Pass: zero S5 failures
- Pass: command completion above 85% for everyday command flow
- Warning: any S4 failure
- Fail: any repeatable self-trigger loop
- Fail: placement prevents reliable child or across-room use

### Report Format

CSV rows should represent one household interaction trial or one false wake
observation window. JSON should include event timelines and scenario metadata.
Markdown should lead with the household answer:

- Can a child wake it naturally?
- Can an adult talk across the room?
- Does the TV trigger it?
- Does family conversation trigger it?
- Does it hear itself?
- Which placement should be used?

## 16. Recommended Benchmark Tiers

### Tier 1: Smoke Test

Purpose: quickly detect obvious failures.

- Device capability
- 1 minute raw capture
- 10 wake trials at 1 m quiet
- 10 ASR trials at 1 m quiet
- 5 TTS self-voice trials

### Tier 2: Standard Comparison

Purpose: compare devices and placements.

- Full device capability
- Raw audio across quiet, TV, and kitchen noise
- Wake word matrix across distance and angle
- ASR matrix across adult, child, quiet, TV, and music
- DOA, if available
- Self voice resistance
- Installation comparison

### Tier 3: Household Qualification

Purpose: approve a device and placement for real household use.

- Full standard comparison
- 60 minute TV false wake test
- 60 minute family conversation false wake test
- Child natural wake
- Adult across-room command flow
- TTS recovery and barge-in
- Final household UX score

## 17. Comparison Rules

When comparing devices:

1. Use the same room, placement class, phrase set, and background level.
2. Keep wake and ASR engines constant unless the frontend includes them.
3. Report onboard DSP settings explicitly.
4. Do not compare DOA scores for devices without DOA.
5. Do not hide failed trials.
6. Separate playback-based results from live-human results.
7. Report confidence intervals when sample size is large enough.

## 18. Data Retention and Privacy

Household audio may contain sensitive speech. EchoLab should support storing
metrics without retaining raw audio when privacy requires it.

Rules:

- Use synthetic or scripted data when possible.
- Use participant IDs rather than real names.
- Store raw audio only when needed for debugging or reproducibility.
- Mark raw audio artifacts as private by default.
- Do not store secrets, credentials, or tokens in benchmark metadata.
- Do not report speaker identity. Report only test labels and acoustic
  characteristics.

## 19. Minimum Report Summary Template

```text
# EchoLab Benchmark Report

Device:
Frontend:
Room:
Placement:
Run ID:
Date:

## Household UX Answer

- Child natural wake:
- Adult across-room speech:
- TV false wakes:
- Family conversation false wakes:
- Self voice resistance:
- Recommended placement:

## Overall Scores

- Wake reliability:
- Speech recognition usability:
- False activation resistance:
- Self voice resistance:
- Installation practicality:
- DOA usefulness:
- Total household UX score:

## Major Failures

| Scenario | Severity | Description | Reproducible |
| --- | --- | --- | --- |

## Benchmark Results

| Benchmark | Key Metric | Result | Target | Status |
| --- | ---: | ---: | ---: | --- |

## Limitations

## Raw Artifacts
```

## 20. Initial EchoLab Standard Matrix

The initial standard matrix for GeePi-oriented household qualification should
include:

- Devices: ReSpeaker USB Mic Array v2.1 and SunFounder USB Microphone baseline
- Host: Raspberry Pi 5
- Distances: 0.5 m, 1 m, 2 m, 3 m
- Angles: 0, 45, 90, 180 degrees
- Backgrounds: quiet, TV speech, music, kitchen noise, family conversation, TTS
- Speakers: adult and child
- Placements: beside display, behind display, under display, elevated display

This matrix is the recommended long-term baseline for comparing future
hardware. Smaller smoke tests may be used during development, but final
recommendations should be based on the household qualification tier.

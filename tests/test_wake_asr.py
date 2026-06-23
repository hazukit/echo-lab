from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from echolab.benchmark.wake_asr import (
    MicConfig,
    WakeAsrConfig,
    WakeAsrTrial,
    parse_float_list,
    parse_mic,
    run_wake_asr_benchmark,
    summarize_wake_asr,
)


class WakeAsrTest(unittest.TestCase):
    def test_parse_mic_requires_name_and_device(self) -> None:
        mic = parse_mic("SunFounder=plughw:1,0")

        self.assertEqual(mic.name, "SunFounder")
        self.assertEqual(mic.device, "plughw:1,0")

    def test_parse_float_list(self) -> None:
        self.assertEqual(parse_float_list("0.5,1,2"), (0.5, 1.0, 2.0))

    def test_summarize_wake_asr_by_microphone(self) -> None:
        trials = [
            _trial("SunFounder", True, 0.7, "hey geepi", "hey geepi"),
            _trial("SunFounder", False, 0.4, "hey geepi", "hey sleepy"),
            _trial("ReSpeaker", True, 0.9, "hey geepi", "hey geepi"),
            _trial("ReSpeaker", True, 0.8, "hey geepi", "hey geepi"),
        ]

        summary = summarize_wake_asr(trials)

        self.assertEqual(summary["SunFounder"]["wake_detection_rate"], 0.5)
        self.assertEqual(summary["ReSpeaker"]["wake_detection_rate"], 1.0)
        self.assertGreater(summary["ReSpeaker"]["mean_wake_confidence"], summary["SunFounder"]["mean_wake_confidence"])
        self.assertGreater(summary["ReSpeaker"]["mean_asr_score"], summary["SunFounder"]["mean_asr_score"])

    def test_run_wake_asr_benchmark_writes_outputs_without_recording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            config = WakeAsrConfig(
                microphones=(MicConfig(name="SunFounder", device="plughw:1,0"),),
                output_dir=output_dir,
                distances_m=(0.5,),
                angles=("front",),
                speaker_label="adult",
                condition="quiet",
                utterance="Hey GeePi",
                expected_text="Hey GeePi",
                record=False,
                interactive=False,
            )

            trials = run_wake_asr_benchmark(config)

            self.assertEqual(len(trials), 1)
            self.assertTrue((output_dir / "wake_asr_results.json").exists())
            self.assertTrue((output_dir / "wake_asr_results.csv").exists())
            self.assertTrue((output_dir / "wake_asr_report.md").exists())
            payload = json.loads((output_dir / "wake_asr_results.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["benchmark"], "wake_asr")
            self.assertEqual(payload["metadata"]["condition"], "quiet")


def _trial(
    mic_name: str,
    wake_detected: bool,
    confidence: float,
    expected: str,
    actual: str,
) -> WakeAsrTrial:
    return WakeAsrTrial(
        trial_id=f"{mic_name}-1",
        mic_name=mic_name,
        input_device="plughw:1,0",
        placement_name="beside GeePi",
        placement_notes=None,
        distance_m=1.0,
        angle="front",
        speaker_label="adult",
        condition="quiet",
        timestamp_utc="2026-01-01T00:00:00+00:00",
        utterance=expected,
        wav_path="sample.wav",
        wake_configured=True,
        wake_detected=wake_detected,
        wake_confidence=confidence,
        asr_configured=True,
        asr_text=actual,
        asr_score=1.0 if expected == actual else 0.5,
    )

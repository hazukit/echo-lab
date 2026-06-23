from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from echolab.benchmark.placement import PlacementBenchmarkConfig, run_placement_benchmark, summarize_placements
from echolab.benchmark.wake_asr import MicConfig, WakeAsrConfig, WakeAsrTrial


class PlacementTest(unittest.TestCase):
    def test_summarize_placements_ranks_household_usability(self) -> None:
        trials = [
            _trial("beside GeePi", True, 0.9, 1.0, 1000, 2000, -55),
            _trial("beside GeePi", True, 0.8, 1.0, 1000, 2000, -55),
            _trial("under GeePi / raised platform", False, 0.3, 0.5, 500, 1000, -35),
            _trial("under GeePi / raised platform", True, 0.5, 0.5, 500, 1000, -35),
        ]

        summary = summarize_placements(trials, {"beside GeePi": "good", "under GeePi / raised platform": "ok"})

        self.assertGreater(
            summary["beside GeePi"]["household_usability_score"],
            summary["under GeePi / raised platform"]["household_usability_score"],
        )
        self.assertEqual(summary["beside GeePi"]["wake_detection_rate"], 1.0)
        self.assertEqual(summary["under GeePi / raised platform"]["wake_detection_rate"], 0.5)

    def test_run_placement_benchmark_writes_outputs_without_recording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            config = PlacementBenchmarkConfig(
                wake_asr_config=WakeAsrConfig(
                    microphones=(MicConfig(name="ReSpeaker", device="plughw:2,0"),),
                    output_dir=output_dir,
                    placement_names=("beside GeePi", "behind GeePi"),
                    distances_m=(0.5,),
                    angles=("front",),
                    speaker_label="adult",
                    condition="quiet",
                    utterance="Hey GeePi",
                    expected_text="Hey GeePi",
                    record=False,
                    interactive=False,
                ),
                placement_acceptability={"beside GeePi": "good", "behind GeePi": "poor"},
            )

            trials = run_placement_benchmark(config)

            self.assertEqual(len(trials), 2)
            self.assertTrue((output_dir / "placement_results.json").exists())
            self.assertTrue((output_dir / "placement_results.csv").exists())
            self.assertTrue((output_dir / "placement_report.md").exists())
            payload = json.loads((output_dir / "placement_results.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["benchmark"], "placement")
            self.assertEqual(payload["metadata"]["placement_acceptability"]["beside GeePi"], "good")


def _trial(
    placement_name: str,
    wake_detected: bool,
    confidence: float,
    asr_score: float,
    rms: float,
    peak: float,
    noise_floor: float,
) -> WakeAsrTrial:
    return WakeAsrTrial(
        trial_id=f"{placement_name}-1",
        mic_name="ReSpeaker",
        input_device="plughw:2,0",
        placement_name=placement_name,
        placement_notes=None,
        distance_m=1.0,
        angle="front",
        speaker_label="adult",
        condition="quiet",
        timestamp_utc="2026-01-01T00:00:00+00:00",
        utterance="Hey GeePi",
        wav_path="sample.wav",
        scoring_wav_path="sample.wav",
        capture_channels=1,
        extracted_channel=None,
        wake_configured=True,
        wake_detected=wake_detected,
        wake_confidence=confidence,
        audio_rms=rms,
        audio_peak=peak,
        audio_noise_floor_dbfs=noise_floor,
        asr_configured=True,
        asr_text="Hey GeePi",
        asr_score=asr_score,
    )

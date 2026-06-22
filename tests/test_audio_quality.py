from __future__ import annotations

import math
import tempfile
import unittest
import wave
from pathlib import Path

from echolab.analysis import analyze_wav


class AudioQualityTest(unittest.TestCase):
    def test_analyze_wav_reports_expected_pcm_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            wav_path = Path(tmp_dir) / "sample.wav"
            samples = [0, 1000, -1000, 32767, -32768]

            with wave.open(str(wav_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b"".join(sample.to_bytes(2, "little", signed=True) for sample in samples))

            record = analyze_wav(wav_path)
            metrics = {metric.name: metric.value for metric in record.metrics}

            self.assertEqual(record.benchmark, "audio_quality")
            self.assertEqual(record.variables["sample_rate_hz"], 16000)
            self.assertEqual(record.variables["channels"], 1)
            self.assertEqual(metrics["peak"], 32768)
            self.assertEqual(metrics["clipping_ratio"], 0.4)
            self.assertIsInstance(metrics["rms_dbfs"], float)
            self.assertFalse(math.isinf(metrics["rms_dbfs"]))

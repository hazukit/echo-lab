from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path

from echolab.analysis.channels import analyze_channel_wav, write_channel_csv, write_channel_json, write_channel_markdown


class ChannelAnalysisTest(unittest.TestCase):
    def test_analyze_channel_wav_reports_per_channel_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            wav_path = Path(tmp_dir) / "channels.wav"
            frames = []
            for index in range(100):
                frames.append((1000 if index % 2 == 0 else -1000).to_bytes(2, "little", signed=True))
                frames.append((200 if index % 2 == 0 else -200).to_bytes(2, "little", signed=True))

            with wave.open(str(wav_path), "wb") as wav:
                wav.setnchannels(2)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b"".join(frames))

            result = analyze_channel_wav(wav_path, input_device="hw:1,0")

            self.assertEqual(result.channels, 2)
            self.assertEqual(len(result.metrics), 2)
            self.assertGreater(result.metrics[0].rms, result.metrics[1].rms)
            self.assertEqual(result.metrics[0].relative_level_db, 0.0)
            self.assertLess(result.metrics[1].relative_level_db or 0.0, 0.0)

    def test_channel_writers_generate_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            wav_path = tmp_path / "channels.wav"
            with wave.open(str(wav_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes((100).to_bytes(2, "little", signed=True) * 10)

            result = analyze_channel_wav(wav_path)
            write_channel_json(result, tmp_path / "channels.json")
            write_channel_csv(result, tmp_path / "channels.csv")
            write_channel_markdown(result, tmp_path / "channels.md")

            self.assertTrue((tmp_path / "channels.json").exists())
            self.assertTrue((tmp_path / "channels.csv").exists())
            self.assertTrue((tmp_path / "channels.md").exists())

    def test_channel_role_hints_are_level_based_and_cautious(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            wav_path = Path(tmp_dir) / "six_channels.wav"
            frames = []
            amplitudes = (1200, 150, 145, 160, 155, 0)
            for index in range(200):
                sign = 1 if index % 2 == 0 else -1
                for amplitude in amplitudes:
                    frames.append((amplitude * sign).to_bytes(2, "little", signed=True))

            with wave.open(str(wav_path), "wb") as wav:
                wav.setnchannels(6)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b"".join(frames))

            result = analyze_channel_wav(wav_path, input_device="hw:2,0")
            hints = [metric.role_hint for metric in result.metrics]

            self.assertEqual(hints[0], "likely processed/beamformed or mixed output")
            self.assertEqual(hints[1:5], ["likely raw/reference microphone channel"] * 4)
            self.assertEqual(hints[5], "likely inactive/silent")

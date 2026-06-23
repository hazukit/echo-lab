from __future__ import annotations

import sys
import unittest
from pathlib import Path

from echolab.plugins import CommandAsrPlugin, CommandWakeWordPlugin, PluginContext


class PluginTest(unittest.TestCase):
    def test_command_wake_word_plugin_returns_generic_result(self) -> None:
        command = (
            f"{sys.executable} -c "
            "\"import json; print(json.dumps({'detected': True, 'confidence': 0.91, 'latency_ms': 120}))\""
        )
        plugin = CommandWakeWordPlugin(command)

        plugin.initialize()
        result = plugin.run(PluginContext(wav_path=Path("sample.wav"), trial_id="trial-1"))
        plugin.shutdown()

        self.assertEqual(result.plugin_type, "wake_word")
        self.assertTrue(result.data["detected"])
        self.assertEqual(result.data["confidence"], 0.91)
        self.assertIsNone(result.error)

    def test_command_asr_plugin_accepts_plain_text(self) -> None:
        command = f"{sys.executable} -c \"print('hello geepi')\""
        plugin = CommandAsrPlugin(command)

        result = plugin.run(PluginContext(wav_path=Path("sample.wav"), trial_id="trial-1"))

        self.assertEqual(result.plugin_type, "asr")
        self.assertEqual(result.data["text"], "hello geepi")


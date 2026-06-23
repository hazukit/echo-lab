from __future__ import annotations

import argparse
import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from echolab.cli import _prompt_wake_asr_args


class CliTest(unittest.TestCase):
    def test_prompt_wake_asr_args_collects_minimal_interactive_config(self) -> None:
        args = argparse.Namespace(
            mic=None,
            out=Path("reports/wake-asr"),
            distances="0.5,1,2,3",
            angles="front,left,right",
            trials=1,
            speaker_label="unknown",
            condition="quiet",
            utterance="wake word test",
            expected_text=None,
            wake_command=None,
            asr_command=None,
        )
        responses = iter(
            [
                "ReSpeaker mono=plughw:2,0",
                "n",
                "reports/interactive",
                "0.5",
                "front",
                "5",
                "adult",
                "quiet",
                "Hey GeePi",
                "",
                "",
                "",
            ]
        )

        with patch("builtins.input", lambda _: next(responses)), contextlib.redirect_stdout(io.StringIO()):
            parsed = _prompt_wake_asr_args(args)

        self.assertEqual(parsed.mic, ["ReSpeaker mono=plughw:2,0"])
        self.assertEqual(parsed.out, Path("reports/interactive"))
        self.assertEqual(parsed.distances, "0.5")
        self.assertEqual(parsed.angles, "front")
        self.assertEqual(parsed.trials, 5)
        self.assertEqual(parsed.utterance, "Hey GeePi")

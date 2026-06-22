from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from echolab.benchmark import BenchmarkRecord, BenchmarkRun, Metric
from echolab.reporting import write_csv, write_json, write_markdown


class ReportingTest(unittest.TestCase):
    def test_report_exporters_write_structured_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            run = BenchmarkRun(
                name="Example",
                records=(
                    BenchmarkRecord(
                        benchmark="audio_quality",
                        subject="sample.wav",
                        variables={"distance_m": 1.0},
                        metrics=(Metric("rms", 123, "pcm"),),
                    ),
                ),
            )

            write_json(run, tmp_path / "report.json")
            write_csv(run, tmp_path / "report.csv")
            write_markdown(run, tmp_path / "report.md")

            self.assertEqual(json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["name"], "Example")
            self.assertIn("distance_m", (tmp_path / "report.csv").read_text(encoding="utf-8"))
            self.assertIn("# Example", (tmp_path / "report.md").read_text(encoding="utf-8"))

from __future__ import annotations

import argparse
from pathlib import Path

from echolab.analysis import analyze_wav
from echolab.benchmark import BenchmarkRun
from echolab.reporting import write_csv, write_json, write_markdown


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "audio-quality":
        run = BenchmarkRun(
            name="Audio Quality Benchmark",
            records=(analyze_wav(args.wav_path),),
            metadata={"source": "wav"},
        )
        out_base = args.out
        write_csv(run, out_base.with_suffix(".csv"))
        write_json(run, out_base.with_suffix(".json"))
        write_markdown(run, out_base.with_suffix(".md"))
        return 0

    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="echolab")
    subparsers = parser.add_subparsers(dest="command")

    audio_quality = subparsers.add_parser("audio-quality", help="Analyze a PCM WAV file.")
    audio_quality.add_argument("wav_path", type=Path)
    audio_quality.add_argument("--out", type=Path, required=True, help="Output path without extension.")

    return parser


if __name__ == "__main__":
    raise SystemExit(main())


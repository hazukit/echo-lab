from __future__ import annotations

import argparse
from pathlib import Path

from echolab.analysis import analyze_wav
from echolab.benchmark import BenchmarkRun
from echolab.benchmark.placement import PlacementBenchmarkConfig, parse_key_value, run_placement_benchmark
from echolab.benchmark.wake_asr import (
    WakeAsrConfig,
    parse_float_list,
    parse_mic,
    parse_str_list,
    run_wake_asr_benchmark,
)
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

    if args.command == "benchmark" and args.benchmark_command == "wake-asr":
        config = WakeAsrConfig(
            microphones=tuple(parse_mic(value) for value in args.mic),
            output_dir=args.out,
            distances_m=parse_float_list(args.distances),
            angles=parse_str_list(args.angles),
            speaker_label=args.speaker_label,
            condition=args.condition,
            utterance=args.utterance,
            expected_text=args.expected_text,
            duration_s=args.duration,
            sample_rate_hz=args.sample_rate,
            channels=args.channels,
            trials_per_case=args.trials,
            record=not args.no_record,
            interactive=not args.non_interactive,
            record_command=args.record_command,
            wake_command=args.wake_command,
            asr_command=args.asr_command,
        )
        run_wake_asr_benchmark(config)
        return 0

    if args.command == "benchmark" and args.benchmark_command == "placement":
        acceptability = dict(parse_key_value(value) for value in args.placement_acceptability or ())
        config = PlacementBenchmarkConfig(
            wake_asr_config=WakeAsrConfig(
                microphones=tuple(parse_mic(value) for value in args.mic),
                output_dir=args.out,
                placement_names=parse_str_list(args.placements),
                placement_notes=args.placement_notes,
                distances_m=parse_float_list(args.distances),
                angles=parse_str_list(args.angles),
                speaker_label=args.speaker_label,
                condition=args.condition,
                utterance=args.utterance,
                expected_text=args.expected_text,
                duration_s=args.duration,
                sample_rate_hz=args.sample_rate,
                channels=args.channels,
                trials_per_case=args.trials,
                record=not args.no_record,
                interactive=not args.non_interactive,
                record_command=args.record_command,
                wake_command=args.wake_command,
                asr_command=args.asr_command,
            ),
            placement_acceptability=acceptability,
        )
        run_placement_benchmark(config)
        return 0

    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="echolab")
    subparsers = parser.add_subparsers(dest="command")

    audio_quality = subparsers.add_parser("audio-quality", help="Analyze a PCM WAV file.")
    audio_quality.add_argument("wav_path", type=Path)
    audio_quality.add_argument("--out", type=Path, required=True, help="Output path without extension.")

    benchmark = subparsers.add_parser("benchmark", help="Run an end-to-end benchmark scenario.")
    benchmark_subparsers = benchmark.add_subparsers(dest="benchmark_command")

    wake_asr = benchmark_subparsers.add_parser(
        "wake-asr",
        help="Compare microphones with a wake word and ASR household baseline.",
    )
    wake_asr.add_argument(
        "--mic",
        action="append",
        required=True,
        help="Microphone in NAME=ALSA_DEVICE format. Repeat for each mic.",
    )
    wake_asr.add_argument("--out", type=Path, default=Path("reports/wake-asr"), help="Output directory.")
    wake_asr.add_argument("--distances", default="0.5,1,2,3", help="Comma-separated distances in meters.")
    wake_asr.add_argument("--angles", default="front,left,right", help="Comma-separated angle labels.")
    wake_asr.add_argument("--speaker-label", default="unknown", help="Speaker label such as adult or child.")
    wake_asr.add_argument("--condition", default="quiet", help="Room condition label.")
    wake_asr.add_argument("--utterance", default="wake word test", help="Prompt shown for each trial.")
    wake_asr.add_argument("--expected-text", help="Expected ASR text for simple word-level scoring.")
    wake_asr.add_argument("--duration", type=float, default=3.0, help="Recording duration per trial.")
    wake_asr.add_argument("--sample-rate", type=int, default=16000, help="Capture sample rate.")
    wake_asr.add_argument("--channels", type=int, default=1, help="Capture channels.")
    wake_asr.add_argument("--trials", type=int, default=1, help="Trials per distance and angle.")
    wake_asr.add_argument(
        "--record-command",
        help="Optional recorder command template. Supports {wav_path}, {device}, {duration_s}, {sample_rate_hz}, {channels}.",
    )
    wake_asr.add_argument(
        "--wake-command",
        help="Optional wake scorer command template. Supports {wav_path}; should print JSON with detected/confidence/latency_ms.",
    )
    wake_asr.add_argument(
        "--asr-command",
        help="Optional ASR command template. Supports {wav_path}; should print JSON with text/latency_ms or plain text.",
    )
    wake_asr.add_argument("--no-record", action="store_true", help="Skip recording and only write/scoring planned trials.")
    wake_asr.add_argument("--non-interactive", action="store_true", help="Do not prompt before each recording.")

    placement = benchmark_subparsers.add_parser(
        "placement",
        help="Compare GeePi microphone placement options with wake word and ASR trials.",
    )
    placement.add_argument(
        "--mic",
        action="append",
        required=True,
        help="Microphone in NAME=ALSA_DEVICE format. Repeat for each mic.",
    )
    placement.add_argument(
        "--placements",
        default="beside GeePi,behind GeePi,under GeePi / raised platform,stand base area",
        help="Comma-separated placement labels.",
    )
    placement.add_argument(
        "--placement-notes",
        help="Optional notes applied to this placement run, such as cable routing or display obstruction.",
    )
    placement.add_argument(
        "--placement-acceptability",
        action="append",
        help="Physical design rating in NAME=VALUE format. Values can be good, ok, poor, blocking. Repeat as needed.",
    )
    placement.add_argument("--out", type=Path, default=Path("reports/placement"), help="Output directory.")
    placement.add_argument("--distances", default="0.5,1,2,3", help="Comma-separated distances in meters.")
    placement.add_argument("--angles", default="front,left,right", help="Comma-separated angle labels.")
    placement.add_argument("--speaker-label", default="unknown", help="Speaker label such as adult or child.")
    placement.add_argument("--condition", default="quiet", help="Room condition label.")
    placement.add_argument("--utterance", default="wake word test", help="Prompt shown for each trial.")
    placement.add_argument("--expected-text", help="Expected ASR text for simple word-level scoring.")
    placement.add_argument("--duration", type=float, default=3.0, help="Recording duration per trial.")
    placement.add_argument("--sample-rate", type=int, default=16000, help="Capture sample rate.")
    placement.add_argument("--channels", type=int, default=1, help="Capture channels.")
    placement.add_argument("--trials", type=int, default=1, help="Trials per placement, distance, and angle.")
    placement.add_argument(
        "--record-command",
        help="Optional recorder command template. Supports {wav_path}, {device}, {duration_s}, {sample_rate_hz}, {channels}.",
    )
    placement.add_argument(
        "--wake-command",
        help="Optional wake scorer command template. Supports {wav_path}; should print JSON with detected/confidence/latency_ms.",
    )
    placement.add_argument(
        "--asr-command",
        help="Optional ASR command template. Supports {wav_path}; should print JSON with text/latency_ms or plain text.",
    )
    placement.add_argument("--no-record", action="store_true", help="Skip recording and only write/scoring planned trials.")
    placement.add_argument("--non-interactive", action="store_true", help="Do not prompt before each recording.")

    return parser


if __name__ == "__main__":
    raise SystemExit(main())

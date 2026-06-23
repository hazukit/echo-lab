from __future__ import annotations

import argparse
import json
from pathlib import Path

from echolab.analysis import analyze_wav, record_and_analyze_channels
from echolab.benchmark import BenchmarkRun
from echolab.benchmark.placement import PlacementBenchmarkConfig, parse_key_value, run_placement_benchmark
from echolab.benchmark.wake_asr import (
    WakeAsrConfig,
    parse_float_list,
    parse_mic,
    parse_str_list,
    run_wake_asr_benchmark,
)
from echolab.devices.alsa import (
    inspect_alsa_capture_devices,
    inspect_payload,
    render_inspect_markdown,
    write_inspect_csv,
    write_inspect_json,
    write_inspect_markdown,
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

    if args.command == "inspect":
        devices = inspect_alsa_capture_devices()
        if args.out:
            write_inspect_json(devices, args.out / "inspect_devices.json")
            write_inspect_csv(devices, args.out / "inspect_devices.csv")
            write_inspect_markdown(devices, args.out / "inspect_devices.md")
        if args.json:
            print(json.dumps(inspect_payload(devices), indent=2, sort_keys=True))
        else:
            print(render_inspect_markdown(devices), end="")
        return 0

    if args.command == "analyze" and args.analyze_command == "channels":
        record_and_analyze_channels(
            input_device=args.device,
            output_dir=args.out,
            duration_s=args.duration,
            sample_rate_hz=args.sample_rate,
            channels=args.channels,
            sample_format=args.format,
            record_command=args.record_command,
        )
        return 0

    if args.command == "benchmark" and args.benchmark_command == "wake-asr":
        if args.interactive_mode:
            args = _prompt_wake_asr_args(args)
        if not args.mic:
            parser.error("echolab benchmark wake-asr requires --mic unless --interactive is used")
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
            interactive=args.interactive_mode or not args.non_interactive,
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

    inspect = subparsers.add_parser("inspect", help="Inspect available capture devices.")
    output_format = inspect.add_mutually_exclusive_group()
    output_format.add_argument("--json", action="store_true", help="Print machine-readable JSON to stdout.")
    output_format.add_argument("--markdown", action="store_true", help="Print human-readable Markdown to stdout.")
    inspect.add_argument("--out", type=Path, help="Optional output directory for JSON, CSV, and Markdown files.")

    analyze = subparsers.add_parser("analyze", help="Analyze captured audio artifacts or devices.")
    analyze_subparsers = analyze.add_subparsers(dest="analyze_command")
    channels = analyze_subparsers.add_parser("channels", help="Record and analyze per-channel capture behavior.")
    channels.add_argument("--device", default="default", help="ALSA capture device such as hw:2,0 or plughw:2,0.")
    channels.add_argument("--out", type=Path, default=Path("reports/channels"), help="Output directory.")
    channels.add_argument("--duration", type=float, default=3.0, help="Recording duration in seconds.")
    channels.add_argument("--sample-rate", type=int, default=16000, help="Capture sample rate.")
    channels.add_argument("--channels", type=int, default=1, help="Channel count to capture.")
    channels.add_argument("--format", default="S16_LE", help="ALSA sample format.")
    channels.add_argument(
        "--record-command",
        help="Optional recorder command template. Supports {wav_path}, {device}, {duration_s}, {sample_rate_hz}, {channels}, {format}.",
    )

    benchmark = subparsers.add_parser("benchmark", help="Run an end-to-end benchmark scenario.")
    benchmark_subparsers = benchmark.add_subparsers(dest="benchmark_command")

    wake_asr = benchmark_subparsers.add_parser(
        "wake-asr",
        help="Compare microphones with a wake word and ASR household baseline.",
    )
    wake_asr.add_argument(
        "--mic",
        action="append",
        help="Microphone in NAME=ALSA_DEVICE format. Repeat for each mic.",
    )
    wake_asr.add_argument("--out", type=Path, default=Path("reports/wake-asr"), help="Output directory.")
    wake_asr.add_argument("--distances", default="0.5,1,2,3", help="Comma-separated distances in meters.")
    wake_asr.add_argument("--angles", default="front,left,right", help="Comma-separated angle labels.")
    wake_asr.add_argument("--speaker-label", default="unknown", help="Speaker label such as adult or child.")
    wake_asr.add_argument("--condition", default="quiet", help="Room condition label.")
    wake_asr.add_argument("--utterance", "--phrase", default="wake word test", help="Prompt shown for each trial.")
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
    wake_asr.add_argument("--interactive", dest="interactive_mode", action="store_true", help="Prompt for setup and step through each trial.")
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
    placement.add_argument("--utterance", "--phrase", default="wake word test", help="Prompt shown for each trial.")
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


def _prompt_wake_asr_args(args: argparse.Namespace) -> argparse.Namespace:
    print("EchoLab interactive Wake + ASR benchmark")
    print("Press Enter to accept defaults shown in brackets.")
    print()

    args.mic = args.mic or _prompt_mics()
    args.out = Path(_prompt_text("Output directory", str(args.out)))
    args.distances = _prompt_text("Distances, comma-separated meters", args.distances)
    args.angles = _prompt_text("Angles, comma-separated", args.angles)
    args.trials = int(_prompt_text("Trials per condition", str(args.trials)))
    args.speaker_label = _prompt_text("Speaker label", args.speaker_label)
    args.condition = _prompt_text("Condition", args.condition)
    args.utterance = _prompt_text("Utterance prompt", args.utterance)
    expected = _prompt_text("Expected ASR text, optional", args.expected_text or "")
    args.expected_text = expected or None
    wake_command = _prompt_text("Wake scorer command, optional", args.wake_command or "")
    args.wake_command = wake_command or None
    asr_command = _prompt_text("ASR command, optional", args.asr_command or "")
    args.asr_command = asr_command or None
    return args


def _prompt_mics() -> list[str]:
    mics: list[str] = []
    while True:
        default = "ReSpeaker mono=plughw:2,0" if not mics else ""
        value = _prompt_text("Mic NAME=DEVICE, blank when done", default)
        if not value:
            if mics:
                return mics
            print("At least one microphone is required.")
            continue
        mics.append(value)
        another = _prompt_text("Add another mic? y/N", "n").lower()
        if another not in {"y", "yes"}:
            return mics


def _prompt_text(label: str, default: str) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value if value else default


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import csv
import json
import math
import shlex
import subprocess
import wave
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from echolab.analysis.audio_quality import analyze_wav


DEFAULT_DISTANCES_M = (0.5, 1.0, 2.0, 3.0)
DEFAULT_ANGLES = ("front", "left", "right")
DEFAULT_PLACEMENTS = ("default",)


@dataclass(frozen=True, slots=True)
class MicConfig:
    name: str
    device: str


@dataclass(frozen=True, slots=True)
class WakeAsrConfig:
    microphones: tuple[MicConfig, ...]
    output_dir: Path
    placement_names: tuple[str, ...] = DEFAULT_PLACEMENTS
    placement_notes: str | None = None
    distances_m: tuple[float, ...] = DEFAULT_DISTANCES_M
    angles: tuple[str, ...] = DEFAULT_ANGLES
    speaker_label: str = "unknown"
    condition: str = "quiet"
    utterance: str = "wake word test"
    expected_text: str | None = None
    duration_s: float = 3.0
    sample_rate_hz: int = 16000
    channels: int = 1
    trials_per_case: int = 1
    record: bool = True
    interactive: bool = True
    record_command: str | None = None
    wake_command: str | None = None
    asr_command: str | None = None


@dataclass(frozen=True, slots=True)
class WakeAsrTrial:
    trial_id: str
    mic_name: str
    input_device: str
    placement_name: str
    placement_notes: str | None
    distance_m: float
    angle: str
    speaker_label: str
    condition: str
    timestamp_utc: str
    utterance: str
    wav_path: str
    wake_configured: bool
    wake_detected: bool | None = None
    wake_confidence: float | None = None
    wake_latency_ms: float | None = None
    wake_raw: dict[str, Any] = field(default_factory=dict)
    audio_rms: float | None = None
    audio_peak: float | None = None
    audio_noise_floor_dbfs: float | None = None
    asr_configured: bool = False
    asr_text: str | None = None
    asr_latency_ms: float | None = None
    asr_score: float | None = None
    asr_raw: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trial_id": self.trial_id,
            "mic_name": self.mic_name,
            "input_device": self.input_device,
            "placement_name": self.placement_name,
            "placement_notes": self.placement_notes,
            "distance_m": self.distance_m,
            "angle": self.angle,
            "speaker_label": self.speaker_label,
            "condition": self.condition,
            "timestamp_utc": self.timestamp_utc,
            "utterance": self.utterance,
            "wav_path": self.wav_path,
            "wake_configured": self.wake_configured,
            "wake_detected": self.wake_detected,
            "wake_confidence": self.wake_confidence,
            "wake_latency_ms": self.wake_latency_ms,
            "wake_raw": self.wake_raw,
            "audio_rms": self.audio_rms,
            "audio_peak": self.audio_peak,
            "audio_noise_floor_dbfs": self.audio_noise_floor_dbfs,
            "asr_configured": self.asr_configured,
            "asr_text": self.asr_text,
            "asr_latency_ms": self.asr_latency_ms,
            "asr_score": self.asr_score,
            "asr_raw": self.asr_raw,
            "error": self.error,
        }


def run_wake_asr_benchmark(config: WakeAsrConfig) -> list[WakeAsrTrial]:
    trials = collect_wake_asr_trials(config)
    write_wake_asr_json(trials, config, config.output_dir / "wake_asr_results.json")
    write_wake_asr_csv(trials, config.output_dir / "wake_asr_results.csv")
    write_wake_asr_markdown(trials, config, config.output_dir / "wake_asr_report.md")
    return trials


def collect_wake_asr_trials(config: WakeAsrConfig) -> list[WakeAsrTrial]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = config.output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    trials: list[WakeAsrTrial] = []
    for placement_name in config.placement_names:
        for mic in config.microphones:
            for distance_m in config.distances_m:
                for angle in config.angles:
                    for trial_index in range(1, config.trials_per_case + 1):
                        trial_id = _trial_id(placement_name, mic.name, distance_m, angle, trial_index)
                        wav_path = audio_dir / f"{trial_id}.wav"
                        if config.interactive and config.record:
                            _prompt_for_trial(placement_name, mic, distance_m, angle, config, trial_index)
                        error = _record_trial(config, mic, wav_path) if config.record else None
                        trial = _score_trial(config, placement_name, mic, distance_m, angle, trial_index, wav_path, error)
                        trials.append(trial)
    return trials


def write_wake_asr_json(trials: list[WakeAsrTrial], config: WakeAsrConfig, path: Path) -> None:
    payload = {
        "benchmark": "wake_asr",
        "created_at": datetime.now(UTC).isoformat(),
        "metadata": {
            "microphones": [{"name": mic.name, "device": mic.device} for mic in config.microphones],
            "placement_names": list(config.placement_names),
            "placement_notes": config.placement_notes,
            "distances_m": list(config.distances_m),
            "angles": list(config.angles),
            "speaker_label": config.speaker_label,
            "condition": config.condition,
            "utterance": config.utterance,
            "expected_text": config.expected_text,
            "duration_s": config.duration_s,
            "sample_rate_hz": config.sample_rate_hz,
            "channels": config.channels,
            "trials_per_case": config.trials_per_case,
            "wake_configured": config.wake_command is not None,
            "asr_configured": config.asr_command is not None,
        },
        "trials": [trial.to_dict() for trial in trials],
        "summary": summarize_wake_asr(trials),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_wake_asr_csv(trials: list[WakeAsrTrial], path: Path) -> None:
    fieldnames = [
        "trial_id",
        "mic_name",
        "input_device",
        "placement_name",
        "placement_notes",
        "distance_m",
        "angle",
        "speaker_label",
        "condition",
        "timestamp_utc",
        "utterance",
        "wav_path",
        "wake_configured",
        "wake_detected",
        "wake_confidence",
        "wake_latency_ms",
        "audio_rms",
        "audio_peak",
        "audio_noise_floor_dbfs",
        "asr_configured",
        "asr_text",
        "asr_latency_ms",
        "asr_score",
        "error",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for trial in trials:
            row = {key: trial.to_dict()[key] for key in fieldnames}
            writer.writerow(row)


def write_wake_asr_markdown(trials: list[WakeAsrTrial], config: WakeAsrConfig, path: Path) -> None:
    summary = summarize_wake_asr(trials)
    best_wake = _best_device(summary, "wake_detection_rate")
    best_confidence = _best_device(summary, "mean_wake_confidence")
    best_asr = _best_device(summary, "mean_asr_score")
    dropoff = _distance_dropoff(trials)

    lines = [
        "# Wake Word + ASR Baseline Comparison",
        "",
        "## Household Answers",
        "",
        f"- Which mic detects wake word more reliably? {_answer(best_wake)}",
        f"- Which mic has higher wake confidence? {_answer(best_confidence)}",
        f"- Which mic gives better ASR text? {_answer(best_asr)}",
        f"- At what distance does performance drop? {dropoff}",
        f"- Is ReSpeaker clearly better than SunFounder? {_respeaker_answer(summary)}",
        "",
        "## Configuration",
        "",
        f"- Condition: `{config.condition}`",
        f"- Speaker label: `{config.speaker_label}`",
        f"- Utterance: `{config.utterance}`",
        f"- Expected ASR text: `{config.expected_text or ''}`",
        f"- Distances: `{', '.join(str(distance) for distance in config.distances_m)} m`",
        f"- Angles: `{', '.join(config.angles)}`",
        f"- Trials per case: `{config.trials_per_case}`",
        f"- Wake scoring configured: `{config.wake_command is not None}`",
        f"- ASR configured: `{config.asr_command is not None}`",
        "",
        "## Device Summary",
        "",
        "| Mic | Trials | Wake Detection | Mean Wake Confidence | Mean ASR Score | Mean ASR Latency ms | Errors |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mic_name, values in sorted(summary.items()):
        lines.append(
            "| "
            f"{mic_name} | "
            f"{values['trial_count']} | "
            f"{_pct(values.get('wake_detection_rate'))} | "
            f"{_num(values.get('mean_wake_confidence'))} | "
            f"{_pct(values.get('mean_asr_score'))} | "
            f"{_num(values.get('mean_asr_latency_ms'))} | "
            f"{values['error_count']} |"
        )

    lines.extend(
        [
            "",
            "## Distance Summary",
            "",
            "| Mic | Distance m | Trials | Wake Detection | Mean Wake Confidence | Mean ASR Score |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in _summarize_by_distance(trials):
        lines.append(
            "| "
            f"{row['mic_name']} | "
            f"{row['distance_m']} | "
            f"{row['trial_count']} | "
            f"{_pct(row.get('wake_detection_rate'))} | "
            f"{_num(row.get('mean_wake_confidence'))} | "
            f"{_pct(row.get('mean_asr_score'))} |"
        )

    lines.extend(
        [
            "",
            "## Raw Result Files",
            "",
            "- `wake_asr_results.json`",
            "- `wake_asr_results.csv`",
            "- `audio/*.wav`",
            "",
            "## Notes",
            "",
            "Wake and ASR scoring are optional. If no scorer command is configured, this report still records the audio and metadata but cannot judge recognition quality.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarize_wake_asr(trials: list[WakeAsrTrial]) -> dict[str, dict[str, int | float | None]]:
    summary: dict[str, dict[str, int | float | None]] = {}
    for mic_name in sorted({trial.mic_name for trial in trials}):
        mic_trials = [trial for trial in trials if trial.mic_name == mic_name]
        wake_trials = [trial for trial in mic_trials if trial.wake_configured]
        detected = [trial for trial in wake_trials if trial.wake_detected is True]
        confidences = [trial.wake_confidence for trial in mic_trials if trial.wake_confidence is not None]
        asr_scores = [trial.asr_score for trial in mic_trials if trial.asr_score is not None]
        asr_latencies = [trial.asr_latency_ms for trial in mic_trials if trial.asr_latency_ms is not None]
        summary[mic_name] = {
            "trial_count": len(mic_trials),
            "wake_detection_rate": len(detected) / len(wake_trials) if wake_trials else None,
            "mean_wake_confidence": mean(confidences) if confidences else None,
            "mean_asr_score": mean(asr_scores) if asr_scores else None,
            "mean_asr_latency_ms": mean(asr_latencies) if asr_latencies else None,
            "error_count": sum(1 for trial in mic_trials if trial.error),
        }
    return summary


def parse_mic(value: str) -> MicConfig:
    if "=" not in value:
        raise ValueError("Microphone must use NAME=DEVICE format, for example SunFounder=plughw:1,0")
    name, device = value.split("=", 1)
    name = name.strip()
    device = device.strip()
    if not name or not device:
        raise ValueError("Microphone name and device must both be non-empty")
    return MicConfig(name=name, device=device)


def parse_float_list(value: str) -> tuple[float, ...]:
    return tuple(float(item.strip()) for item in value.split(",") if item.strip())


def parse_str_list(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _record_trial(config: WakeAsrConfig, mic: MicConfig, wav_path: Path) -> str | None:
    command = _record_command(config, mic, wav_path)
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        return f"record command not found: {exc.filename}"
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        return f"record command failed with exit {exc.returncode}: {stderr}"
    return None


def _record_command(config: WakeAsrConfig, mic: MicConfig, wav_path: Path) -> list[str]:
    if config.record_command:
        return _format_command(
            config.record_command,
            {
                "wav_path": str(wav_path),
                "device": mic.device,
                "duration_s": str(config.duration_s),
                "sample_rate_hz": str(config.sample_rate_hz),
                "channels": str(config.channels),
            },
        )
    return [
        "arecord",
        "-D",
        mic.device,
        "-f",
        "S16_LE",
        "-r",
        str(config.sample_rate_hz),
        "-c",
        str(config.channels),
        "-d",
        str(max(1, math.ceil(config.duration_s))),
        str(wav_path),
    ]


def _score_trial(
    config: WakeAsrConfig,
    placement_name: str,
    mic: MicConfig,
    distance_m: float,
    angle: str,
    trial_index: int,
    wav_path: Path,
    error: str | None,
) -> WakeAsrTrial:
    trial_id = _trial_id(placement_name, mic.name, distance_m, angle, trial_index)
    timestamp = datetime.now(UTC).isoformat()
    wake_raw: dict[str, Any] = {}
    asr_raw: dict[str, Any] = {}
    audio_metrics = _audio_metrics(wav_path) if error is None and wav_path.exists() else {}
    wake_detected: bool | None = None
    wake_confidence: float | None = None
    wake_latency_ms: float | None = None
    asr_text: str | None = None
    asr_latency_ms: float | None = None

    if error is None and config.wake_command:
        wake_raw = _run_json_or_text_command(config.wake_command, wav_path)
        wake_detected = _optional_bool(wake_raw.get("detected"))
        wake_confidence = _optional_float(wake_raw.get("confidence"))
        wake_latency_ms = _optional_float(wake_raw.get("latency_ms"))
        if "error" in wake_raw:
            error = str(wake_raw["error"])

    if error is None and config.asr_command:
        asr_raw = _run_json_or_text_command(config.asr_command, wav_path)
        asr_text = _optional_str(asr_raw.get("text"))
        asr_latency_ms = _optional_float(asr_raw.get("latency_ms"))
        if "error" in asr_raw:
            error = str(asr_raw["error"])

    return WakeAsrTrial(
        trial_id=trial_id,
        mic_name=mic.name,
        input_device=mic.device,
        placement_name=placement_name,
        placement_notes=config.placement_notes,
        distance_m=distance_m,
        angle=angle,
        speaker_label=config.speaker_label,
        condition=config.condition,
        timestamp_utc=timestamp,
        utterance=config.utterance,
        wav_path=str(wav_path),
        wake_configured=config.wake_command is not None,
        wake_detected=wake_detected,
        wake_confidence=wake_confidence,
        wake_latency_ms=wake_latency_ms,
        wake_raw=wake_raw,
        audio_rms=_optional_float(audio_metrics.get("rms")),
        audio_peak=_optional_float(audio_metrics.get("peak")),
        audio_noise_floor_dbfs=_optional_float(audio_metrics.get("noise_floor_dbfs")),
        asr_configured=config.asr_command is not None,
        asr_text=asr_text,
        asr_latency_ms=asr_latency_ms,
        asr_score=_text_similarity(config.expected_text, asr_text),
        asr_raw=asr_raw,
        error=error,
    )


def _audio_metrics(wav_path: Path) -> dict[str, Any]:
    try:
        record = analyze_wav(wav_path)
    except (OSError, EOFError, wave.Error, ValueError):
        return {}
    return {metric.name: metric.value for metric in record.metrics}


def _run_json_or_text_command(command_template: str, wav_path: Path) -> dict[str, Any]:
    command = _format_command(command_template, {"wav_path": str(wav_path)})
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        return {"error": f"command not found: {exc.filename}"}
    except subprocess.CalledProcessError as exc:
        return {"error": f"command failed with exit {exc.returncode}: {exc.stderr.strip()}"}

    stdout = completed.stdout.strip()
    if not stdout:
        return {}
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return {"text": stdout}
    if isinstance(parsed, dict):
        return parsed
    return {"value": parsed}


def _format_command(template: str, values: dict[str, str]) -> list[str]:
    return [part.format(**values) for part in shlex.split(template)]


def _trial_id(placement_name: str, mic_name: str, distance_m: float, angle: str, trial_index: int) -> str:
    safe_placement = "".join(char.lower() if char.isalnum() else "-" for char in placement_name).strip("-")
    safe_name = "".join(char.lower() if char.isalnum() else "-" for char in mic_name).strip("-")
    distance = str(distance_m).replace(".", "p")
    return f"{safe_placement}_{safe_name}_{distance}m_{angle}_{trial_index:02d}"


def _prompt_for_trial(
    placement_name: str,
    mic: MicConfig,
    distance_m: float,
    angle: str,
    config: WakeAsrConfig,
    trial_index: int,
) -> None:
    print()
    print(f"Placement: {placement_name}")
    print(f"Mic: {mic.name} ({mic.device})")
    print(f"Distance: {distance_m} m / Angle: {angle} / Trial: {trial_index}")
    print(f"Speaker: {config.speaker_label} / Condition: {config.condition}")
    print(f"Utterance: {config.utterance}")
    input("Press Enter, then speak after recording starts...")


def _text_similarity(expected: str | None, actual: str | None) -> float | None:
    if expected is None or actual is None:
        return None
    expected_tokens = _normalize_text(expected).split()
    actual_tokens = _normalize_text(actual).split()
    if not expected_tokens and not actual_tokens:
        return 1.0
    if not expected_tokens or not actual_tokens:
        return 0.0
    distance = _levenshtein(expected_tokens, actual_tokens)
    return max(0.0, 1.0 - distance / len(expected_tokens))


def _normalize_text(value: str) -> str:
    return " ".join("".join(char.lower() if char.isalnum() else " " for char in value).split())


def _levenshtein(left: list[str], right: list[str]) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_value in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_value in enumerate(right, start=1):
            insert_cost = current[right_index - 1] + 1
            delete_cost = previous[right_index] + 1
            replace_cost = previous[right_index - 1] + (left_value != right_value)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in {"1", "true", "yes", "detected"}:
            return True
        if lowered in {"0", "false", "no", "missed"}:
            return False
    if isinstance(value, int | float):
        return bool(value)
    return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _best_device(summary: dict[str, dict[str, int | float | None]], metric: str) -> tuple[str, float] | None:
    candidates = [
        (mic_name, value)
        for mic_name, values in summary.items()
        if isinstance((value := values.get(metric)), int | float)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[1])


def _answer(best: tuple[str, float] | None) -> str:
    if best is None:
        return "Not scored; configure the relevant scorer command."
    return f"{best[0]} currently leads ({_pct(best[1])})."


def _respeaker_answer(summary: dict[str, dict[str, int | float | None]]) -> str:
    respeaker = _find_summary(summary, "respeaker")
    sunfounder = _find_summary(summary, "sunfounder")
    if not respeaker or not sunfounder:
        return "Not enough named device data to compare ReSpeaker and SunFounder directly."
    score_keys = ("wake_detection_rate", "mean_wake_confidence", "mean_asr_score")
    respeaker_wins = 0
    comparable = 0
    for key in score_keys:
        r_value = respeaker.get(key)
        s_value = sunfounder.get(key)
        if isinstance(r_value, int | float) and isinstance(s_value, int | float):
            comparable += 1
            if r_value > s_value:
                respeaker_wins += 1
    if comparable == 0:
        return "Not scored yet; configure wake and ASR scoring."
    if respeaker_wins == comparable:
        return "Yes, ReSpeaker leads all scored comparison metrics in this run."
    if respeaker_wins == 0:
        return "No, ReSpeaker does not lead the scored comparison metrics in this run."
    return "Mixed; ReSpeaker leads some scored metrics but not all."


def _find_summary(
    summary: dict[str, dict[str, int | float | None]], needle: str
) -> dict[str, int | float | None] | None:
    for mic_name, values in summary.items():
        if needle in mic_name.lower():
            return values
    return None


def _distance_dropoff(trials: list[WakeAsrTrial]) -> str:
    rows = _summarize_by_distance(trials)
    scored = [
        row
        for row in rows
        if isinstance(row.get("wake_detection_rate"), int | float) or isinstance(row.get("mean_asr_score"), int | float)
    ]
    if not scored:
        return "Not scored; collect wake or ASR results first."
    weak_rows = []
    for row in scored:
        wake_rate = row.get("wake_detection_rate")
        asr_score = row.get("mean_asr_score")
        wake_weak = isinstance(wake_rate, int | float) and wake_rate < 0.8
        asr_weak = isinstance(asr_score, int | float) and asr_score < 0.8
        if wake_weak or asr_weak:
            weak_rows.append(row)
    if not weak_rows:
        return "No clear drop-off within tested distances."
    first = min(weak_rows, key=lambda row: float(row["distance_m"]))
    return f"{first['mic_name']} drops below 80% around {first['distance_m']} m."


def _summarize_by_distance(trials: list[WakeAsrTrial]) -> list[dict[str, int | float | str | None]]:
    rows: list[dict[str, int | float | str | None]] = []
    keys = sorted({(trial.mic_name, trial.distance_m) for trial in trials})
    for mic_name, distance_m in keys:
        selected = [trial for trial in trials if trial.mic_name == mic_name and trial.distance_m == distance_m]
        wake_trials = [trial for trial in selected if trial.wake_configured]
        detected = [trial for trial in wake_trials if trial.wake_detected is True]
        confidences = [trial.wake_confidence for trial in selected if trial.wake_confidence is not None]
        asr_scores = [trial.asr_score for trial in selected if trial.asr_score is not None]
        rows.append(
            {
                "mic_name": mic_name,
                "distance_m": distance_m,
                "trial_count": len(selected),
                "wake_detection_rate": len(detected) / len(wake_trials) if wake_trials else None,
                "mean_wake_confidence": mean(confidences) if confidences else None,
                "mean_asr_score": mean(asr_scores) if asr_scores else None,
            }
        )
    return rows


def _pct(value: int | float | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def _num(value: int | float | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.3f}"

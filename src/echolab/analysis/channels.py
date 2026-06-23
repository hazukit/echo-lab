from __future__ import annotations

import csv
import json
import math
import shlex
import subprocess
import wave
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from typing import Any


@dataclass(frozen=True, slots=True)
class ChannelMetrics:
    channel_index: int
    rms: float
    peak: int
    clipping_count: int
    speech_activity_ratio: float
    relative_level_db: float | None
    role_hint: str = "unknown"

    def to_dict(self) -> dict[str, int | float | str | None]:
        return {
            "channel_index": self.channel_index,
            "rms": self.rms,
            "peak": self.peak,
            "clipping_count": self.clipping_count,
            "speech_activity_ratio": self.speech_activity_ratio,
            "relative_level_db": self.relative_level_db,
            "role_hint": self.role_hint,
        }


@dataclass(frozen=True, slots=True)
class ChannelAnalysisResult:
    wav_path: str
    input_device: str
    sample_rate_hz: int
    channels: int
    sample_width_bytes: int
    duration_s: float
    metrics: tuple[ChannelMetrics, ...]
    record_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "wav_path": self.wav_path,
            "input_device": self.input_device,
            "sample_rate_hz": self.sample_rate_hz,
            "channels": self.channels,
            "sample_width_bytes": self.sample_width_bytes,
            "duration_s": self.duration_s,
            "record_error": self.record_error,
            "metrics": [metric.to_dict() for metric in self.metrics],
        }


def record_and_analyze_channels(
    input_device: str,
    output_dir: Path,
    duration_s: float = 3.0,
    sample_rate_hz: int = 16000,
    channels: int = 6,
    sample_format: str = "S16_LE",
    record_command: str | None = None,
) -> ChannelAnalysisResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    wav_path = output_dir / "channel_capture.wav"
    error = record_multichannel_wav(
        input_device=input_device,
        wav_path=wav_path,
        duration_s=duration_s,
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        sample_format=sample_format,
        record_command=record_command,
    )
    if error is not None:
        result = ChannelAnalysisResult(
            wav_path=str(wav_path),
            input_device=input_device,
            sample_rate_hz=sample_rate_hz,
            channels=channels,
            sample_width_bytes=0,
            duration_s=duration_s,
            metrics=(),
            record_error=error,
        )
    else:
        result = analyze_channel_wav(wav_path, input_device=input_device)
    write_channel_json(result, output_dir / "channel_analysis.json")
    write_channel_csv(result, output_dir / "channel_analysis.csv")
    write_channel_markdown(result, output_dir / "channel_analysis.md")
    return result


def record_multichannel_wav(
    input_device: str,
    wav_path: Path,
    duration_s: float,
    sample_rate_hz: int,
    channels: int,
    sample_format: str,
    record_command: str | None = None,
) -> str | None:
    if record_command:
        command = [
            part.format(
                wav_path=str(wav_path),
                device=input_device,
                duration_s=str(duration_s),
                sample_rate_hz=str(sample_rate_hz),
                channels=str(channels),
                format=sample_format,
            )
            for part in shlex.split(record_command)
        ]
    else:
        command = [
            "arecord",
            "-D",
            input_device,
            "-f",
            sample_format,
            "-r",
            str(sample_rate_hz),
            "-c",
            str(channels),
            "-d",
            str(max(1, math.ceil(duration_s))),
            str(wav_path),
        ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        return f"record command not found: {exc.filename}"
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip()
        return f"record command failed with exit {exc.returncode}: {detail}"
    return None


def analyze_channel_wav(wav_path: Path, input_device: str = "unknown") -> ChannelAnalysisResult:
    with wave.open(str(wav_path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frames = wav.getnframes()
        raw = wav.readframes(frames)

    if sample_width not in {1, 2, 3, 4}:
        raise ValueError(f"Unsupported WAV sample width: {sample_width}")

    interleaved = _iter_pcm_samples(raw, sample_width)
    per_channel = tuple(interleaved[index::channels] for index in range(channels))
    rms_values = [_rms(samples) for samples in per_channel]
    reference_rms = max(rms_values) if rms_values else 0
    base_metrics = tuple(
        _channel_metrics(index, samples, sample_width, reference_rms)
        for index, samples in enumerate(per_channel, start=1)
    )
    metrics = _apply_role_hints(base_metrics)
    duration_s = frames / sample_rate if sample_rate else 0.0
    return ChannelAnalysisResult(
        wav_path=str(wav_path),
        input_device=input_device,
        sample_rate_hz=sample_rate,
        channels=channels,
        sample_width_bytes=sample_width,
        duration_s=duration_s,
        metrics=metrics,
    )


def write_channel_json(result: ChannelAnalysisResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "benchmark": "channel_analysis",
        "created_at": datetime.now(UTC).isoformat(),
        "result": result.to_dict(),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_channel_csv(result: ChannelAnalysisResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "input_device",
        "wav_path",
        "sample_rate_hz",
        "channels",
        "channel_index",
        "rms",
        "peak",
        "clipping_count",
        "speech_activity_ratio",
        "relative_level_db",
        "role_hint",
        "record_error",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        if not result.metrics:
            writer.writerow(
                {
                    "input_device": result.input_device,
                    "wav_path": result.wav_path,
                    "sample_rate_hz": result.sample_rate_hz,
                    "channels": result.channels,
                    "record_error": result.record_error,
                }
            )
            return
        for metric in result.metrics:
            row = {
                "input_device": result.input_device,
                "wav_path": result.wav_path,
                "sample_rate_hz": result.sample_rate_hz,
                "channels": result.channels,
                "record_error": result.record_error,
            }
            row.update(metric.to_dict())
            writer.writerow(row)


def write_channel_markdown(result: ChannelAnalysisResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# EchoLab Channel Analysis",
        "",
        f"- Input device: `{result.input_device}`",
        f"- WAV path: `{result.wav_path}`",
        f"- Capture: `{result.sample_rate_hz} Hz, {result.channels} channel(s), {result.sample_width_bytes} byte samples`",
        f"- Duration: `{result.duration_s:.3f} s`",
        "",
    ]
    if result.record_error:
        lines.extend(["## Recording Error", "", result.record_error, ""])
    lines.extend(
        [
            "## Per-Channel Metrics",
            "",
            "| Channel | RMS | Peak | Clipping Count | Speech Activity | Relative Level dB | Role Hint |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for metric in result.metrics:
        relative = "n/a" if metric.relative_level_db is None else f"{metric.relative_level_db:.2f}"
        lines.append(
            "| "
            f"{metric.channel_index} | "
            f"{metric.rms:.3f} | "
            f"{metric.peak} | "
            f"{metric.clipping_count} | "
            f"{metric.speech_activity_ratio:.3f} | "
            f"{relative} | "
            f"{metric.role_hint} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _interpret_channels(result),
            "",
            "Channel roles are unknown unless proven by hardware documentation or controlled tests. EchoLab does not assume beamformed, raw, or reference channels from channel count alone.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _channel_metrics(
    channel_index: int,
    samples: tuple[int, ...],
    sample_width: int,
    reference_rms: float,
) -> ChannelMetrics:
    rms = float(_rms(samples))
    peak = max((abs(sample) for sample in samples), default=0)
    clipping = _clipping_count(samples, sample_width)
    activity = _speech_activity_ratio(samples)
    relative = None if reference_rms <= 0 or rms <= 0 else 20.0 * math.log10(rms / reference_rms)
    return ChannelMetrics(
        channel_index=channel_index,
        rms=rms,
        peak=peak,
        clipping_count=clipping,
        speech_activity_ratio=activity,
        relative_level_db=relative,
    )


def _apply_role_hints(metrics: tuple[ChannelMetrics, ...]) -> tuple[ChannelMetrics, ...]:
    active = tuple(metric for metric in metrics if not _is_silent(metric))
    if not active:
        return tuple(_with_role_hint(metric, "likely inactive/silent") for metric in metrics)

    active_rms_values = [metric.rms for metric in active]
    median_active_rms = median(active_rms_values)
    louder_threshold = median_active_rms * _db_to_ratio(10.0)
    prominent = tuple(
        metric
        for metric in active
        if len(active) > 1 and median_active_rms > 0 and metric.rms > louder_threshold
    )
    lower_group = tuple(
        metric
        for metric in active
        if metric not in prominent and _has_similar_lower_level_group(metric, active, prominent)
    )

    hinted: list[ChannelMetrics] = []
    for metric in metrics:
        if _is_silent(metric):
            hinted.append(_with_role_hint(metric, "likely inactive/silent"))
        elif metric in prominent:
            hinted.append(_with_role_hint(metric, "likely processed/beamformed or mixed output"))
        elif metric in lower_group:
            hinted.append(_with_role_hint(metric, "likely raw/reference microphone channel"))
        else:
            hinted.append(metric)
    return tuple(hinted)


def _has_similar_lower_level_group(
    metric: ChannelMetrics,
    active: tuple[ChannelMetrics, ...],
    prominent: tuple[ChannelMetrics, ...],
) -> bool:
    candidates = tuple(item for item in active if item not in prominent)
    if len(candidates) < 2 or metric not in candidates or metric.rms <= 0:
        return False
    similar = [
        item
        for item in candidates
        if item.rms > 0 and abs(20.0 * math.log10(item.rms / metric.rms)) <= 4.0
    ]
    return len(similar) >= 2


def _is_silent(metric: ChannelMetrics) -> bool:
    return metric.rms == 0 and metric.peak == 0


def _with_role_hint(metric: ChannelMetrics, role_hint: str) -> ChannelMetrics:
    return ChannelMetrics(
        channel_index=metric.channel_index,
        rms=metric.rms,
        peak=metric.peak,
        clipping_count=metric.clipping_count,
        speech_activity_ratio=metric.speech_activity_ratio,
        relative_level_db=metric.relative_level_db,
        role_hint=role_hint,
    )


def _db_to_ratio(db: float) -> float:
    return 10.0 ** (db / 20.0)


def _speech_activity_ratio(samples: tuple[int, ...]) -> float:
    if not samples:
        return 0.0
    rms = _rms(samples)
    if rms <= 0:
        return 0.0
    threshold = max(1.0, rms * 0.5)
    active = sum(1 for sample in samples if abs(sample) >= threshold)
    return active / len(samples)


def _interpret_channels(result: ChannelAnalysisResult) -> str:
    if result.record_error:
        return "No channel interpretation is available because recording failed."
    if not result.metrics:
        return "No channel metrics were available."
    if result.channels == 1:
        return "This device behaves as a mono capture source for this test."
    role_counts: dict[str, int] = {}
    for metric in result.metrics:
        role_counts[metric.role_hint] = role_counts.get(metric.role_hint, 0) + 1
    role_parts = [f"{count} channel(s) {role}" for role, count in sorted(role_counts.items())]
    levels = [metric.relative_level_db for metric in result.metrics if metric.relative_level_db is not None]
    if any(metric.role_hint != "unknown" for metric in result.metrics):
        return "Cautious role hints: " + ", ".join(role_parts) + ". These are level-based hints, not confirmed hardware roles."
    if levels and max(levels) - min(levels) > 12:
        return "Channels show large relative level differences; this may indicate useful multi-channel data or inactive channels. Roles remain unknown."
    return "Channels are present and broadly comparable in level. Roles remain unknown without additional evidence."


def _iter_pcm_samples(raw: bytes, sample_width: int) -> tuple[int, ...]:
    samples: list[int] = []
    for offset in range(0, len(raw), sample_width):
        chunk = raw[offset : offset + sample_width]
        if len(chunk) != sample_width:
            continue
        if sample_width == 1:
            samples.append(chunk[0] - 128)
        elif sample_width == 3:
            sign_byte = b"\xff" if chunk[-1] & 0x80 else b"\x00"
            samples.append(int.from_bytes(chunk + sign_byte, "little", signed=True))
        else:
            samples.append(int.from_bytes(chunk, "little", signed=True))
    return tuple(samples)


def _rms(samples: tuple[int, ...]) -> int:
    if not samples:
        return 0
    return int(math.sqrt(sum(sample * sample for sample in samples) / len(samples)))


def _clipping_count(samples: tuple[int, ...], sample_width: int) -> int:
    max_sample = 2 ** (8 * sample_width - 1) - 1
    min_sample = -(2 ** (8 * sample_width - 1))
    return sum(1 for sample in samples if sample <= min_sample or sample >= max_sample)

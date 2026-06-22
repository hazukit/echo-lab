from __future__ import annotations

import math
import wave
from pathlib import Path

from echolab.benchmark.models import BenchmarkRecord, Metric


def analyze_wav(path: Path) -> BenchmarkRecord:
    """Measure basic audio quality metrics from a PCM WAV file."""

    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frames = wav.getnframes()
        raw = wav.readframes(frames)

    if sample_width not in {1, 2, 3, 4}:
        raise ValueError(f"Unsupported WAV sample width: {sample_width}")

    samples = tuple(_iter_pcm_samples(raw, sample_width))
    rms = _rms(samples)
    peak = max((abs(sample) for sample in samples), default=0)
    max_possible = float(2 ** (8 * sample_width - 1))
    rms_dbfs = _dbfs(rms, max_possible)
    peak_dbfs = _dbfs(peak, max_possible)
    duration_s = frames / sample_rate if sample_rate else 0.0
    clipping_ratio = _clipping_ratio(samples, sample_width)

    return BenchmarkRecord(
        benchmark="audio_quality",
        subject=str(path),
        variables={
            "sample_rate_hz": sample_rate,
            "channels": channels,
            "sample_width_bytes": sample_width,
            "frames": frames,
            "duration_s": duration_s,
        },
        metrics=(
            Metric("rms", rms, "pcm"),
            Metric("rms_dbfs", rms_dbfs, "dBFS"),
            Metric("peak", peak, "pcm"),
            Metric("peak_dbfs", peak_dbfs, "dBFS"),
            Metric("clipping_ratio", clipping_ratio, "ratio"),
        ),
    )


def _dbfs(value: int, max_possible: float) -> float:
    if value <= 0:
        return float("-inf")
    return 20.0 * math.log10(value / max_possible)


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
    mean_square = sum(sample * sample for sample in samples) / len(samples)
    return int(math.sqrt(mean_square))


def _clipping_ratio(samples: tuple[int, ...], sample_width: int) -> float:
    if not samples:
        return 0.0
    max_sample = 2 ** (8 * sample_width - 1) - 1
    min_sample = -(2 ** (8 * sample_width - 1))
    clipped = sum(1 for sample in samples if sample <= min_sample or sample >= max_sample)
    return clipped / len(samples)

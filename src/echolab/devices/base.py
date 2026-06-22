from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AudioFormat:
    sample_rate_hz: int
    channels: int
    bit_depth: int
    encoding: str


@dataclass(frozen=True, slots=True)
class AudioDeviceInfo:
    device_id: str
    name: str
    formats: tuple[AudioFormat, ...]
    latency_ms: float | None = None
    transport: str | None = None


class AudioDevice(Protocol):
    """Interface for pluggable microphone and audio frontend integrations."""

    def info(self) -> AudioDeviceInfo:
        """Return static and runtime device information."""


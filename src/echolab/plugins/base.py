from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class PluginContext:
    """Input passed from a benchmark runner to an enabled plugin."""

    wav_path: Path
    trial_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PluginResult:
    """Generic plugin output consumed by reports and benchmark adapters."""

    plugin_name: str
    plugin_type: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_name": self.plugin_name,
            "plugin_type": self.plugin_type,
            "data": self.data,
            "error": self.error,
        }


class AudioPlugin(Protocol):
    """Common lifecycle for WakeWord, ASR, DOA, speaker, and future analyzers."""

    def initialize(self) -> None:
        """Prepare the plugin before a benchmark run."""

    def run(self, context: PluginContext) -> PluginResult:
        """Run the plugin for one captured audio artifact."""

    def metadata(self) -> dict[str, Any]:
        """Return plugin metadata for reports."""

    def shutdown(self) -> None:
        """Release plugin resources after a benchmark run."""


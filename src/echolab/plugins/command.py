from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any

from echolab.plugins.base import PluginContext, PluginResult


@dataclass(frozen=True, slots=True)
class CommandPlugin:
    """Generic external-command plugin adapter.

    The command should print JSON. Plain text is accepted and returned as
    `{"text": ...}` for lightweight local scripts.
    """

    plugin_name: str
    plugin_type: str
    command_template: str

    def initialize(self) -> None:
        return None

    def run(self, context: PluginContext) -> PluginResult:
        command = _format_command(
            self.command_template,
            {
                "wav_path": str(context.wav_path),
                "trial_id": context.trial_id,
            },
        )
        try:
            completed = subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            return PluginResult(
                plugin_name=self.plugin_name,
                plugin_type=self.plugin_type,
                error=f"command not found: {exc.filename}",
            )
        except subprocess.CalledProcessError as exc:
            return PluginResult(
                plugin_name=self.plugin_name,
                plugin_type=self.plugin_type,
                error=f"command failed with exit {exc.returncode}: {exc.stderr.strip()}",
            )

        stdout = completed.stdout.strip()
        if not stdout:
            data: dict[str, Any] = {}
        else:
            try:
                parsed = json.loads(stdout)
            except json.JSONDecodeError:
                data = {"text": stdout}
            else:
                data = parsed if isinstance(parsed, dict) else {"value": parsed}
        return PluginResult(plugin_name=self.plugin_name, plugin_type=self.plugin_type, data=data)

    def metadata(self) -> dict[str, Any]:
        return {
            "plugin_name": self.plugin_name,
            "plugin_type": self.plugin_type,
            "adapter": "command",
            "command_template": self.command_template,
        }

    def shutdown(self) -> None:
        return None


class CommandWakeWordPlugin(CommandPlugin):
    def __init__(self, command_template: str, plugin_name: str = "command_wake_word") -> None:
        super().__init__(
            plugin_name=plugin_name,
            plugin_type="wake_word",
            command_template=command_template,
        )


class CommandAsrPlugin(CommandPlugin):
    def __init__(self, command_template: str, plugin_name: str = "command_asr") -> None:
        super().__init__(
            plugin_name=plugin_name,
            plugin_type="asr",
            command_template=command_template,
        )


def _format_command(template: str, values: dict[str, str]) -> list[str]:
    formatted = template
    for key, value in values.items():
        formatted = formatted.replace("{" + key + "}", value)
    return shlex.split(formatted)

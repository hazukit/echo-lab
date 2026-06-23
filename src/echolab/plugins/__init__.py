"""Plugin interfaces and built-in plugin adapters."""

from echolab.plugins.base import AudioPlugin, PluginContext, PluginResult
from echolab.plugins.command import CommandAsrPlugin, CommandWakeWordPlugin

__all__ = [
    "AudioPlugin",
    "CommandAsrPlugin",
    "CommandWakeWordPlugin",
    "PluginContext",
    "PluginResult",
]


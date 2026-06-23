from __future__ import annotations

import csv
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CaptureRecommendation:
    label: str
    device: str
    sample_rate_hz: int | None
    channels: int | None
    format: str | None

    def to_dict(self) -> dict[str, int | str | None]:
        return {
            "label": self.label,
            "device": self.device,
            "sample_rate_hz": self.sample_rate_hz,
            "channels": self.channels,
            "format": self.format,
        }


@dataclass(frozen=True, slots=True)
class AlsaCaptureDevice:
    card_id: int
    card_name: str
    device_id: int
    device_name: str
    alsa_hw: str
    alsa_plughw: str
    usb_name: str | None
    native_format: str | None
    native_sample_rate_hz: int | None
    native_channels: int | None
    supported_formats: tuple[str, ...]
    supported_sample_rates_hz: tuple[int, ...]
    supported_channels: tuple[int, ...]
    mixer_controls_available: bool | None
    inspection_errors: tuple[str, ...]
    recommendations: tuple[CaptureRecommendation, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "card_name": self.card_name,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "alsa_hw": self.alsa_hw,
            "alsa_plughw": self.alsa_plughw,
            "usb_name": self.usb_name,
            "native_format": self.native_format,
            "native_sample_rate_hz": self.native_sample_rate_hz,
            "native_channels": self.native_channels,
            "supported_formats": list(self.supported_formats),
            "supported_sample_rates_hz": list(self.supported_sample_rates_hz),
            "supported_channels": list(self.supported_channels),
            "mixer_controls_available": self.mixer_controls_available,
            "inspection_errors": list(self.inspection_errors),
            "recommendations": [recommendation.to_dict() for recommendation in self.recommendations],
        }


def inspect_alsa_capture_devices() -> list[AlsaCaptureDevice]:
    listing = _run_command(["arecord", "-l"])
    devices = parse_arecord_list(listing.stdout if listing.returncode == 0 else "")
    inspected: list[AlsaCaptureDevice] = []
    for device in devices:
        inspected.append(_inspect_device(device))
    return inspected


def inspect_payload(devices: list[AlsaCaptureDevice]) -> dict[str, Any]:
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "backend": "alsa",
        "devices": [device.to_dict() for device in devices],
    }


def write_inspect_json(devices: list[AlsaCaptureDevice], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inspect_payload(devices), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_inspect_csv(devices: list[AlsaCaptureDevice], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "card_id",
        "device_id",
        "device_name",
        "alsa_hw",
        "alsa_plughw",
        "usb_name",
        "native_format",
        "native_sample_rate_hz",
        "native_channels",
        "mixer_controls_available",
        "recommended_mono_device",
        "recommended_native_device",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for device in devices:
            recommendations = {item.label: item for item in device.recommendations}
            mono = recommendations.get("GeePi mono mode")
            native = recommendations.get("EchoLab native analysis mode")
            writer.writerow(
                {
                    "card_id": device.card_id,
                    "device_id": device.device_id,
                    "device_name": device.device_name,
                    "alsa_hw": device.alsa_hw,
                    "alsa_plughw": device.alsa_plughw,
                    "usb_name": device.usb_name,
                    "native_format": device.native_format,
                    "native_sample_rate_hz": device.native_sample_rate_hz,
                    "native_channels": device.native_channels,
                    "mixer_controls_available": device.mixer_controls_available,
                    "recommended_mono_device": mono.device if mono else None,
                    "recommended_native_device": native.device if native else None,
                }
            )


def render_inspect_markdown(devices: list[AlsaCaptureDevice]) -> str:
    lines = ["# EchoLab Device Inspection", ""]
    if not devices:
        lines.extend(
            [
                "No ALSA capture devices were detected.",
                "",
                "Install ALSA utilities and confirm the microphone is visible with `arecord -l`.",
            ]
        )
        return "\n".join(lines) + "\n"

    for device in devices:
        mixer = _availability(device.mixer_controls_available)
        native = _native_summary(device)
        lines.extend(
            [
                f"## {device.device_name}",
                "",
                f"- ALSA card/device: `{device.alsa_hw}`",
                f"- PlugHW device: `{device.alsa_plughw}`",
                f"- Card name: `{device.card_name}`",
                f"- USB name: `{device.usb_name or 'unknown'}`",
                f"- Native capture: {native}",
                f"- Mixer controls: {mixer}",
                "",
                "Recommended:",
            ]
        )
        for recommendation in device.recommendations:
            lines.append(
                f"- {recommendation.label}: `{recommendation.device}`, "
                f"{recommendation.sample_rate_hz or 'unknown'} Hz, "
                f"{recommendation.channels or 'unknown'} channel(s), "
                f"{recommendation.format or 'unknown'}"
            )
        if device.inspection_errors:
            lines.extend(["", "Inspection notes:"])
            for error in device.inspection_errors:
                lines.append(f"- {error}")
        lines.append("")
    return "\n".join(lines)


def write_inspect_markdown(devices: list[AlsaCaptureDevice], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_inspect_markdown(devices), encoding="utf-8")


def parse_arecord_list(output: str) -> list[AlsaCaptureDevice]:
    devices: list[AlsaCaptureDevice] = []
    for line in output.splitlines():
        parsed = _parse_arecord_device_line(line)
        if parsed is None:
            continue
        card_id, card_name, device_id, device_name = parsed
        alsa_hw = f"hw:{card_id},{device_id}"
        devices.append(
            AlsaCaptureDevice(
                card_id=card_id,
                card_name=card_name,
                device_id=device_id,
                device_name=device_name,
                alsa_hw=alsa_hw,
                alsa_plughw=f"plughw:{card_id},{device_id}",
                usb_name=None,
                native_format=None,
                native_sample_rate_hz=None,
                native_channels=None,
                supported_formats=(),
                supported_sample_rates_hz=(),
                supported_channels=(),
                mixer_controls_available=None,
                inspection_errors=(),
                recommendations=(),
            )
        )
    return devices


def _parse_arecord_device_line(line: str) -> tuple[int, str, int, str] | None:
    if "[" not in line or "]" not in line:
        return None
    card_match = re.search(r"(?:card|カード)\s+(?P<card>\d+)\s*:", line, re.IGNORECASE)
    device_match = re.search(r"(?:device|デバイス)\s+(?P<device>\d+)\s*:", line, re.IGNORECASE)
    if not card_match or not device_match:
        return None

    bracket_values = re.findall(r"\[([^\]]+)\]", line)
    if not bracket_values:
        return None

    card_id = int(card_match.group("card"))
    device_id = int(device_match.group("device"))
    card_name = bracket_values[0].strip()
    device_name = card_name
    return card_id, card_name, device_id, device_name


def parse_hw_params(output: str) -> tuple[str | None, int | None, int | None, tuple[str, ...], tuple[int, ...], tuple[int, ...]]:
    formats = _parse_string_values(output, "FORMAT")
    channels = _parse_int_values(output, "CHANNELS")
    rates = _parse_int_values(output, "RATE")
    native_format = formats[0] if formats else None
    native_channels = max(channels) if channels else None
    native_rate = _select_rate(rates)
    return native_format, native_rate, native_channels, tuple(formats), tuple(rates), tuple(channels)


def _inspect_device(device: AlsaCaptureDevice) -> AlsaCaptureDevice:
    errors: list[str] = []
    hw_params = _run_command(
        [
            "arecord",
            "-D",
            device.alsa_hw,
            "--dump-hw-params",
            "-f",
            "S16_LE",
            "-r",
            "16000",
            "-c",
            "1",
            "-d",
            "1",
            "/dev/null",
        ]
    )
    hw_params_output = hw_params.stderr + "\n" + hw_params.stdout
    if "FORMAT:" in hw_params_output or "CHANNELS:" in hw_params_output or "RATE:" in hw_params_output:
        native_format, native_rate, native_channels, formats, rates, channels = parse_hw_params(hw_params_output)
    else:
        native_format, native_rate, native_channels, formats, rates, channels = (None, None, None, (), (), ())
        errors.append(_command_error("arecord --dump-hw-params", hw_params))

    mixer = _mixer_available(device.card_id)
    if mixer is None:
        errors.append("Mixer controls unavailable or not reported by amixer.")

    return AlsaCaptureDevice(
        card_id=device.card_id,
        card_name=device.card_name,
        device_id=device.device_id,
        device_name=device.device_name,
        alsa_hw=device.alsa_hw,
        alsa_plughw=device.alsa_plughw,
        usb_name=_usb_name(device),
        native_format=native_format,
        native_sample_rate_hz=native_rate,
        native_channels=native_channels,
        supported_formats=formats,
        supported_sample_rates_hz=rates,
        supported_channels=channels,
        mixer_controls_available=mixer,
        inspection_errors=tuple(errors),
        recommendations=_recommend(device, native_format, native_rate, native_channels),
    )


def _recommend(
    device: AlsaCaptureDevice,
    native_format: str | None,
    native_rate: int | None,
    native_channels: int | None,
) -> tuple[CaptureRecommendation, ...]:
    mono_device = device.alsa_hw if native_channels == 1 else device.alsa_plughw
    native_device = device.alsa_hw
    native_analysis_channels = native_channels or 1
    return (
        CaptureRecommendation(
            label="GeePi mono mode",
            device=mono_device,
            sample_rate_hz=native_rate or 16000,
            channels=1,
            format=native_format or "S16_LE",
        ),
        CaptureRecommendation(
            label="EchoLab native analysis mode",
            device=native_device,
            sample_rate_hz=native_rate or 16000,
            channels=native_analysis_channels,
            format=native_format or "S16_LE",
        ),
    )


def _mixer_available(card_id: int) -> bool | None:
    result = _run_command(["amixer", "-c", str(card_id), "scontrols"])
    if result.returncode != 0:
        return None
    return bool(result.stdout.strip())


def _usb_name(device: AlsaCaptureDevice) -> str | None:
    # ALSA's card/device names are the most portable source without touching
    # system-specific USB trees. Keep this generic and evidence-based.
    if device.card_name == device.device_name:
        return device.card_name or None
    combined = f"{device.card_name} {device.device_name}".strip()
    return combined or None


def _parse_string_values(output: str, key: str) -> list[str]:
    raw = _extract_hw_param(output, key)
    if raw is None:
        return []
    return re.findall(r"[A-Z0-9_]+", raw)


def _parse_int_values(output: str, key: str) -> list[int]:
    raw = _extract_hw_param(output, key)
    if raw is None:
        return []
    values: set[int] = set()
    for start, end in re.findall(r"(\d+)\s*-\s*(\d+)", raw):
        values.update({int(start), int(end)})
    for value in re.findall(r"\d+", raw):
        values.add(int(value))
    return sorted(values)


def _extract_hw_param(output: str, key: str) -> str | None:
    pattern = re.compile(rf"^\s*{re.escape(key)}:\s*(?P<value>.+)$", re.MULTILINE)
    match = pattern.search(output)
    return match.group("value").strip() if match else None


def _select_rate(rates: tuple[int, ...] | list[int]) -> int | None:
    if not rates:
        return None
    if 16000 in rates:
        return 16000
    return min(rates, key=lambda value: abs(value - 16000))


def _availability(value: bool | None) -> str:
    if value is True:
        return "available"
    if value is False:
        return "unavailable"
    return "unavailable or unknown"


def _native_summary(device: AlsaCaptureDevice) -> str:
    rate = f"{device.native_sample_rate_hz} Hz" if device.native_sample_rate_hz else "unknown Hz"
    fmt = device.native_format or "unknown format"
    channels = f"{device.native_channels} channels" if device.native_channels else "unknown channels"
    return f"{rate}, {fmt}, {channels}"


def _command_error(label: str, result: subprocess.CompletedProcess[str]) -> str:
    detail = (result.stderr or result.stdout or "").strip()
    if detail:
        return f"{label} failed with exit {result.returncode}: {detail}"
    return f"{label} failed with exit {result.returncode}"


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=False, capture_output=True, text=True)
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(command, 127, "", f"command not found: {exc.filename}")

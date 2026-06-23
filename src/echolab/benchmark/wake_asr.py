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
from echolab.plugins import AudioPlugin, CommandAsrPlugin, CommandWakeWordPlugin, PluginContext, PluginResult


DEFAULT_DISTANCES_M = (0.5, 1.0, 2.0, 3.0)
DEFAULT_ANGLES = ("front", "left", "right")
DEFAULT_PLACEMENTS = ("default",)


@dataclass(frozen=True, slots=True)
class MicConfig:
    name: str
    device: str
    channels: int | None = None
    extract_channel: int | None = None

    def to_dict(self) -> dict[str, int | str | None]:
        return {
            "name": self.name,
            "device": self.device,
            "channels": self.channels,
            "extract_channel": self.extract_channel,
        }


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
    scoring_wav_path: str
    capture_channels: int
    extracted_channel: int | None
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
    plugin_results: tuple[PluginResult, ...] = ()
    notes: str | None = None
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
            "scoring_wav_path": self.scoring_wav_path,
            "capture_channels": self.capture_channels,
            "extracted_channel": self.extracted_channel,
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
            "plugin_results": [result.to_dict() for result in self.plugin_results],
            "notes": self.notes,
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
    plugins = _build_plugins(config)
    _initialize_plugins(plugins)

    trials: list[WakeAsrTrial] = []
    total_trials = (
        len(config.placement_names)
        * len(config.microphones)
        * len(config.distances_m)
        * len(config.angles)
        * config.trials_per_case
    )
    completed_trials = 0
    for placement_name in config.placement_names:
        for mic in config.microphones:
            for distance_m in config.distances_m:
                for angle in config.angles:
                    for trial_index in range(1, config.trials_per_case + 1):
                        completed_trials += 1
                        trial_id = _trial_id(placement_name, mic.name, distance_m, angle, trial_index)
                        wav_path = audio_dir / f"{trial_id}.wav"
                        trial_notes: str | None = None
                        if config.interactive and config.record:
                            action, trial_notes = _prompt_for_trial(
                                placement_name,
                                mic,
                                distance_m,
                                angle,
                                config,
                                trial_index,
                                completed_trials,
                                total_trials,
                            )
                            if action == "quit":
                                _shutdown_plugins(plugins)
                                return trials
                            if action == "skip":
                                trial = _score_trial(
                                    config,
                                    plugins,
                                    placement_name,
                                    mic,
                                    distance_m,
                                    angle,
                                    trial_index,
                                    wav_path,
                                    "skipped by operator",
                                    trial_notes,
                                )
                                trials.append(trial)
                                continue
                        error = _record_trial(config, mic, wav_path) if config.record else None
                        if config.interactive and config.record:
                            action, after_notes = _prompt_after_trial()
                            trial_notes = _merge_notes(trial_notes, after_notes)
                            if action == "retry":
                                error = _record_trial(config, mic, wav_path)
                                action, after_retry_notes = _prompt_after_trial()
                                trial_notes = _merge_notes(trial_notes, after_retry_notes)
                            if action == "skip":
                                error = "skipped by operator after recording"
                            if action == "quit":
                                trial = _score_trial(
                                    config,
                                    plugins,
                                    placement_name,
                                    mic,
                                    distance_m,
                                    angle,
                                    trial_index,
                                    wav_path,
                                    error,
                                    trial_notes,
                                )
                                trials.append(trial)
                                _shutdown_plugins(plugins)
                                return trials
                        trial = _score_trial(
                            config,
                            plugins,
                            placement_name,
                            mic,
                            distance_m,
                            angle,
                            trial_index,
                            wav_path,
                            error,
                            trial_notes,
                        )
                        trials.append(trial)
    _shutdown_plugins(plugins)
    return trials


def _build_plugins(config: WakeAsrConfig) -> tuple[AudioPlugin, ...]:
    plugins: list[AudioPlugin] = []
    if config.wake_command:
        plugins.append(CommandWakeWordPlugin(config.wake_command))
    if config.asr_command:
        plugins.append(CommandAsrPlugin(config.asr_command))
    return tuple(plugins)


def _initialize_plugins(plugins: tuple[AudioPlugin, ...]) -> None:
    for plugin in plugins:
        plugin.initialize()


def _shutdown_plugins(plugins: tuple[AudioPlugin, ...]) -> None:
    for plugin in plugins:
        plugin.shutdown()


def _has_plugin_type(plugins: tuple[AudioPlugin, ...], plugin_type: str) -> bool:
    return any(plugin.metadata().get("plugin_type") == plugin_type for plugin in plugins)


def write_wake_asr_json(trials: list[WakeAsrTrial], config: WakeAsrConfig, path: Path) -> None:
    plugins = _build_plugins(config)
    payload = {
        "benchmark": "wake_asr",
        "created_at": datetime.now(UTC).isoformat(),
        "metadata": {
            "microphones": [mic.to_dict() for mic in config.microphones],
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
            "wake_configured": _has_plugin_type(plugins, "wake_word"),
            "asr_configured": _has_plugin_type(plugins, "asr"),
            "plugins": [plugin.metadata() for plugin in plugins],
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
        "scoring_wav_path",
        "capture_channels",
        "extracted_channel",
        "wake_configured",
        "wake_detected",
        "wake_confidence",
        "wake_latency_ms",
        "audio_rms",
        "audio_peak",
        "audio_noise_floor_dbfs",
        "false_negative",
        "asr_configured",
        "asr_text",
        "asr_latency_ms",
        "asr_score",
        "plugin_results_json",
        "notes",
        "error",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for trial in trials:
            row_data = trial.to_dict()
            row = {key: row_data[key] for key in fieldnames if key in row_data}
            row["false_negative"] = trial.wake_configured and trial.wake_detected is False
            row["plugin_results_json"] = json.dumps(row_data["plugin_results"], sort_keys=True)
            writer.writerow(row)


def write_wake_asr_markdown(trials: list[WakeAsrTrial], config: WakeAsrConfig, path: Path) -> None:
    plugins = _build_plugins(config)
    summary = summarize_wake_asr(trials)
    best_wake = _best_device(summary, "wake_detection_rate")
    best_confidence = _best_device(summary, "mean_wake_confidence")
    best_asr = _best_device(summary, "mean_asr_score")
    dropoff = _distance_dropoff(trials)
    angle_answer = _angle_answer(trials)
    capture_answer = _capture_mode_answer(summary)
    recommended_config = _recommended_capture_config(summary, config)

    lines = [
        "# Wake Word + ASR Baseline Comparison",
        "",
        "## Household Answers",
        "",
        f"- Which mic detects wake word more reliably? {_answer(best_wake)}",
        f"- Which mic has higher wake confidence? {_answer(best_confidence)}",
        f"- Which mic gives better ASR text? {_answer(best_asr)}",
        f"- At what distance does performance drop? {dropoff}",
        f"- Does angle matter? {angle_answer}",
        f"- Is mono plughw enough, or should GeePi use native CH1 extraction? {capture_answer}",
        f"- Recommended GeePi capture config: {recommended_config}",
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
        f"- Wake scoring configured: `{_has_plugin_type(plugins, 'wake_word')}`",
        f"- ASR configured: `{_has_plugin_type(plugins, 'asr')}`",
        f"- Enabled plugins: `{', '.join(plugin.metadata()['plugin_name'] for plugin in plugins) or 'none'}`",
        "",
        "## Device Summary",
        "",
        "| Mic | Capture | Trials | Wake Detection | False Negatives | Mean Wake Confidence | Mean Wake Latency ms | RMS | Peak | Errors |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mic_name, values in sorted(summary.items()):
        lines.append(
            "| "
            f"{mic_name} | "
            f"{values['capture_mode']} | "
            f"{values['trial_count']} | "
            f"{_pct(values.get('wake_detection_rate'))} | "
            f"{values['false_negative_count']} | "
            f"{_num(values.get('mean_wake_confidence'))} | "
            f"{_num(values.get('mean_wake_latency_ms'))} | "
            f"{_num(values.get('mean_audio_rms'))} | "
            f"{_num(values.get('mean_audio_peak'))} | "
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
            "## Angle Summary",
            "",
            "| Mic | Angle | Trials | Wake Detection | Mean Wake Confidence |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in _summarize_by_angle(trials):
        lines.append(
            "| "
            f"{row['mic_name']} | "
            f"{row['angle']} | "
            f"{row['trial_count']} | "
            f"{_pct(row.get('wake_detection_rate'))} | "
            f"{_num(row.get('mean_wake_confidence'))} |"
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
    summary: dict[str, dict[str, int | float | str | None]] = {}
    for mic_name in sorted({trial.mic_name for trial in trials}):
        mic_trials = [trial for trial in trials if trial.mic_name == mic_name]
        wake_trials = [trial for trial in mic_trials if trial.wake_configured]
        detected = [trial for trial in wake_trials if trial.wake_detected is True]
        missed = [trial for trial in wake_trials if trial.wake_detected is False]
        confidences = [trial.wake_confidence for trial in mic_trials if trial.wake_confidence is not None]
        wake_latencies = [trial.wake_latency_ms for trial in mic_trials if trial.wake_latency_ms is not None]
        asr_scores = [trial.asr_score for trial in mic_trials if trial.asr_score is not None]
        asr_latencies = [trial.asr_latency_ms for trial in mic_trials if trial.asr_latency_ms is not None]
        rms_values = [trial.audio_rms for trial in mic_trials if trial.audio_rms is not None]
        peak_values = [trial.audio_peak for trial in mic_trials if trial.audio_peak is not None]
        first = mic_trials[0]
        summary[mic_name] = {
            "trial_count": len(mic_trials),
            "capture_mode": _capture_mode(first),
            "wake_detection_rate": len(detected) / len(wake_trials) if wake_trials else None,
            "false_negative_count": len(missed),
            "mean_wake_confidence": mean(confidences) if confidences else None,
            "mean_wake_latency_ms": mean(wake_latencies) if wake_latencies else None,
            "mean_asr_score": mean(asr_scores) if asr_scores else None,
            "mean_asr_latency_ms": mean(asr_latencies) if asr_latencies else None,
            "mean_audio_rms": mean(rms_values) if rms_values else None,
            "mean_audio_peak": mean(peak_values) if peak_values else None,
            "error_count": sum(1 for trial in mic_trials if trial.error),
        }
    return summary


def parse_mic(value: str) -> MicConfig:
    if "=" not in value:
        raise ValueError("Microphone must use NAME=DEVICE format, for example SunFounder=plughw:1,0")
    name, spec = value.split("=", 1)
    name = name.strip()
    parts = [part.strip() for part in spec.split(";") if part.strip()]
    device = parts[0] if parts else ""
    options = _parse_mic_options(parts[1:])
    if not name or not device:
        raise ValueError("Microphone name and device must both be non-empty")
    return MicConfig(
        name=name,
        device=device,
        channels=_optional_int(options.get("channels")),
        extract_channel=_optional_int(options.get("extract_channel")),
    )


def _parse_mic_options(parts: list[str]) -> dict[str, str]:
    options: dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            raise ValueError(f"Invalid microphone option: {part}")
        key, parsed_value = part.split("=", 1)
        options[key.strip()] = parsed_value.strip()
    return options


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
    channels = mic.channels or config.channels
    if config.record_command:
        return _format_command(
            config.record_command,
            {
                "wav_path": str(wav_path),
                "device": mic.device,
                "duration_s": str(config.duration_s),
                "sample_rate_hz": str(config.sample_rate_hz),
                "channels": str(channels),
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
        str(channels),
        "-d",
        str(max(1, math.ceil(config.duration_s))),
        str(wav_path),
    ]


def _score_trial(
    config: WakeAsrConfig,
    plugins: tuple[AudioPlugin, ...],
    placement_name: str,
    mic: MicConfig,
    distance_m: float,
    angle: str,
    trial_index: int,
    wav_path: Path,
    error: str | None,
    notes: str | None = None,
) -> WakeAsrTrial:
    trial_id = _trial_id(placement_name, mic.name, distance_m, angle, trial_index)
    timestamp = datetime.now(UTC).isoformat()
    wake_raw: dict[str, Any] = {}
    asr_raw: dict[str, Any] = {}
    plugin_results: tuple[PluginResult, ...] = ()
    scoring_wav_path = _prepare_scoring_wav(mic, wav_path) if error is None and wav_path.exists() else wav_path
    if error is None and scoring_wav_path is None:
        error = f"failed to extract channel {mic.extract_channel} from {wav_path}"
        scoring_wav_path = wav_path
    audio_metrics = _audio_metrics(scoring_wav_path) if error is None and scoring_wav_path.exists() else {}
    wake_detected: bool | None = None
    wake_confidence: float | None = None
    wake_latency_ms: float | None = None
    asr_text: str | None = None
    asr_latency_ms: float | None = None

    if error is None and plugins:
        context = PluginContext(
            wav_path=scoring_wav_path,
            trial_id=trial_id,
            metadata={
                "mic_name": mic.name,
                "input_device": mic.device,
                "placement_name": placement_name,
                "distance_m": distance_m,
                "angle": angle,
                "speaker_label": config.speaker_label,
                "condition": config.condition,
                "utterance": config.utterance,
            },
        )
        plugin_results = tuple(plugin.run(context) for plugin in plugins)
        wake_result = _first_plugin_result(plugin_results, "wake_word")
        if wake_result is not None:
            wake_raw = wake_result.data
            wake_detected = _optional_bool(wake_raw.get("detected"))
            wake_confidence = _optional_float(wake_raw.get("confidence"))
            wake_latency_ms = _optional_float(wake_raw.get("latency_ms"))
            if wake_result.error:
                error = wake_result.error
        asr_result = _first_plugin_result(plugin_results, "asr")
        if asr_result is not None:
            asr_raw = asr_result.data
            asr_text = _optional_str(asr_raw.get("text"))
            asr_latency_ms = _optional_float(asr_raw.get("latency_ms"))
            if asr_result.error:
                error = asr_result.error

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
        scoring_wav_path=str(scoring_wav_path),
        capture_channels=mic.channels or config.channels,
        extracted_channel=mic.extract_channel,
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
        plugin_results=plugin_results,
        notes=notes,
        error=error,
    )


def _audio_metrics(wav_path: Path) -> dict[str, Any]:
    try:
        record = analyze_wav(wav_path)
    except (OSError, EOFError, wave.Error, ValueError):
        return {}
    return {metric.name: metric.value for metric in record.metrics}


def _prepare_scoring_wav(mic: MicConfig, wav_path: Path) -> Path | None:
    if mic.extract_channel is None:
        return wav_path
    extracted_path = wav_path.with_name(f"{wav_path.stem}_ch{mic.extract_channel}.wav")
    try:
        _extract_channel_wav(wav_path, extracted_path, mic.extract_channel)
    except (OSError, EOFError, wave.Error, ValueError):
        return None
    return extracted_path


def _extract_channel_wav(source_path: Path, output_path: Path, channel_index: int) -> None:
    if channel_index < 1:
        raise ValueError("extract_channel must be 1-based")
    with wave.open(str(source_path), "rb") as source:
        channels = source.getnchannels()
        sample_width = source.getsampwidth()
        sample_rate = source.getframerate()
        frames = source.getnframes()
        raw = source.readframes(frames)
    if channel_index > channels:
        raise ValueError(f"extract_channel {channel_index} exceeds WAV channel count {channels}")
    frame_width = sample_width * channels
    selected = bytearray()
    start = (channel_index - 1) * sample_width
    for offset in range(0, len(raw), frame_width):
        frame = raw[offset : offset + frame_width]
        if len(frame) != frame_width:
            continue
        selected.extend(frame[start : start + sample_width])
    with wave.open(str(output_path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(sample_width)
        output.setframerate(sample_rate)
        output.writeframes(bytes(selected))


def _first_plugin_result(results: tuple[PluginResult, ...], plugin_type: str) -> PluginResult | None:
    return next((result for result in results if result.plugin_type == plugin_type), None)


def _format_command(template: str, values: dict[str, str]) -> list[str]:
    formatted = template
    for key, value in values.items():
        formatted = formatted.replace("{" + key + "}", value)
    return shlex.split(formatted)


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
    completed_trials: int,
    total_trials: int,
) -> tuple[str, str | None]:
    print()
    print(f"Trial {completed_trials}/{total_trials}")
    print(f"Placement: {placement_name}")
    print(f"Mic: {mic.name} ({mic.device})")
    print(f"Distance: {distance_m} m / Angle: {angle} / Trial: {trial_index}")
    print(f"Speaker: {config.speaker_label} / Condition: {config.condition}")
    print(f"Utterance: {config.utterance}")
    response = input("Press Enter to record, s=skip, q=quit, or type a note: ").strip()
    if response.lower() == "s":
        return "skip", None
    if response.lower() == "q":
        return "quit", None
    return "record", response or None


def _prompt_after_trial() -> tuple[str, str | None]:
    response = input("Recorded. Press Enter to keep, r=retry, s=skip, q=quit, or type a note: ").strip()
    if response.lower() == "r":
        return "retry", None
    if response.lower() == "s":
        return "skip", None
    if response.lower() == "q":
        return "quit", None
    return "keep", response or None


def _merge_notes(first: str | None, second: str | None) -> str | None:
    notes = [note for note in (first, second) if note]
    return " | ".join(notes) if notes else None


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


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _best_device(summary: dict[str, dict[str, int | float | str | None]], metric: str) -> tuple[str, float] | None:
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


def _capture_mode(trial: WakeAsrTrial) -> str:
    if trial.extracted_channel is not None:
        return f"{trial.input_device}, {trial.capture_channels}ch -> CH{trial.extracted_channel}"
    return f"{trial.input_device}, {trial.capture_channels}ch"


def _capture_mode_answer(summary: dict[str, dict[str, int | float | str | None]]) -> str:
    mono = _find_summary(summary, "mono")
    native = _find_summary(summary, "ch1") or _find_summary(summary, "native")
    if not mono or not native:
        return "Not enough mono and native CH1 results to decide."
    mono_score = _combined_wake_score(mono)
    native_score = _combined_wake_score(native)
    if mono_score is None or native_score is None:
        return "Not scored yet; configure wake scoring for both capture modes."
    if abs(mono_score - native_score) < 0.03:
        return "Mono plughw appears sufficient in this run."
    if native_score > mono_score:
        return "Native CH1 extraction performs better in this run; consider it for GeePi if runtime complexity is acceptable."
    return "Mono plughw performs better in this run and is the simpler GeePi capture mode."


def _recommended_capture_config(
    summary: dict[str, dict[str, int | float | str | None]],
    config: WakeAsrConfig,
) -> str:
    best = _best_device(summary, "wake_detection_rate") or _best_device(summary, "mean_wake_confidence")
    if best is None:
        first = config.microphones[0] if config.microphones else None
        if first is None:
            return "No microphone configured."
        return _mic_recommendation(first, config)
    mic = next((item for item in config.microphones if item.name == best[0]), None)
    return _mic_recommendation(mic, config) if mic else best[0]


def _mic_recommendation(mic: MicConfig, config: WakeAsrConfig) -> str:
    channels = mic.channels or config.channels
    if mic.extract_channel is not None:
        return f"{mic.device}, {config.sample_rate_hz} Hz, capture {channels}ch, extract CH{mic.extract_channel}"
    return f"{mic.device}, {config.sample_rate_hz} Hz, {channels}ch"


def _combined_wake_score(values: dict[str, int | float | str | None]) -> float | None:
    detection = values.get("wake_detection_rate")
    confidence = values.get("mean_wake_confidence")
    if isinstance(detection, int | float) and isinstance(confidence, int | float):
        return float(detection) * 0.75 + float(confidence) * 0.25
    if isinstance(detection, int | float):
        return float(detection)
    if isinstance(confidence, int | float):
        return float(confidence)
    return None


def _angle_answer(trials: list[WakeAsrTrial]) -> str:
    rows = _summarize_by_angle(trials)
    scored = [row for row in rows if isinstance(row.get("wake_detection_rate"), int | float)]
    if len(scored) < 2:
        return "Not scored yet; collect wake detections across angles."
    rates = [float(row["wake_detection_rate"]) for row in scored if isinstance(row.get("wake_detection_rate"), int | float)]
    if max(rates) - min(rates) < 0.1:
        return "No strong angle effect in this run."
    weakest = min(scored, key=lambda row: float(row["wake_detection_rate"]))
    return f"Yes; weakest observed angle is {weakest['angle']} for {weakest['mic_name']} ({_pct(weakest.get('wake_detection_rate'))})."


def _respeaker_answer(summary: dict[str, dict[str, int | float | str | None]]) -> str:
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
    summary: dict[str, dict[str, int | float | str | None]], needle: str
) -> dict[str, int | float | str | None] | None:
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


def _summarize_by_angle(trials: list[WakeAsrTrial]) -> list[dict[str, int | float | str | None]]:
    rows: list[dict[str, int | float | str | None]] = []
    keys = sorted({(trial.mic_name, trial.angle) for trial in trials})
    for mic_name, angle in keys:
        selected = [trial for trial in trials if trial.mic_name == mic_name and trial.angle == angle]
        wake_trials = [trial for trial in selected if trial.wake_configured]
        detected = [trial for trial in wake_trials if trial.wake_detected is True]
        confidences = [trial.wake_confidence for trial in selected if trial.wake_confidence is not None]
        rows.append(
            {
                "mic_name": mic_name,
                "angle": angle,
                "trial_count": len(selected),
                "wake_detection_rate": len(detected) / len(wake_trials) if wake_trials else None,
                "mean_wake_confidence": mean(confidences) if confidences else None,
            }
        )
    return rows


def _pct(value: int | float | str | None) -> str:
    if not isinstance(value, int | float):
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def _num(value: int | float | str | None) -> str:
    if not isinstance(value, int | float):
        return "n/a"
    return f"{float(value):.3f}"

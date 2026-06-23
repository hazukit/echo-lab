from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

from echolab.benchmark.wake_asr import (
    WakeAsrConfig,
    WakeAsrTrial,
    collect_wake_asr_trials,
    write_wake_asr_csv,
)


@dataclass(frozen=True, slots=True)
class PlacementBenchmarkConfig:
    wake_asr_config: WakeAsrConfig
    placement_acceptability: dict[str, str] = field(default_factory=dict)


def run_placement_benchmark(config: PlacementBenchmarkConfig) -> list[WakeAsrTrial]:
    trials = collect_wake_asr_trials(config.wake_asr_config)
    output_dir = config.wake_asr_config.output_dir
    write_placement_json(trials, config, output_dir / "placement_results.json")
    write_wake_asr_csv(trials, output_dir / "placement_results.csv")
    write_placement_markdown(trials, config, output_dir / "placement_report.md")
    return trials


def write_placement_json(trials: list[WakeAsrTrial], config: PlacementBenchmarkConfig, path: Path) -> None:
    wake_config = config.wake_asr_config
    payload = {
        "benchmark": "placement",
        "created_at": datetime.now(UTC).isoformat(),
        "metadata": {
            "microphones": [{"name": mic.name, "device": mic.device} for mic in wake_config.microphones],
            "placement_names": list(wake_config.placement_names),
            "placement_notes": wake_config.placement_notes,
            "placement_acceptability": config.placement_acceptability,
            "distances_m": list(wake_config.distances_m),
            "angles": list(wake_config.angles),
            "speaker_label": wake_config.speaker_label,
            "condition": wake_config.condition,
            "utterance": wake_config.utterance,
            "expected_text": wake_config.expected_text,
            "duration_s": wake_config.duration_s,
            "sample_rate_hz": wake_config.sample_rate_hz,
            "channels": wake_config.channels,
            "trials_per_case": wake_config.trials_per_case,
            "wake_configured": wake_config.wake_command is not None,
            "asr_configured": wake_config.asr_command is not None,
        },
        "placements": summarize_placements(trials, config.placement_acceptability),
        "trials": [trial.to_dict() for trial in trials],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_placement_markdown(trials: list[WakeAsrTrial], config: PlacementBenchmarkConfig, path: Path) -> None:
    summary = summarize_placements(trials, config.placement_acceptability)
    ranking = sorted(summary.items(), key=lambda item: float(item[1]["household_usability_score"]), reverse=True)
    best = ranking[0][0] if ranking else None

    lines = [
        "# GeePi Placement Benchmark",
        "",
        "## Household Answers",
        "",
        f"- Which placement works best? {_best_answer(best, summary)}",
        f"- Which placement fails at distance? {_distance_failure_answer(trials)}",
        f"- Does under-display placement hurt recognition? {_under_display_answer(summary)}",
        f"- Is the placement acceptable for GeePi's physical design? {_physical_answer(summary)}",
        "",
        "## Configuration",
        "",
        f"- Condition: `{config.wake_asr_config.condition}`",
        f"- Speaker label: `{config.wake_asr_config.speaker_label}`",
        f"- Utterance: `{config.wake_asr_config.utterance}`",
        f"- Expected ASR text: `{config.wake_asr_config.expected_text or ''}`",
        f"- Distances: `{', '.join(str(distance) for distance in config.wake_asr_config.distances_m)} m`",
        f"- Angles: `{', '.join(config.wake_asr_config.angles)}`",
        f"- Trials per case: `{config.wake_asr_config.trials_per_case}`",
        "",
        "## Placement Ranking",
        "",
        "| Rank | Placement | Score | Trials | Wake Detection | Wake Confidence | ASR Accuracy | RMS | Peak | Noise Floor dBFS | Physical | Notes |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for rank, (placement_name, values) in enumerate(ranking, start=1):
        lines.append(
            "| "
            f"{rank} | "
            f"{placement_name} | "
            f"{_num(values['household_usability_score'])} | "
            f"{values['trial_count']} | "
            f"{_pct(values.get('wake_detection_rate'))} | "
            f"{_num(values.get('mean_wake_confidence'))} | "
            f"{_pct(values.get('mean_asr_score'))} | "
            f"{_num(values.get('mean_audio_rms'))} | "
            f"{_num(values.get('mean_audio_peak'))} | "
            f"{_num(values.get('mean_noise_floor_dbfs'))} | "
            f"{values['physical_acceptability']} | "
            f"{values['placement_notes'] or ''} |"
        )

    lines.extend(
        [
            "",
            "## Distance Behavior",
            "",
            "| Placement | Distance m | Trials | Wake Detection | ASR Accuracy |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in _summarize_by_placement_distance(trials):
        lines.append(
            "| "
            f"{row['placement_name']} | "
            f"{row['distance_m']} | "
            f"{row['trial_count']} | "
            f"{_pct(row.get('wake_detection_rate'))} | "
            f"{_pct(row.get('mean_asr_score'))} |"
        )

    lines.extend(
        [
            "",
            "## Raw Result Files",
            "",
            "- `placement_results.json`",
            "- `placement_results.csv`",
            "- `placement_report.md`",
            "- `audio/*.wav`",
            "",
            "## Scoring Notes",
            "",
            "Household usability ranking prioritizes wake detection and ASR accuracy. Wake confidence, audio levels, distance resilience, and physical acceptability adjust the ranking but do not replace raw metrics.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def summarize_placements(
    trials: list[WakeAsrTrial], placement_acceptability: dict[str, str]
) -> dict[str, dict[str, int | float | str | None]]:
    summary: dict[str, dict[str, int | float | str | None]] = {}
    for placement_name in sorted({trial.placement_name for trial in trials}):
        selected = [trial for trial in trials if trial.placement_name == placement_name]
        wake_trials = [trial for trial in selected if trial.wake_configured]
        detected = [trial for trial in wake_trials if trial.wake_detected is True]
        confidences = [trial.wake_confidence for trial in selected if trial.wake_confidence is not None]
        asr_scores = [trial.asr_score for trial in selected if trial.asr_score is not None]
        rms_values = [trial.audio_rms for trial in selected if trial.audio_rms is not None]
        peak_values = [trial.audio_peak for trial in selected if trial.audio_peak is not None]
        noise_values = [trial.audio_noise_floor_dbfs for trial in selected if trial.audio_noise_floor_dbfs is not None]
        notes = next((trial.placement_notes for trial in selected if trial.placement_notes), None)
        physical = placement_acceptability.get(placement_name, "unknown")
        values: dict[str, int | float | str | None] = {
            "trial_count": len(selected),
            "wake_detection_rate": len(detected) / len(wake_trials) if wake_trials else None,
            "mean_wake_confidence": mean(confidences) if confidences else None,
            "mean_asr_score": mean(asr_scores) if asr_scores else None,
            "mean_audio_rms": mean(rms_values) if rms_values else None,
            "mean_audio_peak": mean(peak_values) if peak_values else None,
            "mean_noise_floor_dbfs": mean(noise_values) if noise_values else None,
            "distance_resilience": _distance_resilience(selected),
            "physical_acceptability": physical,
            "placement_notes": notes,
        }
        values["household_usability_score"] = _household_usability_score(values)
        summary[placement_name] = values
    return summary


def parse_key_value(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise ValueError("Expected NAME=VALUE")
    key, parsed_value = value.split("=", 1)
    key = key.strip()
    parsed_value = parsed_value.strip()
    if not key or not parsed_value:
        raise ValueError("NAME and VALUE must both be non-empty")
    return key, parsed_value


def _household_usability_score(values: dict[str, int | float | str | None]) -> float:
    weighted_total = 0.0
    weight_used = 0.0
    for key, weight in (
        ("wake_detection_rate", 0.35),
        ("mean_asr_score", 0.35),
        ("mean_wake_confidence", 0.15),
        ("distance_resilience", 0.10),
    ):
        value = values.get(key)
        if isinstance(value, int | float):
            weighted_total += float(value) * weight
            weight_used += weight

    noise_score = _noise_score(values.get("mean_noise_floor_dbfs"))
    if noise_score is not None:
        weighted_total += noise_score * 0.05
        weight_used += 0.05

    if weight_used == 0:
        base = 0.0
    else:
        base = weighted_total / weight_used
    return max(0.0, min(100.0, base * 100.0 * _physical_multiplier(str(values.get("physical_acceptability")))))


def _noise_score(value: int | float | str | None) -> float | None:
    if not isinstance(value, int | float):
        return None
    if value <= -60:
        return 1.0
    if value >= -20:
        return 0.0
    return (-20.0 - float(value)) / 40.0


def _physical_multiplier(label: str) -> float:
    normalized = label.lower()
    if normalized in {"good", "ok", "acceptable", "yes"}:
        return 1.0
    if normalized in {"minor", "warning", "fair"}:
        return 0.9
    if normalized in {"poor", "bad"}:
        return 0.75
    if normalized in {"blocking", "unacceptable", "no"}:
        return 0.5
    return 0.95


def _distance_resilience(trials: list[WakeAsrTrial]) -> float | None:
    rows = _summarize_by_placement_distance(trials)
    scored = []
    for row in rows:
        wake = row.get("wake_detection_rate")
        asr = row.get("mean_asr_score")
        values = [float(value) for value in (wake, asr) if isinstance(value, int | float)]
        if values:
            scored.append(mean(values))
    return mean(scored) if scored else None


def _summarize_by_placement_distance(trials: list[WakeAsrTrial]) -> list[dict[str, int | float | str | None]]:
    rows: list[dict[str, int | float | str | None]] = []
    keys = sorted({(trial.placement_name, trial.distance_m) for trial in trials})
    for placement_name, distance_m in keys:
        selected = [trial for trial in trials if trial.placement_name == placement_name and trial.distance_m == distance_m]
        wake_trials = [trial for trial in selected if trial.wake_configured]
        detected = [trial for trial in wake_trials if trial.wake_detected is True]
        asr_scores = [trial.asr_score for trial in selected if trial.asr_score is not None]
        rows.append(
            {
                "placement_name": placement_name,
                "distance_m": distance_m,
                "trial_count": len(selected),
                "wake_detection_rate": len(detected) / len(wake_trials) if wake_trials else None,
                "mean_asr_score": mean(asr_scores) if asr_scores else None,
            }
        )
    return rows


def _best_answer(best: str | None, summary: dict[str, dict[str, int | float | str | None]]) -> str:
    if best is None:
        return "No placement trials were recorded."
    if not _has_scored_metrics(summary):
        return "Not scored yet; configure wake or ASR scoring, or record WAV files for audio metrics."
    score = summary[best]["household_usability_score"]
    return f"{best} ranks highest for household usability ({_num(score)} / 100)."


def _distance_failure_answer(trials: list[WakeAsrTrial]) -> str:
    failing = []
    for row in _summarize_by_placement_distance(trials):
        wake = row.get("wake_detection_rate")
        asr = row.get("mean_asr_score")
        if (isinstance(wake, int | float) and wake < 0.8) or (isinstance(asr, int | float) and asr < 0.8):
            failing.append(row)
    if not failing:
        return "No scored placement drops below 80% in the tested distance range."
    first = min(failing, key=lambda row: float(row["distance_m"]))
    return f"{first['placement_name']} first drops below 80% around {first['distance_m']} m."


def _under_display_answer(summary: dict[str, dict[str, int | float | str | None]]) -> str:
    under = [item for item in summary.items() if "under" in item[0].lower()]
    if not under:
        return "No under-display placement was tested."
    if not _has_scored_metrics(summary):
        return "Under-display was tested, but scoring is not configured yet."
    best_under = max(under, key=lambda item: float(item[1]["household_usability_score"]))
    best_any = max(summary.items(), key=lambda item: float(item[1]["household_usability_score"]))
    delta = float(best_any[1]["household_usability_score"]) - float(best_under[1]["household_usability_score"])
    if delta < 5:
        return "No clear penalty; under-display is close to the best placement."
    return f"Yes, under-display trails the best placement by {_num(delta)} points in this run."


def _has_scored_metrics(summary: dict[str, dict[str, int | float | str | None]]) -> bool:
    metric_keys = (
        "wake_detection_rate",
        "mean_wake_confidence",
        "mean_asr_score",
        "mean_audio_rms",
        "mean_audio_peak",
        "mean_noise_floor_dbfs",
    )
    return any(isinstance(values.get(key), int | float) for values in summary.values() for key in metric_keys)


def _physical_answer(summary: dict[str, dict[str, int | float | str | None]]) -> str:
    if not summary:
        return "No placement data."
    labels = {str(values["physical_acceptability"]).lower() for values in summary.values()}
    if labels == {"unknown"}:
        return "Not rated; use --placement-acceptability to record physical design fit."
    blocking = [name for name, values in summary.items() if str(values["physical_acceptability"]).lower() in {"blocking", "unacceptable", "no"}]
    if blocking:
        return f"Some placements are physically unacceptable: {', '.join(blocking)}."
    return "Rated placements are physically acceptable or only minor concerns."


def _pct(value: int | float | str | None) -> str:
    if not isinstance(value, int | float):
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def _num(value: int | float | str | None) -> str:
    if not isinstance(value, int | float):
        return "n/a"
    return f"{float(value):.3f}"

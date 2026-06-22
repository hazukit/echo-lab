from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from echolab.benchmark.models import BenchmarkRun


def write_json(run: BenchmarkRun, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(run: BenchmarkRun, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(_flatten_records(run))
    fieldnames = sorted({key for row in rows for key in row})

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(run: BenchmarkRun, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {run.name}",
        "",
        f"- Run ID: `{run.run_id}`",
        f"- Created: `{run.created_at.isoformat()}`",
        f"- Records: `{len(run.records)}`",
        "",
    ]

    for index, record in enumerate(run.records, start=1):
        lines.extend(
            [
                f"## {index}. {record.subject}",
                "",
                f"- Benchmark: `{record.benchmark}`",
            ]
        )
        if record.variables:
            lines.append("- Variables:")
            for key, value in sorted(record.variables.items()):
                lines.append(f"  - `{key}`: `{value}`")
        lines.extend(["", "| Metric | Value | Unit |", "| --- | ---: | --- |"])
        for metric in record.metrics:
            unit = metric.unit or ""
            lines.append(f"| `{metric.name}` | `{metric.value}` | `{unit}` |")
        if record.notes:
            lines.extend(["", record.notes])
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def _flatten_records(run: BenchmarkRun) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in run.records:
        base: dict[str, Any] = {
            "run_id": run.run_id,
            "run_name": run.name,
            "created_at": run.created_at.isoformat(),
            "benchmark": record.benchmark,
            "subject": record.subject,
            "notes": record.notes,
        }
        base.update({f"var_{key}": value for key, value in record.variables.items()})
        for metric in record.metrics:
            row = dict(base)
            row["metric"] = metric.name
            row["value"] = metric.value
            row["unit"] = metric.unit
            rows.append(row)
    return rows


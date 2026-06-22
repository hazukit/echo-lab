from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


MetricValue = int | float | str | bool | None


@dataclass(frozen=True, slots=True)
class Metric:
    """A single comparable measurement."""

    name: str
    value: MetricValue
    unit: str | None = None

    def to_dict(self) -> dict[str, MetricValue]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkRecord:
    """One benchmark observation for a device, scenario, or input file."""

    benchmark: str
    subject: str
    metrics: tuple[Metric, ...]
    variables: dict[str, Any] = field(default_factory=dict)
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark": self.benchmark,
            "subject": self.subject,
            "variables": self.variables,
            "metrics": [metric.to_dict() for metric in self.metrics],
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkRun:
    """A reproducible benchmark run with structured records."""

    name: str
    records: tuple[BenchmarkRecord, ...]
    run_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "records": [record.to_dict() for record in self.records],
        }


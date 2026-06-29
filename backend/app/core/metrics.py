"""Prometheus-style metrics collector (lightweight, no dependency).

Exposes counters and histograms as a simple /metrics text endpoint. No prometheus
client library needed — we format the text ourselves.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

_lock = threading.Lock()


@dataclass
class _Counter:
    value: float = 0.0
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class _Histogram:
    buckets: list[float] = field(default_factory=lambda: [0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0])
    _counts: dict[float, int] = field(default_factory=dict, init=False)
    _sum: float = field(default=0.0, init=False)
    _count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        for b in self.buckets:
            self._counts[b] = 0

    def observe(self, value: float) -> None:
        self._sum += value
        self._count += 1
        for b in self.buckets:
            if value <= b:
                self._counts[b] += 1

    def serialize(self, name: str, help_text: str) -> str:
        lines = [f"# HELP {name} {help_text}", f"# TYPE {name} histogram"]
        for b in self.buckets:
            le = f"{b:.3f}" if b < 1 else str(int(b))
            lines.append(f'{name}_bucket{{le="{le}"}} {self._counts[b]}')
        lines.append(f'{name}_bucket{{le="+Inf"}} {self._count}')
        lines.append(f"{name}_count {self._count}")
        lines.append(f"{name}_sum {self._sum:.3f}")
        return "\n".join(lines)


_counters: dict[str, _Counter] = {}
_histograms: dict[str, _Histogram] = {}


def inc_counter(name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
    labels = labels or {}
    key = f"{name}:{','.join(f'{k}={v}' for k, v in sorted(labels.items()))}"
    with _lock:
        if key not in _counters:
            _counters[key] = _Counter(value=0.0, labels=labels)
        _counters[key].value += value


def observe_histogram(name: str, value: float) -> None:
    with _lock:
        if name not in _histograms:
            _histograms[name] = _Histogram()
        _histograms[name].observe(value)


def serialize_metrics() -> str:
    lines: list[str] = []
    with _lock:
        # Counters
        seen_names: set[str] = set()
        for key, c in _counters.items():
            name = key.split(":")[0]
            if name not in seen_names:
                lines.append(f"# HELP {name} counter")
                lines.append(f"# TYPE {name} counter")
                seen_names.add(name)
            lbl = ",".join(f'{k}="{v}"' for k, v in sorted(c.labels.items()))
            suffix = f"{{{lbl}}}" if lbl else ""
            lines.append(f"{name}{suffix} {c.value}")
        # Histograms
        for name, h in _histograms.items():
            lines.append(h.serialize(name, f"histogram {name}"))
    return "\n".join(lines) + "\n"

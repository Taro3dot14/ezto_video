"""Event types for the harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HarnessEvent:
    """Event emitted by the harness during workflow execution."""
    type: str  # node_start, node_end, interrupt, error, completed
    node: str | None = None
    phase: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

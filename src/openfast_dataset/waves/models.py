"""Portable, deterministic SeaState wave dependency descriptions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from openfast_dataset.campaign.provenance import scientific_hash


@dataclass(frozen=True)
class WaveRealization:
    kind: Literal["none", "regular", "irregular", "external"]
    content: dict[str, Any]
    scientific_hash: str

    @property
    def wave_id(self) -> str:
        return f"wave_{self.scientific_hash[:16]}"

    @classmethod
    def create(cls, kind: str, content: dict[str, Any]) -> "WaveRealization":
        normalized = {"kind": kind, **content}
        return cls(kind=kind, content=normalized, scientific_hash=scientific_hash(normalized))

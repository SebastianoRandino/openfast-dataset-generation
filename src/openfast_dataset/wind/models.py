"""Portable wind-realization domain objects; no executable integration lives here."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from openfast_dataset.campaign.provenance import scientific_hash


@dataclass(frozen=True)
class WindRealization:
    """One reusable wind dependency, identified by normalized scientific content."""
    kind: Literal["steady", "turbulent", "external"]
    content: dict[str, Any]
    scientific_hash: str

    @property
    def wind_id(self) -> str:
        return f"wind_{self.scientific_hash[:16]}"

    @property
    def directory(self) -> Path:
        return Path("wind") / self.wind_id

    @classmethod
    def create(cls, kind: str, content: dict[str, Any]) -> WindRealization:
        normalized = {"kind": kind, **content}
        return cls(kind=kind, content=normalized, scientific_hash=scientific_hash(normalized))

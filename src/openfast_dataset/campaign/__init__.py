"""Campaign specifications, deterministic case expansion, and provenance."""

from .models import CampaignSpecification, ResolvedCase, ValidationError
from .resolver import resolve_campaign

__all__ = ["CampaignSpecification", "ResolvedCase", "ValidationError", "resolve_campaign"]

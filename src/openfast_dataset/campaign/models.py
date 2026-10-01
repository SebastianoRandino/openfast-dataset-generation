"""Small, intentionally incomplete domain model for scientific campaigns."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal


class ValidationError(ValueError):
    """Raised when a campaign is scientifically incomplete or inconsistent."""


def required_openfast_version(configuration: dict[str, Any]) -> str | None:
    version = configuration.get("openfast_version")
    known = {"iea15mw-volturnus-openfast-v1": "4.1.1",
             "IEA15MW_VolturnUS_v4.1.1": "4.1.1", "IEA15MW_VolturnUS_v5.0.0": "5.0.0"}
    inferred = known.get(configuration.get("openfast_template_id"))
    if version is not None and (not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version)):
        raise ValidationError("openfast_version must be a version string such as 5.0.0")
    if inferred and version is not None and inferred != version:
        raise ValidationError("OpenFAST template ID conflicts with openfast_version")
    return version or inferred


def _positive(name: str, value: float | None) -> None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be a positive number") from None
    if numeric <= 0:
        raise ValidationError(f"{name} must be positive")


@dataclass(frozen=True)
class TimeScales:
    integration_dt_s: float
    duration_s: float
    output_dt_s: float | None = None
    actuator_dt_s: float | None = None
    wind_dt_s: float | None = None
    wave_dt_s: float | None = None
    discard_transient_s: float | None = None

    def validate(self) -> None:
        _positive("numerics.integration_dt_s", self.integration_dt_s)
        _positive("numerics.duration_s", self.duration_s)
        for key in ("output_dt_s", "actuator_dt_s", "wind_dt_s", "wave_dt_s"):
            value = getattr(self, key)
            if value is not None:
                _positive(f"numerics.{key}", value)
        if self.discard_transient_s is not None:
            if self.discard_transient_s < 0 or self.discard_transient_s >= self.duration_s:
                raise ValidationError("numerics.discard_transient_s must be >= 0 and less than duration_s")


@dataclass(frozen=True)
class Platform:
    kind: Literal["floating", "fixed"]
    hydrodynamics_template: str | None = None
    mooring_template: str | None = None
    initial_conditions: dict[str, float] = field(default_factory=dict)

    def validate(self) -> None:
        if self.kind not in {"floating", "fixed"}:
            raise ValidationError("platform.kind must be 'floating' or 'fixed'")


@dataclass(frozen=True)
class Wind:
    kind: Literal["steady", "turbulent", "external"]
    speed_mps: float | None = None
    reference_height_m: float | None = None
    direction_deg: float | None = None
    shear_exponent: float | None = None
    spectral_model: str | None = None
    iec_wind_type: str | None = None
    iec_turbulence_class: str | None = None
    seed_index: int | None = None
    seed: int | None = None
    bts_path: str | None = None
    generation_duration_s: float | None = None
    usable_duration_s: float | str | None = None
    template_id: str | None = None
    grid: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    turbsim: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.kind not in {"steady", "turbulent", "external"}:
            raise ValidationError("wind.kind must be steady, turbulent, or external")
        if not isinstance(self.metadata, dict):
            raise ValidationError("wind.metadata must be a mapping")
        if not isinstance(self.turbsim, dict):
            raise ValidationError("wind.turbsim must be a mapping")
        overrides = self.turbsim.get("overrides", {})
        if not isinstance(overrides, dict):
            raise ValidationError("wind.turbsim.overrides must be a mapping")
        if self.kind in {"steady", "turbulent"}:
            _positive("wind.speed_mps", self.speed_mps)
        if self.kind == "turbulent":
            if not self.spectral_model:
                raise ValidationError("turbulent wind requires wind.spectral_model")
            if not self.iec_wind_type:
                raise ValidationError("turbulent wind requires wind.iec_wind_type")
            if not self.iec_turbulence_class:
                raise ValidationError("turbulent wind requires wind.iec_turbulence_class")
            if self.seed_index is None and self.seed is None:
                raise ValidationError("turbulent wind requires wind.seed_index or wind.seed")
            if self.generation_duration_s is not None:
                _positive("wind.generation_duration_s", self.generation_duration_s)
            if self.usable_duration_s is not None and self.usable_duration_s != "ALL":
                _positive("wind.usable_duration_s", self.usable_duration_s)
            if not isinstance(self.metadata, dict):
                raise ValidationError("wind.metadata must be a mapping")
            if not isinstance(self.turbsim, dict):
                raise ValidationError("wind.turbsim must be a mapping")
            overrides = self.turbsim.get("overrides", {})
            if not isinstance(overrides, dict):
                raise ValidationError("wind.turbsim.overrides must be a mapping")
        if self.kind == "external" and not self.bts_path:
            raise ValidationError("external wind requires wind.bts_path")


@dataclass(frozen=True)
class Waves:
    kind: Literal["none", "regular", "irregular", "external"] = "none"
    wave_height_m: float | None = None
    period_s: float | None = None
    significant_height_m: float | None = None
    peak_period_s: float | None = None
    spectrum: str | None = None
    direction_deg: float | None = None
    seed: int | None = None
    seed_index: int | None = None
    seed_2: int | str | None = None
    peak_shape: float | str | None = "DEFAULT"
    external_reference: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.kind not in {"none", "regular", "irregular", "external"}:
            raise ValidationError("waves.kind must be none, regular, irregular, or external")
        if self.kind == "regular":
            _positive("waves.wave_height_m", self.wave_height_m)
            _positive("waves.period_s", self.period_s)
            if self.significant_height_m is not None or self.peak_period_s is not None:
                raise ValidationError("regular waves must not define significant_height_m or peak_period_s")
        if self.kind == "irregular":
            _positive("waves.significant_height_m", self.significant_height_m)
            _positive("waves.peak_period_s", self.peak_period_s)
        if self.kind == "irregular" and not self.spectrum:
            raise ValidationError("irregular waves require waves.spectrum")
        if self.kind == "irregular" and self.wave_height_m is not None:
            raise ValidationError("irregular waves must not define wave_height_m")
        if self.kind == "irregular" and self.seed is None and self.seed_index is None:
            raise ValidationError("irregular waves require waves.seed or waves.seed_index")
        if self.seed_index is not None and (not isinstance(self.seed_index, int) or self.seed_index < 0):
            raise ValidationError("waves.seed_index must be a non-negative integer")
        if self.kind == "none" and any(value is not None for value in (self.wave_height_m, self.period_s, self.significant_height_m, self.peak_period_s)):
            raise ValidationError("waves.kind none must not define wave heights or periods")
        if self.direction_deg is not None and not -180 <= self.direction_deg <= 180:
            raise ValidationError("waves.direction_deg must be between -180 and 180 degrees")
        if self.kind == "external" and not self.external_reference:
            raise ValidationError("external waves require waves.external_reference")


@dataclass(frozen=True)
class Controller:
    kind: Literal["template"] = "template"

    def validate(self) -> None:
        if self.kind != "template":
            raise ValidationError("controller.kind must be template")


@dataclass(frozen=True)
class Actuation:
    enabled: bool = False
    delay_s: float | None = None
    rate_limit: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    model: str | None = None

    def validate(self) -> None:
        if self.enabled:
            raise ValidationError("active actuation is not supported yet")
        if self.delay_s is not None and self.delay_s < 0:
            raise ValidationError("actuation.delay_s must be >= 0")
        if self.rate_limit is not None:
            _positive("actuation.rate_limit", self.rate_limit)
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValidationError("actuation.minimum must not exceed actuation.maximum")


@dataclass(frozen=True)
class ResolvedCase:
    case_id: str
    split: str | None
    scientific: dict[str, Any]
    provenance: dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> dict[str, Any]:
        return {"case_id": self.case_id, "split": self.split, "scientific": self.scientific}


@dataclass(frozen=True)
class CampaignSpecification:
    name: str
    model: str
    turbine: dict[str, Any]
    platform: Platform
    numerics: TimeScales
    wind: Wind
    waves: Waves
    controller: Controller
    actuation: Actuation
    openfast_template_id: str | None = None
    openfast_primary_fst: str | None = None
    openfast_version: str | None = None
    modules: dict[str, bool] = field(default_factory=dict)
    overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    sweeps: list[dict[str, Any]] = field(default_factory=list)
    case_groups: list[dict[str, Any]] = field(default_factory=list)
    cases: list[dict[str, Any]] = field(default_factory=list)
    splits: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.name:
            raise ValidationError("campaign.name is required")
        if not self.model:
            raise ValidationError("campaign.model is required")
        required_openfast_version({"openfast_template_id": self.openfast_template_id, "openfast_version": self.openfast_version})
        self.platform.validate(); self.numerics.validate(); self.wind.validate(); self.waves.validate()
        self.controller.validate(); self.actuation.validate()
        unknown = set(self.splits) - {"train", "validation", "test"}
        if unknown:
            raise ValidationError(f"unsupported split names: {sorted(unknown)}")

    def base_scientific(self) -> dict[str, Any]:
        configuration = {"openfast_template_id": self.openfast_template_id, "openfast_primary_fst": self.openfast_primary_fst}
        if self.openfast_version is not None:
            configuration["openfast_version"] = self.openfast_version
        return {
            "model": self.model, "model_configuration": configuration, "turbine": self.turbine, "platform": asdict(self.platform),
            "numerics": asdict(self.numerics), "wind": asdict(self.wind), "waves": asdict(self.waves),
            "controller": asdict(self.controller), "actuation": asdict(self.actuation),
            "modules": self.modules, "overrides": self.overrides,
        }


def validate_resolved_scientific(scientific: dict[str, Any]) -> None:
    """Validate one fully-expanded case using the same typed domain model."""
    try:
        required_openfast_version(scientific.get("model_configuration", {}))
        Platform(**scientific["platform"]).validate()
        TimeScales(**scientific["numerics"]).validate()
        Wind(**scientific["wind"]).validate()
        Waves(**scientific["waves"]).validate()
        Controller(**scientific["controller"]).validate()
        Actuation(**scientific["actuation"]).validate()
    except KeyError as error:
        raise ValidationError(f"resolved case is missing {error.args[0]!r}") from error
    except TypeError as error:
        raise ValidationError(f"resolved case has an unsupported structured field: {error}") from error

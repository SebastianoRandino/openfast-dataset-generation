"""Small, intentionally incomplete domain model for scientific campaigns."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


class ValidationError(ValueError):
    """Raised when a campaign is scientifically incomplete or inconsistent."""


def _positive(name: str, value: float | None) -> None:
    if value is None or value <= 0:
        raise ValidationError(f"{name} must be positive")


@dataclass(frozen=True)
class TimeScales:
    integration_dt_s: float
    duration_s: float
    output_dt_s: float | None = None
    controller_dt_s: float | None = None
    actuator_dt_s: float | None = None
    wind_dt_s: float | None = None
    wave_dt_s: float | None = None
    discard_transient_s: float | None = None

    def validate(self) -> None:
        _positive("numerics.integration_dt_s", self.integration_dt_s)
        _positive("numerics.duration_s", self.duration_s)
        for key in ("output_dt_s", "controller_dt_s", "actuator_dt_s", "wind_dt_s", "wave_dt_s"):
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
        if self.kind == "fixed" and (self.hydrodynamics_template or self.mooring_template):
            raise ValidationError("platform hydrodynamics_template/mooring_template apply only to floating platforms")


@dataclass(frozen=True)
class Wind:
    kind: Literal["steady", "turbulent", "external"]
    speed_mps: float | None = None
    reference_height_m: float | None = None
    direction_deg: float | None = None
    shear_exponent: float | None = None
    turbulence_model: str | None = None
    turbulence_class: str | None = None
    seed_index: int | None = None
    seed: int | None = None
    bts_path: str | None = None
    grid: dict[str, Any] = field(default_factory=dict)
    overrides: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.kind not in {"steady", "turbulent", "external"}:
            raise ValidationError("wind.kind must be steady, turbulent, or external")
        if self.kind in {"steady", "turbulent"}:
            _positive("wind.speed_mps", self.speed_mps)
        if self.kind == "turbulent":
            if not self.turbulence_model:
                raise ValidationError("turbulent wind requires wind.turbulence_model")
            if self.seed_index is None and self.seed is None:
                raise ValidationError("turbulent wind requires wind.seed_index or wind.seed")
        if self.kind == "external" and not self.bts_path:
            raise ValidationError("external wind requires wind.bts_path")


@dataclass(frozen=True)
class Waves:
    kind: Literal["none", "regular", "irregular", "external"] = "none"
    significant_height_m: float | None = None
    peak_period_s: float | None = None
    spectrum: str | None = None
    direction_deg: float | None = None
    seed: int | None = None
    external_reference: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.kind not in {"none", "regular", "irregular", "external"}:
            raise ValidationError("waves.kind must be none, regular, irregular, or external")
        if self.kind in {"regular", "irregular"}:
            _positive("waves.significant_height_m", self.significant_height_m)
            _positive("waves.peak_period_s", self.peak_period_s)
        if self.kind == "irregular" and not self.spectrum:
            raise ValidationError("irregular waves require waves.spectrum")
        if self.kind == "external" and not self.external_reference:
            raise ValidationError("external waves require waves.external_reference")


@dataclass(frozen=True)
class Controller:
    kind: Literal["none", "rosco", "custom"] = "none"
    template: str | None = None
    omega_pc: float | None = None
    zeta_pc: float | None = None
    overrides: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.kind not in {"none", "rosco", "custom"}:
            raise ValidationError("controller.kind must be none, rosco, or custom")
        if self.kind == "rosco" and not self.template:
            raise ValidationError("ROSCO controller requires controller.template")
        if self.omega_pc is not None:
            _positive("controller.omega_pc", self.omega_pc)
        if self.zeta_pc is not None:
            _positive("controller.zeta_pc", self.zeta_pc)


@dataclass(frozen=True)
class Actuation:
    enabled: bool = False
    update_dt_s: float | None = None
    delay_s: float | None = None
    rate_limit: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    model: str | None = None

    def validate(self) -> None:
        if self.enabled and self.update_dt_s is None:
            raise ValidationError("enabled actuation requires actuation.update_dt_s")
        if self.update_dt_s is not None:
            _positive("actuation.update_dt_s", self.update_dt_s)
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
        self.platform.validate(); self.numerics.validate(); self.wind.validate(); self.waves.validate()
        self.controller.validate(); self.actuation.validate()
        if self.waves.kind != "none" and self.platform.kind != "floating":
            raise ValidationError("waves require platform.kind: floating")
        unknown = set(self.splits) - {"train", "validation", "test"}
        if unknown:
            raise ValidationError(f"unsupported split names: {sorted(unknown)}")

    def base_scientific(self) -> dict[str, Any]:
        return {
            "model": self.model, "turbine": self.turbine, "platform": asdict(self.platform),
            "numerics": asdict(self.numerics), "wind": asdict(self.wind), "waves": asdict(self.waves),
            "controller": asdict(self.controller), "actuation": asdict(self.actuation),
            "modules": self.modules, "overrides": self.overrides,
        }

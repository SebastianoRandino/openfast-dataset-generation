"""Read-only ED/BD comparison; run from any cwd with the project virtual environment."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW = ROOT / "outputs/structural-comparison-v5-production-dt001"
HERE = Path(__file__).resolve().parent
START = 100.0
FS = 100.0
NSEG = 8192
UNITS = {
    "GenPwr": "kW",
    "GenTq": "kN-m",
    "RotSpeed": "rpm",
    "GenSpeed": "rpm",
    **{f"BldPitch{i}": "deg" for i in range(1, 4)},
    "RtAeroFxh": "N",
    "RtAeroMxh": "N-m",
    **{f"Ptfm{x}": "m" for x in ("Surge", "Sway", "Heave")},
    **{f"Ptfm{x}": "deg" for x in ("Roll", "Pitch", "Yaw")},
    "TTDspFA": "m",
    "TTDspSS": "m",
    **{f"YawBrF{x}p": "kN" for x in "xyz"},
    **{f"YawBrM{x}p": "kN-m" for x in "xyz"},
}
SELECTED = [
    "RotSpeed",
    "GenPwr",
    "RtAeroFxh",
    "RtAeroMxh",
    "PtfmSurge",
    "PtfmPitch",
    "TipDxb1",
    "RootMyb1",
]


def channel_map():
    rows = [
        {
            "channel": k,
            "ed": k,
            "bd": k,
            "ed_unit": u,
            "bd_unit": u,
            "unit": u,
            "ed_factor": 1.0,
            "bd_factor": 1.0,
            "basis": "same module and output definition",
        }
        for k, u in UNITS.items()
    ]
    for blade in range(1, 4):
        for ed, bd, source, target, factor in [
            ("TipDxb", "TipTDxr", "m", "m", 1.0),
            ("TipDyb", "TipTDyr", "m", "m", 1.0),
            ("RootFxb", "RootFxr", "N", "kN", 0.001),
            ("RootFyb", "RootFyr", "N", "kN", 0.001),
            ("RootMxb", "RootMxr", "N-m", "kN-m", 0.001),
            ("RootMyb", "RootMyr", "N-m", "kN-m", 0.001),
        ]:
            rows.append(
                {
                    "channel": f"{ed}{blade}",
                    "ed": f"{ed}{blade}",
                    "bd": f"B{blade}{bd}",
                    "ed_unit": target,
                    "bd_unit": source,
                    "unit": target,
                    "ed_factor": 1.0,
                    "bd_factor": factor,
                    "basis": "pitched root axes; see channel_mapping.md",
                }
            )
    return rows


def read_outb(path):
    """Decode NWTC binary IDs 1-4, retaining duplicate invalid header entries."""
    with Path(path).open("rb") as f:

        def unpack(fmt):
            size = struct.calcsize(fmt)
            data = f.read(size)
            if len(data) != size:
                raise ValueError("Truncated OUTB header")
            return struct.unpack(fmt, data)

        (fid,) = unpack("<h")
        if fid not in (1, 2, 3, 4):
            raise ValueError(f"Unsupported OUTB ID {fid}")
        length = unpack("<h")[0] if fid == 4 else 10
        nc, nt = unpack("<ii")
        t0, dt = unpack("<dd")
        scale = np.frombuffer(f.read(nc * 4), dtype="<f4") if fid != 3 else None
        offset = np.frombuffer(f.read(nc * 4), dtype="<f4") if fid != 3 else None
        (nd,) = unpack("<i")
        description = f.read(nd).decode("utf-8", errors="replace")
        names = [f.read(length).decode().strip() for _ in range(nc + 1)]
        units = [f.read(length).decode().strip().strip("()") for _ in range(nc + 1)]
        if fid == 1:
            packed_time = np.frombuffer(f.read(nt * 4), dtype="<i4")
            time = (packed_time.astype(float) - dt) / t0
        else:
            time = t0 + dt * np.arange(nt)
        dtype = "<f8" if fid == 3 else "<i2"
        payload = f.read()
        if len(payload) != nt * nc * np.dtype(dtype).itemsize:
            raise ValueError("Incomplete or trailing OUTB payload")
        values = np.frombuffer(payload, dtype=dtype).reshape(nt, nc).astype(float)
        if fid != 3:
            if not np.all(np.isfinite(scale)) or np.any(scale == 0):
                raise ValueError("Invalid compression scale")
            values = (values - offset) / scale
    return time, names, units, values, description


def extract(record, name, expected_unit, factor):
    _, names, units, values, _ = record
    if names.count(name) != 1:
        raise ValueError(f"Missing or ambiguous channel {name}")
    idx = names.index(name)
    if units[idx] != expected_unit:
        raise ValueError(f"{name}: expected {expected_unit}, got {units[idx]}")
    result = values[:, idx - 1] * factor
    if not np.all(np.isfinite(result)):
        raise ValueError(f"Nonfinite data: {name}")
    return result


def statistics(x):
    return {
        "mean": float(np.mean(x)),
        "std": float(np.std(x, ddof=0)),
        "rms": float(np.sqrt(np.mean(x * x))),
        "minimum": float(np.min(x)),
        "maximum": float(np.max(x)),
        "peak_to_peak": float(np.ptp(x)),
    }


def relative_difference(bd, ed, threshold):
    return 100 * (bd - ed) / abs(ed) if abs(ed) > threshold else np.nan


def compare(ed, bd):
    a, b = statistics(ed), statistics(bd)
    # A mean below 10% of reference RMS is fluctuation-dominated; suppress its ratio.
    threshold = max(1e-9, 0.10 * a["rms"])
    row = {**{f"ed_{k}": v for k, v in a.items()}, **{f"bd_{k}": v for k, v in b.items()}}
    row.update(
        mean_difference=b["mean"] - a["mean"],
        absolute_mean_difference=abs(b["mean"] - a["mean"]),
        mean_reference_threshold=threshold,
        relative_mean_difference_pct=relative_difference(b["mean"], a["mean"], threshold),
        relative_std_difference_pct=relative_difference(b["std"], a["std"], 1e-9),
        relative_rms_difference_pct=relative_difference(b["rms"], a["rms"], 1e-9),
        std_difference=b["std"] - a["std"],
        rms_difference=b["rms"] - a["rms"],
    )
    return row


def welch(x, fs=FS, nperseg=NSEG):
    """One-sided density, periodic Hann, segment mean removal, 50% overlap."""
    if len(x) < nperseg:
        raise ValueError("Too few samples for specified Welch segments")
    window = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(nperseg) / nperseg)
    segments = np.lib.stride_tricks.sliding_window_view(x, nperseg)[:: nperseg // 2]
    transform = np.fft.rfft((segments - segments.mean(axis=1, keepdims=True)) * window)
    power = np.mean(abs(transform) ** 2, axis=0) / (fs * np.sum(window**2))
    power[1:-1] *= 2
    return np.fft.rfftfreq(nperseg, 1 / fs), power


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(raw):
    return {str(p.relative_to(raw)): sha(p) for p in sorted(raw.rglob("*")) if p.is_file()}


def markdown_table(frame, columns):
    labels = "| " + " | ".join(columns) + " |"
    lines = [labels, "|" + "---|" * len(columns)]
    for _, row in frame.iterrows():
        cells = [
            f"{row[c]:.5g}"
            if isinstance(row[c], (float, np.floating)) and np.isfinite(row[c])
            else ("n/a" if pd.isna(row[c]) else str(row[c]))
            for c in columns
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def run(raw=DEFAULT_RAW, out=HERE):
    raw, out = Path(raw), Path(out)
    if out.resolve().is_relative_to(raw.resolve()):
        raise ValueError("Analysis output must be outside production directory")
    out.mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(exist_ok=True)
    provenance = json.loads(
        (ROOT / "docs/structural_comparison_production_provenance.json").read_text()
    )
    before = snapshot(raw)
    mapping = channel_map()
    records, inventory, validation = {}, [], []
    for case in provenance["runs"]:
        paths = list((raw / "cases" / case["prepared_case"]).rglob("*.outb"))
        if len(paths) != 1:
            raise ValueError(f"Expected exactly one OUTB for {case['case']}")
        p = paths[0]
        if sha(p) != case["outb_sha256"]:
            raise ValueError(f"Production checksum mismatch: {case['case']}")
        record = read_outb(p)
        t, names, units, _, _ = record
        if len(t) != 40001 or t[0] != 0 or t[-1] != 400:
            raise ValueError("Unexpected sample count or duration")
        if not np.allclose(np.diff(t), 0.01, rtol=0, atol=1e-12):
            raise ValueError("Unexpected time step")
        records[case["case"]] = record
        inventory.extend(
            {"case": case["case"], "index": i, "channel": n, "unit": u}
            for i, (n, u) in enumerate(zip(names, units))
        )
        validation.append(
            {
                "case": case["case"],
                "samples": len(t),
                "analyzed_samples": int((t >= START).sum()),
                "first_time": float(t[0]),
                "last_time": float(t[-1]),
                "sha256": case["outb_sha256"],
                "provenance_hash_matches": True,
            }
        )
    rows, psd_rows, peaks, runtimes = [], [], [], []
    for lc in ("LC1", "LC2", "LC3"):
        ed, bd = records[f"{lc}_ED"], records[f"{lc}_BD"]
        if not np.array_equal(ed[0], bd[0]):
            raise ValueError(f"Time vectors differ in {lc}")
        mask = ed[0] >= START
        t = ed[0][mask]
        series = {}
        for m in mapping:
            a = extract(ed, m["ed"], m["ed_unit"], m["ed_factor"])[mask]
            b = extract(bd, m["bd"], m["bd_unit"], m["bd_factor"])[mask]
            rows.append(dict(lc=lc, channel=m["channel"], unit=m["unit"], **compare(a, b)))
            series[m["channel"]] = (a, b)
        fig_t, axes_t = plt.subplots(4, 2, figsize=(13, 12), constrained_layout=True)
        fig_f, axes_f = plt.subplots(4, 2, figsize=(13, 12), constrained_layout=True)
        for channel, ax_t, ax_f in zip(SELECTED, axes_t.flat, axes_f.flat):
            a, b = series[channel]
            unit = next(m["unit"] for m in mapping if m["channel"] == channel)
            display_factor = 0.001 if channel in ("GenPwr", "RtAeroFxh", "RtAeroMxh") else 1
            display_unit = {"GenPwr": "MW", "RtAeroFxh": "kN", "RtAeroMxh": "kN-m"}.get(
                channel, unit
            )
            f, pa = welch(a)
            _, pb = welch(b)
            for model, x, pwr in (("ED", a, pa), ("BD", b, pb)):
                ax_t.plot(t, x * display_factor, label=model, linewidth=0.7, alpha=0.85)
                ax_f.loglog(f[1:], pwr[1:] * display_factor**2, label=model, linewidth=1)
            ax_t.set(xlabel="Time [s]", ylabel=f"{channel} [{display_unit}]")
            ax_f.set(xlabel="Frequency [Hz]", ylabel=f"{channel} [{display_unit}²/Hz]")
            ax_f.set_xlim(f[1], FS / 2)
            for ax in (ax_t, ax_f):
                ax.grid(True, alpha=0.25)
                ax.legend(fontsize=8)
            psd_rows.extend(
                {
                    "lc": lc,
                    "channel": channel,
                    "unit": f"{unit}^2/Hz",
                    "frequency_hz": float(freq),
                    "ed_psd": float(p),
                    "bd_psd": float(q),
                }
                for freq, p, q in zip(f, pa, pb)
            )
            band = (f > 0) & (f <= 2)
            ia, ib = np.where(band)[0][np.argmax(pa[band])], np.where(band)[0][np.argmax(pb[band])]
            integral_a, integral_b = np.sum(pa[band]) * (FS / NSEG), np.sum(pb[band]) * (FS / NSEG)
            peaks.append(
                {
                    "lc": lc,
                    "channel": channel,
                    "ed_peak_hz": f[ia],
                    "bd_peak_hz": f[ib],
                    "ed_peak_density": pa[ia],
                    "bd_peak_density": pb[ib],
                    "band": "0<f<=2 Hz",
                    "ed_band_power": integral_a,
                    "bd_band_power": integral_b,
                    "band_power_difference_pct": relative_difference(integral_b, integral_a, 1e-18),
                }
            )
        fig_t.suptitle(f"{lc}: ED vs BeamDyn, 100–400 s")
        fig_f.suptitle(f"{lc}: Welch PSD, 100–400 s")
        fig_t.savefig(out / "figures" / f"{lc}_time.png", dpi=140)
        fig_f.savefig(out / "figures" / f"{lc}_psd.png", dpi=140)
        plt.close(fig_t)
        plt.close(fig_f)
        runs = {r["case"]: r for r in provenance["runs"]}
        ae, ab = runs[f"{lc}_ED"]["wall_clock_s"], runs[f"{lc}_BD"]["wall_clock_s"]
        runtimes.append({"lc": lc, "ed_wall_s": ae, "bd_wall_s": ab, "bd_over_ed": ab / ae})
    stats = pd.DataFrame(rows)
    peak_df, runtime_df = pd.DataFrame(peaks), pd.DataFrame(runtimes)
    for name, frame in (
        ("statistics", stats),
        ("channel_map", pd.DataFrame(mapping)),
        ("channel_inventory", pd.DataFrame(inventory)),
        ("psd", pd.DataFrame(psd_rows)),
        ("spectral_summary", peak_df),
        ("runtime", runtime_df),
    ):
        suffix = ".csv.gz" if name == "psd" else ".csv"
        compression = {"method": "gzip", "mtime": 0} if name == "psd" else None
        frame.to_csv(
            out / f"{name}{suffix}", index=False, float_format="%.12g", compression=compression
        )
    columns = [
        "channel",
        "unit",
        "ed_mean",
        "bd_mean",
        "relative_mean_difference_pct",
        "ed_std",
        "bd_std",
        "relative_std_difference_pct",
    ]
    main = stats[stats.channel.isin(SELECTED)]
    ranked = stats.assign(rank=stats.relative_std_difference_pct.abs()).sort_values(
        "rank", ascending=False
    )
    ranked.drop(columns="rank").to_csv(out / "cross_condition_summary.csv", index=False)
    report = [
        "# ED–BeamDyn structural comparison: first post-processing stage",
        "",
        (
            "Source: the six completed v5 production runs mapped by `docs/structural_comparison_production_provenance.json`. "
            "This is a descriptive response comparison, not validation against measurements or a final identification dataset."
        ),
        "",
        "## Numerical completion and analysis validation",
        "",
        (
            "All six production runs reached 400 s with return code 0, zero tight-coupling failures, "
            "zero invalid-solution warnings and no fatal errors, per production provenance. "
            "Re-read OUTBs have 40001 samples from 0 to 400 s; each ED/BD time vector is exactly identical "
            "at 0.01 s spacing. Only t >= 100 s is selected (30001 samples). "
            "All matched full-length channels are finite; header units are asserted before conversion. "
            "Checksums match production provenance. All production files are hashed before and after processing."
        ),
        "",
        "## Physical response differences",
        "",
        (
            "41 physically matched channels are listed in `channel_map.csv`; all native channels and units "
            "are in `channel_inventory.csv`. See `channel_mapping.md` for blade frame, origin, sign and unit checks. "
            "Statistics use population standard deviation (ddof=0). RMS includes the mean. "
            "Differences are BD minus ED; relative percentages divide by |ED|. Mean ratios are suppressed "
            "when |ED mean| <= max(1e-9 engineering units, 10% ED RMS); CSV blanks and n/a denote suppression. "
            "Absolute mean differences remain available. Std/RMS ratios are suppressed for references <=1e-9. "
            "Large percentage changes in small-amplitude channels must be read alongside absolute values."
        ),
    ]
    for lc in ("LC1", "LC2", "LC3"):
        sub = main[main.lc == lc]
        sub[columns].to_csv(out / f"{lc}_summary.csv", index=False, float_format="%.12g")
        report.extend(
            [
                "",
                f"### {lc}",
                "",
                markdown_table(sub, columns),
                "",
                f"![Time overlays](figures/{lc}_time.png)",
            ]
        )
    report.extend(
        [
            "",
            "### Largest cross-condition standard-deviation changes",
            "",
            markdown_table(
                ranked.head(10),
                [
                    "lc",
                    "channel",
                    "unit",
                    "ed_std",
                    "bd_std",
                    "relative_std_difference_pct",
                    "absolute_mean_difference",
                ],
            ),
            "",
            "### Largest mean changes with meaningful ED references",
            "",
            markdown_table(
                stats.loc[stats.relative_mean_difference_pct.abs().nlargest(8).index],
                [
                    "lc",
                    "channel",
                    "unit",
                    "ed_mean",
                    "bd_mean",
                    "absolute_mean_difference",
                    "relative_mean_difference_pct",
                ],
            ),
            "",
            (
                "LC1 shows the largest mean changes among the priority channels: generator power "
                "falls 7.51%, aerodynamic thrust 14.17%, and platform pitch from 0.318 to 0.0849 deg "
                "(an absolute change of 0.233 deg). LC2 thrust and blade-1 flapwise root moment means "
                "fall 7.58% and 9.79%; platform-pitch std falls 18.71%. LC3 priority-channel means "
                "are closer, while platform-pitch std falls 23.14% and blade-1 tip-x std rises 11.20%. "
                "The largest std increase across all matches is LC3 YawBrFzp (+37.93%); the largest "
                "reduction is LC2 collective blade pitch (-33.10%). Small-reference edgewise mean "
                "ratios are suppressed; their absolute changes remain in statistics.csv."
            ),
            "",
            "## Spectral description",
            "",
            (
                "Descriptively, 0<f<=2 Hz band power is lower in BD for LC2 thrust (-42.07%), "
                "platform pitch (-39.95%) and surge (-31.95%). Blade-1 tip-x band power rises "
                "45.64% in LC1 and 40.76% in LC3. LC3 aerodynamic-torque band power rises 42.51%, "
                "and its maximum bin changes from 0.0244 Hz (ED) to 0.1221 Hz (BD). LC1 blade-tip "
                "and root-flapwise maxima share 0.08545 Hz; LC3 shares 0.1221 Hz. Many other "
                "maxima sit at the first resolved bin (0.01221 Hz), indicating dominant low-frequency "
                "content with limited resolution. These are finite-window descriptions, without "
                "attributing peaks to structural modes. Band-power changes need not equal full-window "
                "variance changes because Welch detrends each segment and weights its samples."
            ),
            "",
            (
                "Sampling frequency 100 Hz; Welch one-sided density, periodic Hann window; 8192 samples "
                "(81.92 s) per segment, 4096 samples (50%) overlap, six complete segments, constant "
                "detrending per segment, arithmetic averaging, no zero padding. Frequency resolution "
                "100/8192 = 0.01220703125 Hz; Nyquist 50 Hz. Identical parameters are applied to ED and BD. "
                "The unused final 1329 samples are retained in time statistics; Welch uses complete segments. "
                "Full 0–50 Hz spectra are saved in `psd.csv.gz`. The table describes the maximum PSD bin "
                "and integrated power within 0<f<=2 Hz, not mode identification or a claim about narrow peaks."
            ),
            "",
            markdown_table(
                peak_df, ["lc", "channel", "ed_peak_hz", "bd_peak_hz", "band_power_difference_pct"]
            ),
        ]
    )
    for lc in ("LC1", "LC2", "LC3"):
        report.extend(["", f"![PSD overlays {lc}](figures/{lc}_psd.png)"])
    report.extend(
        [
            "",
            "## Remaining AeroDyn / ROSCO validity warnings",
            "",
            (
                "Numerical completion does not establish physical validity. Recorded axial-induction "
                "and UA-disabled warnings occur in all runs; Mach warnings occur in all except LC1_ED. "
                "BD has Bladed-interface warnings in all three conditions. LC1 ED and BD each record "
                "two ROSCO estimator warnings with fallback to filtered hub-height wind speed. "
                "Warning repeat suppression does not show recovery. BD close-node mesh mapping notices "
                "occur at initialization; missing MoorDyn object IDs and skipped AeroDyn nodal channels "
                "are initialization notices. Invalid MoorDyn outputs are excluded. "
                "See the authoritative production execution report for counts; this stage changes no configuration."
            ),
            "",
            "## Computational cost",
            "",
            "Recorded solver subprocess wall times, separate from response differences:",
            "",
            markdown_table(runtime_df, ["lc", "ed_wall_s", "bd_wall_s", "bd_over_ed"]),
            "",
            "## Reproduction",
            "",
            "From the repository root:",
            "",
            "```sh",
            ".venv/bin/python analysis/structural_comparison/analyze.py",
            "```",
            "",
            (
                "Requires the existing project dependencies (NumPy, pandas, matplotlib); no solver is invoked. "
                "Optional `--raw-dir` and `--output-dir` arguments support relocated inputs and results. "
                "Only analysis products are written. Raw 0–400 s outputs, logs, inputs and campaign files "
                "are preserved; no final identification dataset is created."
            ),
        ]
    )
    after = snapshot(raw)
    if before != after:
        raise ValueError("Production artifacts changed during analysis")
    check = {
        "runs": validation,
        "pairwise_time_identical": True,
        "finite_matched_channels": True,
        "analyzed_start_s": START,
        "analyzed_end_s": 400,
        "matched_channels": len(mapping),
        "production_files_unchanged": True,
        "production_file_count": len(before),
        "production_sha256": before,
        "psd": {
            "fs_hz": FS,
            "nperseg": NSEG,
            "overlap": 4096,
            "resolution_hz": FS / NSEG,
            "window": "periodic Hann",
            "detrend": "segment mean",
            "segments": 6,
        },
        "versions": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "matplotlib": matplotlib.__version__,
        },
    }
    (out / "validation.json").write_text(json.dumps(check, indent=2) + "\n")
    (out / "report.md").write_text("\n".join(report) + "\n")
    print(
        f"Validated {len(records)} OUTBs, {len(mapping)} matched channels, {len(before)} unchanged production files"
    )
    print(runtime_df.to_string(index=False))
    print(ranked.head(10)[["lc", "channel", "relative_std_difference_pct"]].to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--output-dir", type=Path, default=HERE)
    args = parser.parse_args()
    run(args.raw_dir, args.output_dir)

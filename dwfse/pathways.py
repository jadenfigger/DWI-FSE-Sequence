"""Exact, bounded echo-pathway decomposition for MRzero sequences.

This module intentionally does not use ``PyDistribution.prepass_mag`` or
``emitted_signal``.  Those values are graph-construction heuristics.  Instead,
it enumerates every RF branch and applies the same RF, relaxation, diffusion,
dephasing, off-resonance, gradient, and ADC-phase equations as MRzeroCore's
``execute_graph`` at the selected ADC sample.

The implementation is deliberately narrow: one stationary voxel, one selected
receive coil, an instantaneous-RF MRzero sequence, and at most eight ADC-bearing
echoes.  At that size the unpruned enumeration is finite and inexpensive.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from math import pi
import os
from typing import Iterable

import numpy as np
import torch


SQRT2 = 1.41421356237
INV_SQRT2 = 0.70710678118


@dataclass(frozen=True)
class PathwayContribution:
    """One history's coherent contribution to one ADC sample."""

    history: tuple[str, ...]
    value: complex

    @property
    def label(self) -> str:
        return " ".join(self.history)


@dataclass(frozen=True)
class EchoPathwayMetrics:
    """Quantitative pathway metrics at the center sample of an ADC window."""

    echo: int
    repetition: int
    adc_event: int
    time_s: float
    primary_history: tuple[str, ...]
    contributions: tuple[PathwayContribution, ...]
    primary: complex
    other: complex
    total: complex
    l1_amplitude: float
    primary_l1_fraction: float
    other_l1_fraction: float
    primary_coherent_ratio: float
    other_coherent_ratio: float
    other_relative_phase_deg: float
    cancellation_ratio: float
    mrzero_signal: complex | None = None
    closure_relative_error: float | None = None


@dataclass
class _Path:
    kind: str                         # "p" (canonical +) or "z"
    mag: complex
    kt: np.ndarray                    # [kx, ky, kz, tau]
    parity: int                       # Hennig transverse sign, +1 or -1
    history: tuple[str, ...]
    equilibrium: bool                 # unencoded equilibrium/recovery lineage


def _scalar(value, name: str) -> float:
    tensor = torch.as_tensor(value).detach().cpu().reshape(-1)
    if tensor.numel() != 1:
        raise ValueError(f"{name} must contain exactly one voxel value")
    return float(tensor[0])


def _complex_scalar(value, name: str) -> complex:
    tensor = torch.as_tensor(value).detach().cpu().reshape(-1)
    if tensor.numel() != 1:
        raise ValueError(f"{name} must contain exactly one selected value")
    return complex(tensor[0])


def _validate(seq, data, coil: int, max_echo_train_length: int) -> None:
    if int(torch.as_tensor(data.PD).numel()) != 1:
        raise ValueError("exact pathway enumeration currently requires one voxel")
    if data.voxel_motion is not None or data.phantom_motion is not None:
        raise ValueError("motion is not supported by exact pathway enumeration")
    coil_count = int(torch.as_tensor(data.coil_sens).shape[0])
    if not 0 <= coil < coil_count:
        raise ValueError(f"coil must be in [0, {coil_count})")
    echo_count = sum(bool(torch.any(rep.adc_usage > 0)) for rep in seq)
    if echo_count == 0:
        raise ValueError("sequence has no ADC-bearing echoes")
    if echo_count > max_echo_train_length:
        raise ValueError(
            f"{echo_count} ADC-bearing echoes exceed the supported ETL "
            f"{max_echo_train_length}"
        )
    if len(seq) > max_echo_train_length + 1:
        raise ValueError(
            "the bounded enumerator supports one excitation followed by at most "
            f"{max_echo_train_length} RF intervals"
        )
    if len(seq) != echo_count + 1 or bool(torch.any(seq[0].adc_usage > 0)):
        raise ValueError(
            "single-shot scope requires one non-ADC excitation interval followed "
            "by exactly one ADC-bearing interval per echo"
        )
    for index, rep in enumerate(seq[1:], 1):
        adc = np.flatnonzero(rep.adc_usage.detach().cpu().numpy() > 0)
        if adc.size == 0 or np.any(np.diff(adc) != 1):
            raise ValueError(
                f"RF interval {index} must contain one contiguous ADC window"
            )
    usages = [getattr(rep.pulse.usage, "name", "UNDEF") for rep in seq]
    if usages[0] != "EXCIT" or any(usage != "REFOC" for usage in usages[1:]):
        raise ValueError(
            "single-shot scope requires one EXCIT pulse followed only by REFOC pulses; "
            f"got {usages}"
        )


def primary_history(repetition: int) -> tuple[str, ...]:
    """Primary spin-echo history: excitation ``+``, then alternating signs."""
    return tuple("+" if i % 2 == 0 else "-" for i in range(repetition + 1))


def _rf_coefficients(rep, data) -> tuple[
    complex, complex, complex, complex, float, float
]:
    shim = torch.as_tensor(rep.pulse.shim_array).detach().cpu()
    b1 = torch.as_tensor(data.B1).detach().cpu()
    if shim.shape[0] == 1:
        b1_eff = complex(b1[:, 0].sum())
    else:
        if b1.shape[0] != shim.shape[0]:
            raise ValueError("pulse transmit channels do not match data.B1")
        weights = shim[:, 0] * torch.exp(-1j * shim[:, 1])
        b1_eff = complex((b1[:, 0] * weights).sum())

    angle = float(rep.pulse.angle) * abs(b1_eff)
    phase = float(rep.pulse.phase) + np.angle(b1_eff)
    p_to_p = float(np.cos(angle / 2) ** 2)
    z_to_z = float(np.cos(angle))
    z_to_p = -INV_SQRT2 * 1j * np.sin(angle) * np.exp(1j * phase)
    p_to_z = -np.conjugate(z_to_p)
    m_to_z = -z_to_p
    m_to_p = (1 - p_to_p) * np.exp(2j * phase)
    return complex(z_to_p), complex(p_to_z), complex(m_to_z), complex(m_to_p), p_to_p, z_to_z


def _branch(paths: Iterable[_Path], coeffs) -> list[_Path]:
    z_to_p, p_to_z, m_to_z, m_to_p, p_to_p, z_to_z = coeffs
    result: list[_Path] = []
    for path in paths:
        if path.kind == "z":
            z_label = "Z0" if path.equilibrium else "Z"
            result.append(_Path(
                "z", path.mag * z_to_z, path.kt.copy(), path.parity,
                path.history + (z_label,), path.equilibrium,
            ))
            result.append(_Path(
                "p", path.mag * z_to_p, path.kt.copy(), path.parity,
                path.history + (("+" if path.parity > 0 else "-"),), False,
            ))
        else:
            result.append(_Path(
                "p", path.mag * p_to_p, path.kt.copy(), path.parity,
                path.history + (("+" if path.parity > 0 else "-"),), False,
            ))
            result.append(_Path(
                "p", np.conjugate(path.mag) * m_to_p, -path.kt.copy(),
                -path.parity,
                path.history + (("-" if path.parity > 0 else "+"),), False,
            ))
            result.append(_Path(
                "z", path.mag * p_to_z, path.kt.copy(), path.parity,
                path.history + ("Z",), False,
            ))
            result.append(_Path(
                "z", np.conjugate(path.mag) * m_to_z, -path.kt.copy(),
                -path.parity, path.history + ("Z",), False,
            ))
    return result


def _sample_value(path: _Path, trajectory: np.ndarray, event: int, rep, data,
                  diffusion: np.ndarray, pos: np.ndarray, b0: float,
                  t2: float, t2dash: float, pd_coil: complex,
                  dephasing_cache: dict[tuple[float, float, float], float]) -> complex:
    kt = path.kt + trajectory[event]
    elapsed = trajectory[event, 3]
    rotation = np.exp(-2j * pi * (kt[3] * b0 + np.dot(kt[:3], pos)))
    relaxation = np.exp(-elapsed / t2) * np.exp(-abs(kt[3]) / t2dash)
    k_key = tuple(float(value) for value in kt[:3])
    if k_key not in dephasing_cache:
        k_tensor = torch.as_tensor(kt[:3], dtype=torch.float32).reshape(1, 3)
        dephasing_cache[k_key] = float(torch.as_tensor(
            data.dephasing_func(k_tensor, data.nyquist)
        ).detach().cpu().reshape(-1)[0])
    dephasing = dephasing_cache[k_key]
    adc_rotation = np.exp(1j * float(rep.adc_phase[event]))
    return (
        SQRT2 * path.mag * rotation * relaxation * diffusion[event]
        * dephasing * pd_coil * adc_rotation
    )


def enumerate_center_pathways(
    seq,
    data,
    *,
    coil: int = 0,
    max_echo_train_length: int = 8,
) -> list[EchoPathwayMetrics]:
    """Enumerate exact complex contributions at each ADC window's center.

    No magnitude threshold or strongest-path inference is used.  The primary
    pathway is selected only by its explicit no-``Z`` alternating history.
    ``primary_l1_fraction`` uses the sum of magnitudes of coherently grouped
    histories as its denominator.  The separately reported coherent ratios can
    exceed one when pathways cancel.
    """
    _validate(seq, data, coil, max_echo_train_length)
    if seq.normalized_grads:
        size = torch.as_tensor(data.size).detach().cpu().numpy().astype(float)
        if np.any(size == 0):
            raise ValueError("normalized gradients require nonzero data.size")
        grad_scale = 1 / size
    else:
        grad_scale = np.ones(3)

    paths = [_Path("z", 1 + 0j, np.zeros(4), +1, (), True)]
    echoes: list[EchoPathwayMetrics] = []
    elapsed_before_rep = 0.0
    echo_number = 0
    pos = torch.as_tensor(data.voxel_pos).detach().cpu().numpy()[0]
    b0 = _scalar(data.B0, "B0")
    t1 = abs(_scalar(data.T1, "T1"))
    t2 = abs(_scalar(data.T2, "T2"))
    t2dash = abs(_scalar(data.T2dash, "T2dash"))
    d = _scalar(data.D, "D")
    pd_coil = abs(_scalar(data.PD, "PD")) * _complex_scalar(
        data.coil_sens[coil, 0], "coil sensitivity"
    )
    dephasing_cache: dict[tuple[float, float, float], float] = {}

    for rep_index, rep in enumerate(seq):
        paths = _branch(paths, _rf_coefficients(rep, data))
        dt = rep.event_time.detach().cpu().numpy().astype(float)
        gradm = rep.gradm.detach().cpu().numpy().astype(float) * grad_scale[None, :]
        trajectory = np.cumsum(np.column_stack((gradm, dt)), axis=0)
        adc_events = np.flatnonzero(rep.adc_usage.detach().cpu().numpy() > 0)
        center_event = int(adc_events[len(adc_events) // 2]) if adc_events.size else None

        grouped: dict[tuple[str, ...], complex] = {}
        evolved: list[_Path] = []
        total_time = float(dt.sum())
        r1 = np.exp(-total_time / t1)
        r2 = np.exp(-total_time / t2)

        for path in paths:
            dist_traj = path.kt[None, :] + trajectory
            k2 = dist_traj[:, :3]
            k1 = np.vstack((path.kt[:3], k2[:-1]))
            b = ((2 * pi) ** 2 / 3) * dt * np.sum(
                k1**2 + k1*k2 + k2**2, axis=1
            )
            diffusion = np.exp(-1e-9 * d * np.cumsum(b))

            if path.kind == "p":
                if center_event is not None:
                    value = _sample_value(
                        path, trajectory, center_event, rep, data, diffusion,
                        pos, b0, t2, t2dash, pd_coil, dephasing_cache,
                    )
                    grouped[path.history] = grouped.get(path.history, 0j) + value
                evolved.append(_Path(
                    "p", path.mag * r2 * diffusion[-1], dist_traj[-1].copy(),
                    path.parity, path.history, False,
                ))
            else:
                z_diffusion = np.exp(
                    -1e-9 * d * total_time * np.linalg.norm(path.kt[:3]) ** 2
                )
                evolved.append(_Path(
                    "z", path.mag * r1 * z_diffusion, path.kt.copy(),
                    path.parity, path.history, path.equilibrium,
                ))

        # T1 recovery is an independent affine source.  Keeping it separate
        # makes every reported complex term attributable to one RF history.
        evolved.append(_Path(
            "z", complex(1 - r1), np.zeros(4), +1,
            ("Z0",) * (rep_index + 1), True,
        ))
        paths = evolved

        if center_event is not None:
            echo_number += 1
            ordered = tuple(
                PathwayContribution(history, value)
                for history, value in sorted(
                    grouped.items(), key=lambda item: abs(item[1]), reverse=True
                )
            )
            primary_key = primary_history(rep_index)
            if primary_key not in grouped:
                raise RuntimeError(
                    "explicit primary history was not enumerated: "
                    + " ".join(primary_key)
                )
            primary = grouped.get(primary_key, 0j)
            total = sum(grouped.values(), 0j)
            other = total - primary
            l1 = float(sum(abs(value) for value in grouped.values()))
            total_abs = abs(total)
            rel_phase = 0.0
            if primary != 0 and other != 0:
                rel_phase = float(np.degrees(np.angle(other / primary)))
            echoes.append(EchoPathwayMetrics(
                echo=echo_number,
                repetition=rep_index,
                adc_event=center_event,
                time_s=elapsed_before_rep + float(trajectory[center_event, 3]),
                primary_history=primary_key,
                contributions=ordered,
                primary=primary,
                other=other,
                total=total,
                l1_amplitude=l1,
                primary_l1_fraction=abs(primary) / l1 if l1 else 0.0,
                other_l1_fraction=(l1 - abs(primary)) / l1 if l1 else 0.0,
                primary_coherent_ratio=abs(primary) / total_abs if total_abs else np.inf,
                other_coherent_ratio=abs(other) / total_abs if total_abs else np.inf,
                other_relative_phase_deg=rel_phase,
                cancellation_ratio=total_abs / l1 if l1 else 0.0,
            ))
        elapsed_before_rep += total_time

    return echoes


def with_mrzero_closure(
    seq,
    data,
    *,
    coil: int = 0,
    max_echo_train_length: int = 8,
    max_state_count: int = 100_000,
) -> list[EchoPathwayMetrics]:
    """Enumerate pathways and attach closure against an unpruned MRzero run."""
    import MRzeroCore as mr0

    metrics = enumerate_center_pathways(
        seq, data, coil=coil, max_echo_train_length=max_echo_train_length
    )
    graph = mr0.compute_graph(
        seq, data, max_state_count=max_state_count, min_state_mag=0
    )
    signal = mr0.execute_graph(
        graph, seq, data,
        min_emitted_signal=0, min_latent_signal=0,
        print_progress=False, clear_state_mag=True,
    ).detach().cpu().numpy()

    result: list[EchoPathwayMetrics] = []
    offset = 0
    metric_index = 0
    for rep in seq:
        count = int(torch.sum(rep.adc_usage > 0))
        if count:
            measured = complex(signal[offset + count // 2, coil])
            metric = metrics[metric_index]
            denom = max(abs(measured), np.finfo(float).eps)
            result.append(EchoPathwayMetrics(
                **{
                    **metric.__dict__,
                    "mrzero_signal": measured,
                    "closure_relative_error": abs(metric.total - measured) / denom,
                }
            ))
            metric_index += 1
        offset += count
    return result


def format_report(metrics: Iterable[EchoPathwayMetrics], top: int = 6) -> str:
    """Format quantitative primary/other metrics and leading histories."""
    lines = [
        "Exact center-ADC pathway decomposition",
        "  primary = explicit + - + - ... history (no Z)",
        "  L1 fraction = |group| / sum(|coherently grouped histories|)",
    ]
    for metric in metrics:
        closure = ""
        if metric.closure_relative_error is not None:
            closure = f", closure {metric.closure_relative_error:.3e}"
        lines.append(
            f"-- echo {metric.echo}  rep {metric.repetition}: "
            f"primary {100*metric.primary_l1_fraction:.3f}% L1, "
            f"other {100*metric.other_l1_fraction:.3f}% L1, "
            f"other phase {metric.other_relative_phase_deg:+.2f} deg, "
            f"net/L1 {metric.cancellation_ratio:.6f}{closure}"
        )
        lines.append(
            f"   primary {abs(metric.primary):.9g} at "
            f"{np.degrees(np.angle(metric.primary)):+.2f} deg   "
            f"{' '.join(metric.primary_history)}"
        )
        for contribution in metric.contributions[:top]:
            lines.append(
                f"   {abs(contribution.value):.9g} at "
                f"{np.degrees(np.angle(contribution.value)):+.2f} deg   "
                f"{contribution.label}"
            )
    return "\n".join(lines)


def _complex_record(value: complex) -> dict[str, float]:
    return {
        "real": float(value.real),
        "imag": float(value.imag),
        "magnitude": float(abs(value)),
        "phase_deg": float(np.degrees(np.angle(value))),
    }


def _finite_or_none(value: float) -> float | None:
    return float(value) if np.isfinite(value) else None


def metric_record(metric: EchoPathwayMetrics, top: int | None = 12) -> dict:
    """Convert one metric to a JSON-serializable scientific record."""
    contributions = metric.contributions if top is None else metric.contributions[:top]
    return {
        "echo": metric.echo,
        "repetition": metric.repetition,
        "adc_event": metric.adc_event,
        "center_time_s": metric.time_s,
        "center_rule": "upper middle sample (zero-based index sample_count // 2)",
        "primary_history": list(metric.primary_history),
        "primary_present": any(
            contribution.history == metric.primary_history
            for contribution in metric.contributions
        ),
        "pathway_history_count": len(metric.contributions),
        "reported_pathway_count": len(contributions),
        "primary": _complex_record(metric.primary),
        "other_coherent_sum": _complex_record(metric.other),
        "total": _complex_record(metric.total),
        "l1_amplitude": metric.l1_amplitude,
        "primary_l1_fraction": metric.primary_l1_fraction,
        "other_l1_fraction": metric.other_l1_fraction,
        "primary_coherent_ratio": _finite_or_none(metric.primary_coherent_ratio),
        "other_coherent_ratio": _finite_or_none(metric.other_coherent_ratio),
        "other_relative_to_primary_phase_deg": metric.other_relative_phase_deg,
        "net_over_l1_cancellation_ratio": metric.cancellation_ratio,
        "mrzero_signal": (
            None if metric.mrzero_signal is None
            else _complex_record(metric.mrzero_signal)
        ),
        "closure_relative_error": metric.closure_relative_error,
        "pathways": [
            {
                "history": list(contribution.history),
                "value": _complex_record(contribution.value),
                "l1_fraction": (
                    abs(contribution.value) / metric.l1_amplitude
                    if metric.l1_amplitude else 0.0
                ),
            }
            for contribution in contributions
        ],
    }


def _cli(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Exact center-ADC pathway metrics for single-shot FSE (ETL <= 8)."
    )
    parser.add_argument("seq_file")
    parser.add_argument("--out", required=True, help="output JSON file")
    parser.add_argument("--b1", type=float, default=1.0, help="relative B1 scale")
    parser.add_argument("--b0", type=float, default=0.0, help="off-resonance [Hz]")
    parser.add_argument("--T1", type=float, default=1.5, help="T1 [s]")
    parser.add_argument("--T2", type=float, default=0.08, help="T2 [s]")
    parser.add_argument("--T2dash", type=float, default=0.03, help="T2' [s]")
    parser.add_argument(
        "--diffusion-mm2-s", dest="D", type=float, default=0.0,
        help="diffusion coefficient [mm^2/s], e.g. 0.001 (converted for MRzero)",
    )
    parser.add_argument(
        "--voxel-mm", type=float, nargs=3, default=[0.2, 0.2, 1.0],
        metavar=("X", "Y", "Z"), help="box voxel dimensions [mm]",
    )
    parser.add_argument("--coil", type=int, default=0)
    parser.add_argument(
        "--top", type=int, default=12,
        help="pathway histories saved per echo; 0 saves every history",
    )
    parser.add_argument("--max-states", type=int, default=1_000_000)
    args = parser.parse_args(argv)
    if args.D < 0:
        parser.error("--diffusion-mm2-s must be nonnegative")
    if args.top < 0:
        parser.error("--top must be nonnegative")

    import MRzeroCore as mr0

    seq = mr0.Sequence.import_file(args.seq_file)
    d_mrzero = args.D * 1e3  # MRzero convention: units of 10^-3 mm^2/s
    voxel_m = [value * 1e-3 for value in args.voxel_mm]
    data = mr0.CustomVoxelPhantom(
        pos=[[0.0, 0.0, 0.0]], PD=1.0,
        T1=args.T1, T2=args.T2, T2dash=args.T2dash,
        D=d_mrzero, B0=args.b0, B1=args.b1,
        voxel_size=voxel_m, voxel_shape="box",
    ).build()
    metrics = with_mrzero_closure(
        seq, data, coil=args.coil, max_state_count=args.max_states
    )
    save_top = None if args.top == 0 else args.top
    records = [metric_record(metric, save_top) for metric in metrics]
    max_closure = max(
        metric.closure_relative_error or 0.0 for metric in metrics
    )
    payload = {
        "metadata": {
            "sequence_file": os.path.abspath(args.seq_file),
            "method": "independent exhaustive RF-branch enumeration",
            "primary_definition": "+ - + - ... after excitation, with no Z interval",
            "grouping": (
                "RF branches with the same displayed history are summed coherently; "
                "L1 fractions use magnitudes after that history-level grouping"
            ),
            "rf_model": "instantaneous rotations (MRzero execute_graph limitation)",
            "scope": (
                "one stationary voxel, one receive coil, one excitation, "
                "at most 8 ADC-bearing refocusing intervals"
            ),
            "B1_relative": args.b1,
            "B0_Hz": args.b0,
            "T1_s": args.T1,
            "T2_s": args.T2,
            "T2dash_s": args.T2dash,
            "D_mm2_per_s": args.D,
            "D_MRzero_units_1e-3_mm2_per_s": d_mrzero,
            "voxel_size_mm": args.voxel_mm,
            "coil": args.coil,
            "enumeration_pruning": "none",
            "mrzero_graph_min_state_mag": 0.0,
            "mrzero_execute_thresholds": 0.0,
            "mrzero_graph_max_state_count": args.max_states,
            "longitudinal_diffusion_compatibility": (
                "mirrors MRzeroCore 1.1.1 execute_graph exactly; its longitudinal "
                "state decay uses exp(-1e-9 D dt |k|^2), without the (2*pi)^2 "
                "factor used by its transverse b integration"
            ),
            "max_closure_relative_error": max_closure,
        },
        "echoes": records,
    }
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(format_report(metrics, top=min(args.top or 6, 6)))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())

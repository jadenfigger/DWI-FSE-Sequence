"""Event-level Bloch model of the actual v1.83 and v1.912 PPL/PPR pair (Oct 12 in-vivo protocols).

Helper for oct12_b1_sensitivity.py.  The scanner PPL sources are run through the repository's
PPL-to-event mapper (dwfse.ppl; nominal instruction costs, no compiler/console timing), which gives
the played RF samples (research SLR frames for v1.912, stock 3-lobe sinc for v1.83), gradient
waveforms and ADC windows of the first shot.  The same Bloch engine as docs/v19 (dwfse.ppl.bloch)
then plays that shot on a z-grid (5 slice widths) with an optional phase-axis grid for the ss-MGOT
spoiler.  B1 scale kappa multiplies every RF sample; df is a global off-resonance.

Navigator-train convention: nav_on=1 and shot 1 is the volume navigator, i.e. 8 echoes with zero
phase encoding (the quantity measured as "echo train" on the scanner).  Echo amplitude is |signal|
at the middle of each ADC window, in units of M0 for a full 1-mm slice.

Not modelled: T2' / intravoxel B0 spread, diffusion (b10 is negligible), x (readout) dimension
and receive profile, MT, TR steady state unless tr_ms is given.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from dwfse.ppl.run import map_events  # noqa: E402
from dwfse.ppl.ledger import build_ledger, adc_middle_times  # noqa: E402
from dwfse.ppl.bloch import EventBloch, Grid, SimConfig, rf_calibration_hz_per_unit  # noqa: E402
from dwfse.vendor_seq import decode  # noqa: E402

SC = ROOT / "scanner"
PLAN = ROOT / "experiments/2026-10-12_exvivo_invivo_plan"
CASES = {
    "v183": dict(ppl=SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.83.ppl",
                 ppr=PLAN / "FSE-DWI_10-12-2026_v183_testU/FSE-DWI_10-12-2026_v183_testU.ppr"),
    "v1912": dict(ppl=SC / "FSE_dwi_CPMG_non_CPMG_twoTE-1.912.ppl",
                  ppr=PLAN / "FSE-DWI_10-12-2026_v1912_testV/FSE-DWI_10-12-2026_v1912_testV.ppr"),
}
# One centre slice, one b10 row, navigator mode 1 (shot 1 = unencoded 8-echo navigator train).
OVERRIDES = {"no_slices": 1, "fov_slice_off": [0], "no_diff_acq": 1, "no_experiments": 1,
             "acq_b": [10], "acq_x": [1000], "acq_y": [0], "acq_z": [0],
             "nav_on": 1, "no_views": 136, "views_per_seg": 8, "no_disacq": 0}
MODEL = dict(stmt_cost_us=0.0, expr_costs=True, expr_scale=0.8)   # nominal instruction-cost model
W_SLICE = 1.0e-3                       # protocol slice width (m)
VOXEL_Y = 35e-3 / 128                  # phase-axis voxel (FOV 35 mm / 128)
T1_DEFAULT, T2_DEFAULT = 1.9, 0.045    # in-vivo brain, 9.4 T
TR_S = 2.0


def setup(ver: str) -> dict:
    c = CASES[ver]
    it = map_events(c["ppl"], c["ppr"], overrides=OVERRIDES, max_shots=2, rf_latency_us=3.0, **MODEL)
    led = build_ledger(it, 1)
    stock = decode(SC / "utilities/rfstd44.seq").frame("3lobe_sinc_3kHz")
    led["cal"] = rf_calibration_hz_per_unit(stock.samples, stock.wait_ticks / 10, it.vars["rfcal"].value)
    lat = float(it.vars["rfdelay"].value)
    return dict(ver=ver, it=it, led=led, lat=lat, adc=adc_middle_times(it, led))


def make_grid(ver: str, nz: int = 3000, ny: int | None = None, span: float = 5.0) -> Grid:
    z = (np.arange(nz) + 0.5) / nz * span * W_SLICE - span * W_SLICE / 2
    if ny is None:
        ny = 32 if ver == "v1912" else 1
    y = (np.arange(ny) + 0.5) / ny * VOXEL_Y - VOXEL_Y / 2 if ny > 1 else np.zeros(1)
    return Grid(z, y)


def echo_train(ctx: dict, kappa: float = 1.0, df: float = 0.0, T1: float = T1_DEFAULT,
               T2: float = T2_DEFAULT, nz: int = 3000, ny: int | None = None, tr_s: float | None = None,
               n_cycles: int = 6, return_profile: bool = False):
    """Complex signal (M0 units, full 1-mm slice = 1) at the middle of each of the 8 ADC windows.

    tr_s=None  : single shot from fully relaxed equilibrium.
    tr_s=2.0   : repeat the shot n_cycles times with TR (transverse state discarded, T1 regrowth of Mz
                 over TR minus shot duration); the last cycle is returned (dummy-train steady state).
    """
    led, it, lat = ctx["led"], ctx["it"], ctx["lat"]
    grid = make_grid(ctx["ver"], nz=nz, ny=ny)
    cfg = SimConfig(b1_scale=kappa, df_hz=df, grad_latency_us=lat, t1_s=T1, t2_s=T2)
    sim = EventBloch(led, grid, led["cal"], cfg)
    dz = (grid.z[1] - grid.z[0]) / W_SLICE
    out = None
    for cyc in range(1 if tr_s is None else n_cycles):
        t_prev = sim.t
        snaps, ad = sim.run(led["rf"], {}, ctx["adc"], rf_substeps=1)
        out = np.array([complex(ad[n][0].mean(axis=0).sum() * dz) for n, _ in ctx["adc"]])
        if tr_s is not None:
            # duration of the played shot = from first event to the last processed time
            first = min(p["t"][0] for p in led["rf"]) - 1.0
            dur_s = (sim.t - first) * 1e-6
            gap = max(tr_s - dur_s, 0.0)
            sim.m[:] = 0
            sim.mz = 1 + (sim.mz - 1) * np.exp(-gap / T1)
    if return_profile:
        return out, grid.z, sim
    return out


def flip_table(ctx: dict) -> list[dict]:
    """Nominal on-resonance flip of each RF event under the repository's inferred linear calibration
    (rfcal gives 90 deg on the stock 3-lobe sinc), plus the slice-select gradient (Hz/mm) at its centre."""
    rows = []
    led = ctx["led"]
    for p in led["rf"]:
        integral = float(np.sum(p["amp"])) * led["cal"] * p["dt"] * 1e-6
        g = led["G"]["S"].value_at(p["t_center"] - ctx["lat"]) / 32767.0 * led["H"]
        rows.append(dict(frame=p["frame"], t_center_us=p["t_center"], phase_deg=p["phase_deg"],
                         mul=p["mul"], nominal_flip_deg=360.0 * integral, slice_grad_hz_per_mm=float(g)))
    return rows


# ----------------------------------------------------------------------------- parallel job runner
import json  # noqa: E402
import time  # noqa: E402
from concurrent.futures import ProcessPoolExecutor, as_completed  # noqa: E402

_CTX: dict = {}


def make_job(ver, kappa, df=0.0, T1=T1_DEFAULT, T2=T2_DEFAULT, tr_s=None, nz=1000, ny=64):
    return dict(ver=ver, kappa=round(float(kappa), 4), df=round(float(df), 2), T1=float(T1), T2=float(T2),
                tr_s=None if tr_s is None else float(tr_s), nz=int(nz), ny=int(ny))


def job_key(j: dict) -> str:
    return "|".join(f"{k}={j[k]}" for k in ("ver", "kappa", "df", "T1", "T2", "tr_s", "nz", "ny"))


def _work(j: dict):
    if j["ver"] not in _CTX:
        _CTX[j["ver"]] = setup(j["ver"])
    t = time.time()
    s = echo_train(_CTX[j["ver"]], kappa=j["kappa"], df=j["df"], T1=j["T1"], T2=j["T2"], nz=j["nz"],
                   ny=j["ny"], tr_s=j["tr_s"])
    return job_key(j), [[float(x.real), float(x.imag)] for x in s], time.time() - t


def load_cache(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def run_jobs(jobs: list[dict], cache_path: Path, workers: int = 14, verbose: bool = True) -> dict:
    """Run missing Bloch jobs in parallel (expensive v1.912 jobs first); results cached as JSON.
    cache[key] = [[re, im] x 8].  Returns the cache."""
    cache = load_cache(cache_path)
    todo = {job_key(j): j for j in jobs if job_key(j) not in cache}
    order = sorted(todo.values(), key=lambda j: -(j["nz"] * j["ny"] * (6 if j["tr_s"] else 1)
                                                  * (1 if j["ver"] == "v1912" and True else 0.05)))
    if verbose:
        print(f"[bloch] {len(jobs)} jobs, {len(todo)} to run, {workers} workers", flush=True)
    t0 = time.time()
    done = 0
    if todo:
        with ProcessPoolExecutor(workers) as ex:
            futs = [ex.submit(_work, j) for j in order]
            for f in as_completed(futs):
                key, s, dt = f.result()
                cache[key] = s
                done += 1
                if verbose and (done % 10 == 0 or done == len(todo)):
                    print(f"[bloch] {done}/{len(todo)} done, {time.time() - t0:.0f} s elapsed", flush=True)
                if done % 25 == 0:
                    cache_path.write_text(json.dumps(cache))
        cache_path.write_text(json.dumps(cache))
    return cache


def get_echoes(cache: dict, j: dict) -> np.ndarray:
    """|signal| at the 8 echoes (M0 units) from a cache entry."""
    a = np.array(cache[job_key(j)])
    return np.hypot(a[:, 0], a[:, 1])


if __name__ == "__main__":
    for v in ("v183", "v1912"):
        t = time.time()
        ctx = setup(v)
        print(v, "setup", round(time.time() - t, 1), "s")
        for r in flip_table(ctx):
            print("  ", r["frame"], round(r["t_center_us"] - ctx["led"]["rf"][0]["t_center"], 0), r["phase_deg"], r["mul"],
                  round(r["nominal_flip_deg"], 1))
        t = time.time()
        s = echo_train(ctx, nz=1000)
        print(v, "kappa=1:", np.round(np.abs(s), 4), "time", round(time.time() - t, 1), "s")

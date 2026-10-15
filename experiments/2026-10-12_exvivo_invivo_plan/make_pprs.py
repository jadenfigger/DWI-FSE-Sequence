"""Generate the 2026-10-12 protocols: ex-vivo brain/PBS checks, then in-vivo rat brain (surface coil).

Run from the repository root:  python experiments/2026-10-12_exvivo_invivo_plan/make_pprs.py
Templates are the repository v1.83 / v1.912 PPRs (scanner/), whose :VAR order matches each PPL.
Changes from the 10-11 generator, from what the console taught us:
  * nav_on=2 stores VIEWS_PER_SEGMENT = ETL+1 = 9 (console: NO_VIEWS must be a multiple of it).
  * Multi-slice FOV_OFFSETS rows ", 0, 0, z_mm" are written (the 10-11 console-fixed format).
  * TR 2000 ms everywhere (TR 1000 gave echo-phase alternation with PBS on 10-11).
  * v1.83 protocols carry v183_phmode / v183_phcal in PPL order.
No PPL, raw data or earlier protocol is modified.
"""
from pathlib import Path
import csv
import hashlib
import json
import re
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DATE = "10-12-2026"
VERSIONS = {"v183": "1.83", "v1912": "1.912"}
X, Y, Z = (1000, 0, 0), (0, 1000, 0), (0, 0, 1000)
SIX = [(707, 707, 0), (707, 0, 707), (0, 707, 707), (707, -707, 0), (707, 0, -707), (0, 707, -707)]


def twelve_directions(n=12, iters=4000, seed=7):
    """Antipodally symmetric electrostatic set of n unit vectors, as integer thousandths (|v| ~ 1000)."""
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(n, 3)); v /= np.linalg.norm(v, axis=1)[:, None]
    for it in range(iters):
        f = np.zeros_like(v)
        for s in (1, -1):
            d = v[:, None, :] - s*v[None, :, :]
            r = np.linalg.norm(d, axis=2) + np.eye(n)
            f += (d / r[:, :, None]**3).sum(1)
        v += 0.01*f/(1+it/500); v /= np.linalg.norm(v, axis=1)[:, None]
    v *= np.where(v[:, 2:3] < 0, -1, 1)         # canonical hemisphere (z >= 0)
    q = np.round(v*1000).astype(int)
    return [tuple(int(c) for c in row) for row in q]


TWELVE = twelve_directions()
B10 = (10, X)
PHASE_CAL = [B10]
NAVTEST = [B10, (1000, X), (3000, Z), (6000, Z)]
COMPARE_SHELLS = [B10] + [(b, d) for b in (1000, 3000) for d in (X, Y, Z)]
COMPARE_DTI6 = [B10] + [(2000, d) for d in SIX]
INVIVO_QUICK = [B10] + [(1000, d) for d in (X, Y, Z)]
INVIVO_FULL = ([B10] + [(1000, d) for d in TWELVE] + [B10] + [(3000, d) for d in TWELVE]
               + [B10] + [(6000, d) for d in TWELVE])
OFF_12, OFF_28, OFF_5 = [-480, 0, 480], [-1120, 0, 1120], [-2000, 0, 2000]   # 400 units = 1 mm


def base(letter, version, part, purpose, rows, **kw):
    item = dict(letter=letter, version=version, part=part, purpose=purpose, rows=rows,
                dwell_us=25, esp=11, tr=2000, te=44, big_delta=30000, nav_on=2, offsets=[0], matrix=128,
                phmode=0, phcal=0, sample="ex-vivo brain in PBS", note="")
    item.update(kw)
    return item


TESTS = [
    # Part 0: centre frequency and ss-MGOT rescue
    base("A", "v183", 0, "Frequency check 1/2: b10 at 20 kHz (compare readout position with B)", [B10], dwell_us=50, esp=14, nav_on=1),
    base("B", "v183", 0, "Frequency check 2/2: b10 at 40 kHz; image must register with A within 0.5 px", [B10], nav_on=1),
    base("C", "v1912", 0, "ss-MGOT rescue after frequency check: b10, b1000 +x, b3000 +x; must show b-dependent signal", [B10, (1000, X), (3000, X)], nav_on=1),
    # Part 1: off-centre RF phase calibration (docs/v183/CALIBRATION.md)
    base("D", "v183", 1, "Calibration step 1: mode 0 (vendor), +/-1.2 mm", PHASE_CAL, nav_on=1, offsets=OFF_12),
    base("E", "v183", 1, "Calibration step 2a: mode 1, phcal 0 (= v1.82), +/-1.2 mm", PHASE_CAL, nav_on=1, offsets=OFF_12, phmode=1, phcal=0),
    base("F", "v183", 1, "Calibration step 2b: mode 1, phcal +530, +/-1.2 mm", PHASE_CAL, nav_on=1, offsets=OFF_12, phmode=1, phcal=530),
    base("G", "v183", 1, "Calibration step 2c: mode 1, phcal -530, +/-1.2 mm", PHASE_CAL, nav_on=1, offsets=OFF_12, phmode=1, phcal=-530),
    base("H", "v183", 1, "Verify mode 0 at the protocol spacing, +/-2.8 mm", PHASE_CAL, nav_on=1, offsets=OFF_28),
    base("I", "v183", 1, "Verify mode 0 at +/-5 mm", PHASE_CAL, nav_on=1, offsets=OFF_5),
    base("J", "v183", 1, "Verify mode 1 at +/-2.8 mm: SET v183_phcal TO THE TOOL'S RECOMMENDATION", PHASE_CAL, nav_on=1, offsets=OFF_28, phmode=1,
         note="v183_phcal is 0 in the file; edit on the console"),
    base("K", "v183", 1, "Verify mode 1 at +/-5 mm: SET v183_phcal TO THE TOOL'S RECOMMENDATION", PHASE_CAL, nav_on=1, offsets=OFF_5, phmode=1,
         note="v183_phcal is 0 in the file; edit on the console"),
    base("L", "v1912", 1, "ss-MGOT off-centre phase (gated scheme, uncalibrated) at +/-2.8 mm; only if C showed signal", PHASE_CAL, nav_on=1, offsets=OFF_28),
    # Part 2: per-shot navigators (single slice), high-b z is the target
    base("M", "v183", 2, "Navigator test: volume navigator only (nav 1)", NAVTEST, nav_on=1),
    base("N", "v183", 2, "Navigator test: per-shot navigators (nav 2), otherwise identical to M", NAVTEST),
    base("O", "v1912", 2, "Navigator test ss-MGOT: nav 1", NAVTEST, nav_on=1),
    base("P", "v1912", 2, "Navigator test ss-MGOT: nav 2, otherwise identical to O", NAVTEST),
    # Part 3: matched ~5-min comparisons, 3 slices at +/-2.8 mm (v1.912 spacing guard 2.7575 mm)
    base("Q", "v183", 3, "Comparison 1: b10 + b1000/b3000 along x, y, z; 3 slices", COMPARE_SHELLS, offsets=OFF_28),
    base("R", "v1912", 3, "Comparison 1 (ss-MGOT), matched to Q", COMPARE_SHELLS, offsets=OFF_28),
    base("S", "v183", 3, "Comparison 2: b10 + 6 oblique directions at b2000; 3 slices", COMPARE_DTI6, offsets=OFF_28),
    base("T", "v1912", 3, "Comparison 2 (ss-MGOT), matched to S", COMPARE_DTI6, offsets=OFF_28),
    # Part 4: in vivo, surface coil
    base("U", "v183", 4, "In vivo quick check: b10 + b1000 x, y, z; 3 slices", INVIVO_QUICK, offsets=OFF_28, sample="in-vivo rat brain, surface coil"),
    base("V", "v1912", 4, "In vivo quick check (ss-MGOT), matched to U", INVIVO_QUICK, offsets=OFF_28, sample="in-vivo rat brain, surface coil"),
    base("W", "v183", 4, "In vivo full: 3 x b10 + 12 directions at b1000, b3000, b6000; 3 slices", INVIVO_FULL, offsets=OFF_28, sample="in-vivo rat brain, surface coil"),
    base("X", "v1912", 4, "In vivo full (ss-MGOT), matched to W", INVIVO_FULL, offsets=OFF_28, sample="in-vivo rat brain, surface coil"),
]
# nav-1 fallbacks (double letter) for every nav-2 comparison and in-vivo protocol, in case nav 2 fails on the console
for item in [t for t in TESTS if t["part"] in (3, 4)]:
    fb = dict(item, letter=item["letter"]*2, nav_on=1, purpose="FALLBACK (nav 1) for " + item["letter"] + ": " + item["purpose"])
    TESTS.append(fb)

RUN_ORDER = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X"]


def replace_record(lines, name, value):
    hits = [i for i, line in enumerate(lines) if re.match(rf":\w+\s+{re.escape(name)}\s*,", line, re.I)]
    assert len(hits) == 1, (name, hits)
    parts = lines[hits[0]].split(",")
    parts[1] = " " + str(value)
    lines[hits[0]] = ",".join(parts)


def replace_array(lines, name, values, resize=False):
    hits = [i for i, line in enumerate(lines) if re.match(rf":\w+\s+{re.escape(name)}\s*,", line, re.I)]
    assert len(hits) == 1, name
    i = hits[0]
    n = len(values) if resize else int(lines[i].split(",")[1])
    assert len(values) <= n, (name, len(values), n)
    values = list(values) + [0]*(n-len(values))
    end = i+1
    while end < len(lines) and lines[end].startswith(","):
        end += 1
    head = lines[i].split(",")[0]
    angle = name in ("r_angle_var", "p_angle_var", "s_angle_var")
    block = [f"{head}, {n}" if angle else f"{head}, {n}, {values[0]}"]
    block += [", " + ", ".join(map(str, values[j:j+8])) for j in range(0 if angle else 1, n, 8)]
    lines[i:end] = block


def replace_meta(lines, name, first, continuation=None):
    i = next(i for i, line in enumerate(lines) if line.startswith(f":{name} "))
    end = i+1
    while end < len(lines) and lines[end].startswith(","):
        end += 1
    lines[i:end] = [f":{name} {first}"] + (continuation or [])


def build(item):
    version = VERSIONS[item["version"]]
    lines = (ROOT/f"scanner/FSE_dwi_CPMG_non_CPMG_twoTE-{version}.ppr").read_bytes().decode("latin-1").replace("\r\n", "\n").split("\n")
    lines[0] = f":PPL G:\\J_Figger\\FSE_dwi_CPMG_non_CPMG_twoTE-{version}.ppl"
    n, etl = item["matrix"], 8
    raw = (etl+1)*(1+n//etl) if item["nav_on"] == 2 else n+etl
    vps = etl+1 if item["nav_on"] == 2 else etl
    pe_scale = (n+etl)/136
    edits = dict(no_samples=n, no_views=raw, views_per_seg=vps, no_views_2=1, nav_on=item["nav_on"],
                 no_experiments=len(item["rows"]), no_diff_acq=len(item["rows"]), no_averages=1, no_disacq=4,
                 no_slices=len(item["offsets"]), batch_slices=0, tr=item["tr"], te=item["te"], esp=item["esp"],
                 big_delta=item["big_delta"], sm_delta=4000, b_input_mode=1, crush_amp=-8223, diff_crush_amp=-5482,
                 gr_var=-1471 if item["dwell_us"] == 25 else -735, gp_init_var=-round(1000*pe_scale), report_on=0,
                 chess_on=0, mtc_on=0, de_on=0, flow_comp_on=0, PE_order=1, rec_freq=0,
                 subj_angle_x=0, subj_angle_y=0, subj_angle_z=0)
    if item["version"] == "v183":
        edits.update(v183_phmode=item["phmode"], v183_phcal=item["phcal"])
    for name, value in edits.items():
        replace_record(lines, name, value)
    replace_meta(lines, "SAMPLE_PERIOD", 'sample_period, 250, 17, "40.0 KHz  25 µs"' if item["dwell_us"] == 25 else 'sample_period, 500, 12, "20.0 KHz  50 µs"')
    replace_meta(lines, "SMX", "0.0449126" if item["dwell_us"] == 25 else "0.0224563")
    replace_meta(lines, "SMY", f"{0.0305406*pe_scale:.10g}")
    replace_meta(lines, "FOV", "35")
    ns = len(item["offsets"])
    if ns > 1:
        gap_mm = (item["offsets"][1]-item["offsets"][0])/400
        replace_meta(lines, "SLICE_SEPARATION", f"slice_offset, {round(gap_mm*1070)}, {gap_mm:g}")
    for name in ("r_angle_var", "p_angle_var", "s_angle_var", "fov_read_off", "fov_phase_off"):
        replace_array(lines, name, [0]*ns, resize=True)
    replace_array(lines, "fov_slice_off", item["offsets"], resize=True)
    replace_meta(lines, "MULTI_ORIENTATION", ns, [", 0"]*ns)
    replace_meta(lines, "FOV_OFFSETS", ns, [f", 0, 0, {z/400:g}" for z in item["offsets"]])
    replace_array(lines, "acq_b", [b for b, _ in item["rows"]])
    for axis, name in enumerate(("acq_x", "acq_y", "acq_z")):
        replace_array(lines, name, [d[axis] for _, d in item["rows"]])
    return "\r\n".join(lines).encode("latin-1"), raw, vps


def main():
    manifest = []
    for item in TESTS:
        stem = f"FSE-DWI_{DATE}_{item['version']}_test{item['letter']}"
        folder = OUT/stem
        folder.mkdir(exist_ok=True)
        data, raw, vps = build(item)
        ppr = folder/f"{stem}.ppr"
        ppr.write_bytes(data)
        shots = raw//vps + 4                      # shots incl. volume-navigator shot, plus 4 dummies
        duration = len(item["rows"])*shots*item["tr"]/1000
        record = dict(item, stem=stem, ppr=str(ppr.relative_to(OUT)).replace("\\", "/"), ppr_sha256=hashlib.sha256(data).hexdigest(),
                      raw_views=raw, views_per_segment=vps, nominal_duration_s=duration, slice_offsets_mm=[x/400 for x in item["offsets"]])
        manifest.append(record)
        (folder/"protocol_notes.json").write_text(json.dumps(record, indent=2)+"\n")
    summary = dict(date="2026-10-12", fov_mm=35, twelve_directions=TWELVE,
                   min_angle_between_12_dirs_deg=min_angle(TWELVE),
                   ppl_sha256={v: hashlib.sha256((ROOT/f"scanner/FSE_dwi_CPMG_non_CPMG_twoTE-{ver}.ppl").read_bytes()).hexdigest() for v, ver in VERSIONS.items()},
                   protocols=manifest)
    (OUT/"manifest.json").write_text(json.dumps(summary, indent=2)+"\n")
    by = {x["letter"]: x for x in manifest}
    with (OUT/"run_order.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["test", "version", "part", "purpose", "volumes", "dwell_us", "ESP_ms", "TE_ms", "Delta_ms", "TR_ms", "matrix",
                    "slices_mm", "navigator", "raw_views", "views_per_segment", "v183_phmode", "v183_phcal", "scan_minutes", "PPR"])
        for letter in RUN_ORDER + [x["letter"] for x in manifest if len(x["letter"]) == 2]:
            x = by[letter]
            w.writerow([letter, x["version"], x["part"], x["purpose"], len(x["rows"]), x["dwell_us"], x["esp"], x["te"], x["big_delta"]/1000,
                        x["tr"], x["matrix"], " ".join(f"{z:g}" for z in x["slice_offsets_mm"]), x["nav_on"], x["raw_views"],
                        x["views_per_segment"], x["phmode"] if x["version"] == "v183" else "", x["phcal"] if x["version"] == "v183" else "",
                        round(x["nominal_duration_s"]/60, 2), x["ppr"]])
    for part in range(5):
        print(f"part {part}: {sum(by[l]['nominal_duration_s'] for l in RUN_ORDER if by[l]['part']==part)/60:.1f} min")
    print("12 directions:", TWELVE, "min angle", round(min_angle(TWELVE), 1))


def min_angle(dirs):
    v = np.array(dirs, float); v /= np.linalg.norm(v, axis=1)[:, None]
    c = np.abs(v@v.T); np.fill_diagonal(c, 0)
    return float(np.degrees(np.arccos(c.max())))


if __name__ == "__main__":
    main()

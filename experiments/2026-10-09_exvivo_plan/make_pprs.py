"""Generate the 2026-10-09 ex-vivo rat brain PPRs.

Every PPR is derived from an acquired 10-07 protocol (the same protocols the
v1.81 / v1.911 candidate PPRs were built from), so geometry, gains, RF and
phase-encode calibration are identical to scans that already ran. Only the
fields listed in each test below are edited. acq_grad is left as acquired:
with b_input_mode=1 the sequence recomputes the diffusion DACs from acq_b
(the 10-07 seven-b scans ran with the same stale acq_grad).

Run from the repo root:  python experiments/2026-10-09_exvivo_plan/make_pprs.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BASE_V18 = ROOT / "experiments/FSE-DWI_10-07-2026_v18_test1/FSE-DWI_10-07-2026_v18_test1.ppr"
BASE_V191 = ROOT / "experiments/FSE-DWI_10-07-2026_v191_test2/FSE-DWI_10-07-2026_v191_test2.ppr"
PPL_DIR = "G:\\J_Figger\\"
PPL = {
    "1.8": "FSE_dwi_CPMG_non_CPMG_twoTE-1.8.ppl",
    "1.81": "FSE_dwi_CPMG_non_CPMG_twoTE-1.81.ppl",
    "1.91": "FSE_dwi_CPMG_non_CPMG_twoTE-1.91.ppl",
    "1.911": "FSE_dwi_CPMG_non_CPMG_twoTE-1.911.ppl",
}

B7 = [(b, (1000, 0, 0)) for b in (0, 100, 500, 1000, 2000, 3000, 6000)]
B3 = [(b, (1000, 0, 0)) for b in (0, 1000, 3000)]
DIRS = [(0, (1000, 0, 0)),
        (1000, (1000, 0, 0)), (1000, (-1000, 0, 0)),
        (1000, (0, 1000, 0)), (1000, (0, 0, 1000)),
        (3000, (1000, 0, 0)), (3000, (0, 1000, 0)), (3000, (0, 0, 1000))]
POLARITY = [(0, (1000, 0, 0)), (1000, (1000, 0, 0)), (1000, (-1000, 0, 0))]

# name: (base, ppl, diffusion rows, scalar edits)
TESTS = {
    "A_v181_7b":        ("v18",  "1.81",  B7,       {"crush_amp": -8223}),
    "B_v1911_7b":       ("v191", "1.911", B7,       {"esp": 13}),
    "C_v18_7b_control": ("v18",  "1.8",   B7,       {}),
    "D_v191_7b_control": ("v191", "1.91", B7,       {}),
    "E_v181_dirs":      ("v18",  "1.81",  DIRS,     {"crush_amp": -8223}),
    "F_v18_polarity":   ("v18",  "1.8",   POLARITY, {}),
    "G_v1911_dirs":     ("v191", "1.911", DIRS,     {"esp": 13}),
    "H_v181_crush_eq_selector": ("v18", "1.81", B3, {"crush_amp": -2741}),
    "I_v1911_delta30":  ("v191", "1.911", B3,       {"esp": 13, "big_delta": 30000, "te": 44}),
    "J_v181_bw_console": ("v18", "1.81",  B3,       {"crush_amp": -8223}),
}


def read(path):
    text = path.read_bytes().decode("latin-1").replace("\r\n", "\n")
    return text.split("\n")


def set_scalar(lines, name, value):
    hits = [i for i, l in enumerate(lines) if l.startswith(f":VAR {name}, ")]
    assert len(hits) == 1, name
    lines[hits[0]] = f":VAR {name}, {value}"


def set_array(lines, name, values):
    i = next(i for i, l in enumerate(lines) if l.startswith(f":VAR_ARRAY {name}, "))
    n = int(lines[i].split(",")[1])
    j = i + 1
    while j < len(lines) and lines[j].startswith(","):
        j += 1
    vals = list(values) + [0] * (n - len(values))
    new = [f":VAR_ARRAY {name}, {n}, {vals[0]}"]
    rest = vals[1:]
    new += [", " + ", ".join(str(v) for v in rest[k:k + 8]) for k in range(0, len(rest), 8)]
    assert len(new) == j - i, (name, len(new), j - i)
    lines[i:j] = new


def build(base, ppl, rows, edits):
    lines = read(BASE_V18 if base == "v18" else BASE_V191)
    assert lines[0].startswith(":PPL ")
    lines[0] = f":PPL {PPL_DIR}{PPL[ppl]}"
    for k, v in edits.items():
        set_scalar(lines, k, v)
    set_scalar(lines, "no_diff_acq", len(rows))
    hits = [i for i, l in enumerate(lines) if l.startswith(":EXPERIMENT_ARRAY no_experiments, ")]
    assert len(hits) == 1
    lines[hits[0]] = f":EXPERIMENT_ARRAY no_experiments, {len(rows)}"
    set_array(lines, "acq_b", [b for b, _ in rows])
    for axis, name in enumerate(("acq_x", "acq_y", "acq_z")):
        set_array(lines, name, [d[axis] for _, d in rows])
    return "\r\n".join(lines).encode("latin-1")


if __name__ == "__main__":
    for name, (base, ppl, rows, edits) in TESTS.items():
        out = OUT / f"FSE-DWI_10-09-2026_{name}.ppr"
        out.write_bytes(build(base, ppl, rows, edits))
        print(out.name, ppl, len(rows), "volumes")

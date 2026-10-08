"""Reader for MR Solutions .ppr protocol files (text records starting with ':')."""
from __future__ import annotations

from pathlib import Path
import re

ARRAY_KEYS = {"VAR_ARRAY", "GRADIENT_STRENGTH", "X_ANGLE", "Y_ANGLE", "Z_ANGLE",
              "FOV_READ_OFF", "FOV_PHASE_OFF", "FOV_SLICE_OFF"}
IGNORE = {"PPL", "FOV", "MULTI_ORIENTATION", "FOV_OFFSETS", "SWZ", "SMX", "SWX", "SMY", "SWY",
          "DSP_ROUTINE", "DATA_TYPE"}


def _num(tok):
    tok = tok.strip()
    try:
        return int(tok)
    except ValueError:
        return float(tok)


def read_ppr(path):
    text = Path(path).read_text(encoding="latin-1")
    records = []
    for line in text.splitlines():
        if line.startswith(":"):
            records.append(line[1:])
        elif line.startswith(",") and records:
            records[-1] += line
    params = {}
    meta = {}
    for rec in records:
        m = re.match(r"(\w+)\s*(.*)$", rec)
        key, rest = m.group(1).upper(), m.group(2)
        if key == "PPL":
            meta["ppl"] = rest.strip()
            continue
        if key in IGNORE:
            meta[key] = rest
            continue
        if key == "OBSERVE_FREQUENCY":
            parts = [p.strip() for p in re.split(r",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", rest)]
            for name in parts[2:6]:
                params[name.lower()] = 0
            meta[key] = rest
            continue
        parts = [p.strip() for p in re.split(r",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", rest)]
        name = parts[0].lower()
        nums = []
        for p in parts[1:]:
            if p.startswith('"'):
                continue
            try:
                nums.append(_num(p))
            except ValueError:
                pass
        if key in ARRAY_KEYS:
            n = int(nums[0])
            params[name] = [int(round(x)) for x in nums[1:1 + n]]
        else:
            params[name] = int(round(nums[0])) if nums else 0
    return params, meta

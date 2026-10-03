"""
scale_b1.py  -  Write a copy of a Pulseq .seq file with every RF amplitude scaled,
                to mimic B1 error (e.g. 0.8 = all flip angles 20 % low).

Useful for simulators that have no B1 map input (e.g. KomaMRI).

Usage
  python scale_b1.py my_seq.seq 0.8            # writes my_seq_b1-0.80.seq
  python scale_b1.py my_seq.seq 0.8 out.seq

It edits only the amplitude column of the [RF] section. The [SIGNATURE]
block (an md5 of the original file) is dropped, since it no longer matches.
"""
import sys


def scale_b1(src, factor, dst=None):
    dst = dst or src.replace(".seq", f"_b1-{factor:.2f}.seq")
    out, section = [], None
    for line in open(src):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s
            if section == "[SIGNATURE]":
                break
            out.append(line)
            continue
        if section == "[RF]" and s and not s.startswith("#"):
            cols = line.split()
            cols[1] = repr(float(cols[1]) * factor)   # column 2 = amplitude [Hz]
            line = " ".join(cols) + "\n"
        out.append(line)
    with open(dst, "w") as f:
        f.writelines(out)
    print(f"wrote {dst}  (RF amplitude x {factor})")
    return dst


if __name__ == "__main__":
    scale_b1(sys.argv[1], float(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None)

"""Centre-frequency check from two otherwise identical scans at 20 kHz and 40 kHz.

    python tools/frequency_check.py SCAN_20kHz.MRD SCAN_40kHz.MRD

A centre-frequency error df shifts the image along the readout by df / (bandwidth / Nread) pixels,
so the 20-kHz image moves twice as far as the 40-kHz one. Their relative shift d (in 40-kHz pixels)
gives df = d * (40 kHz / Nread). 2026-10-10: 0.2 px (fine). 2026-10-11: 9.1 px = 2.8 kHz (ss-MGOT failed).
Pass: |shift| < 0.5 px (|df| < ~150 Hz). The sign convention of df is not calibrated.
"""
import re
import sys
from pathlib import Path

import numpy as np
from skimage.registration import phase_cross_correlation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scanner/recon"))
from get_mrd_3d4 import get_mrd_3d4  # noqa: E402


def image(path):
    raw, dims, p = get_mrd_3d4(path)
    b = Path(path).read_bytes(); t = b[b.find(b":PPL"):].decode("latin-1")
    etl = int(p["views_per_seg"]); nav = int(re.search(r"^:VAR nav_on,\s*(\d+)", t, re.M)[1])
    if nav == 2:
        raise SystemExit("use nav_on 0/1 scans for this check")
    k = raw[0, 0, dims[2]//2, 0, nav*etl:]
    n = k.shape[0]; s = n//etl; v = s//2
    sh, e = np.arange(s)[:, None], np.arange(etl)[None, :]
    rows = (n//2 + sh - v + np.where(sh < v, -v*e, v*e)).ravel()
    kk = np.zeros_like(k); kk[rows] = k
    dwell = float(np.atleast_1d(p["sample_period"])[-1])
    return abs(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(kk)))), dwell


def main():
    (a, da), (b, db) = image(sys.argv[1]), image(sys.argv[2])
    if da < db:
        (a, da), (b, db) = (b, db), (a, da)
    shift = phase_cross_correlation(a, b, upsample_factor=20)[0]
    nread = a.shape[1]; bw_fast = 1e6/db
    df = shift[1]*bw_fast/nread
    print(f"20/40 kHz relative shift: readout {shift[1]:+.2f} px, phase-encode {shift[0]:+.2f} px")
    print(f"centre-frequency error ~ {abs(df):.0f} Hz -> {'PASS' if abs(shift[1]) < 0.5 else 'FAIL: re-set the centre frequency on the water peak'}")


if __name__ == "__main__":
    main()

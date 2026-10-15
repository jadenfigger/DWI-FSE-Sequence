"""Shared loader for the 2026-10-11 scans (v1.82 / v1.912 / v1.911, fixed rat brain in PBS).

Import from other oct11_* scripts:  from oct11_load import load_all, SCANS
Reads the MRDs read-only. Reconstruction is plain centric-reordered 2D FFT with no navigator
correction ('off'), the same primary mode as the Oct 10 analysis. The volume navigator train
(first ETL raw views, nav_on=1) is returned per volume/slice.

Orientation: image[row, col]; col = readout (logical x), row = phase encode (logical y).
Saved NIfTI volumes are the transpose of these arrays.
"""
from pathlib import Path
import ast, re, sys, hashlib
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scanner/recon'))
from get_mrd_3d4 import get_mrd_3d4  # noqa: E402

SRC = ROOT/'scanner/recon/bare_bones_recon_fse.py'
ns = dict(np=np, re=re)
_tree = ast.parse(SRC.read_text())
exec(compile(ast.Module(body=[n for n in _tree.body if isinstance(n, ast.FunctionDef)], type_ignores=[]), str(SRC), 'exec'), ns)

EXP = ROOT/'experiments'
# letter -> folder suffix. 'v1911_0' and 'v182 TT' / 'v1912 UU' are unplanned additions.
SCANS = {
    'A': 'v182_testA', 'B': 'v1912_testB', 'C': 'v182_testC', 'AB': 'v182_testAB', 'E': 'v182_testE', 'G': 'v182_testG',
    'I': 'v182_testI', 'M': 'v182_testM', 'N': 'v1912_testN', 'K': 'v182_testK', 'O': 'v182_testO', 'Q': 'v182_testQ',
    'S': 'v182_testS', 'T': 'v182_testT', 'TT': 'v182_testTT', 'U': 'v1912_testU', 'UU': 'v1912_testUU', 'V': 'v182_testV',
    '0': 'v1911_test0',
}
VERSION = {k: ('v1.912' if v.startswith('v1912') else 'v1.911' if v.startswith('v1911') else 'v1.82') for k, v in SCANS.items()}


def folder(letter):
    return EXP/f'FSE-DWI_10-11-2026_{SCANS[letter]}'


def header_text(mrd):
    b = Path(mrd).read_bytes()
    return b, b[b.find(b':PPL'):].decode('latin1')


def var(text, key, default=None):
    m = re.search(rf'^:VAR\s+{re.escape(key)},\s*(-?[\d.]+)', text, re.M)
    return float(m.group(1)) if m else default


def load(letter, recon=True):
    f = folder(letter); mrd = next(f.glob('*.MRD'))
    binary, text = header_text(mrd)
    raw, dims, params = get_mrd_3d4(mrd)
    E, S, V, nsamp = dims[0], dims[2], dims[4], dims[5]
    L = int(var(text, 'views_per_seg', params['views_per_seg'])); nav = int(var(text, 'nav_on', 0))
    N = V-nav*L; pe = int(var(text, 'PE_order'))
    rows = ns['pe_rows'](N, L, pe)
    n = int(var(text, 'no_diff_acq', E))
    b = ns['ppr_array'](text, 'acq_b')[:n]
    vec = np.stack([ns['ppr_array'](text, f'acq_{a}')[:n] for a in 'xyz'], 1)/1000.0
    ppl = re.search(r'^:PPL\s+(.*)$', text, re.M).group(1).strip()
    gains = {k: float(re.search(rf'^:_{fld}\s+(-?[\d.]+)', text, re.M).group(1))
             for k, fld in [('rx', 'ObserveReceiverGain'), ('tx', 'ObserveTransmitGain'), ('decouple', 'DecoupleTransmitGain')]}
    sp = np.atleast_1d(params['sample_period'])
    s = dict(letter=letter, folder=f, mrd=mrd, text=text, dims=dims, E=E, S=S, N=N, L=L, nav=nav, nsamp=nsamp, pe=pe, rows=rows,
             b=b, vec=vec, ppl=ppl, version=VERSION[letter], gains=gains, dwell_us=float(sp[-1]),
             esp=var(text, 'esp'), te=var(text, 'te'), tr=var(text, 'tr'), big_delta_ms=var(text, 'big_delta')/1000,
             offsets_mm=[float(x) for x in ns['read_slice_offsets'](text)], fov_mm=ns['read_geometry'](text)[0],
             mrd_sha256=hashlib.sha256(binary).hexdigest(), raw=raw[:, 0, :, 0])
    if recon:
        img = np.zeros((E, S, N, nsamp)); kimg = np.zeros((E, S, N, nsamp), complex); navs = np.zeros((E, S, L, nsamp), complex)
        for e in range(E):
            for sl in range(S):
                k = s['raw'][e, sl]
                kk = np.zeros((N, nsamp), complex); kk[rows] = k[nav*L:]
                kimg[e, sl] = kk
                img[e, sl] = abs(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(kk))))
                if nav:
                    navs[e, sl] = k[:L]
        s.update(img=img, kspace=kimg, navs=navs)
    return s


def load_all(recon=True):
    return {k: load(k, recon) for k in SCANS}


def direction_label(v):
    if not np.any(v):
        return '0'
    nz = np.flatnonzero(np.abs(v) > 1e-6)
    if len(nz) > 1:
        return '(' + ','.join(f'{x:+.2f}' for x in v) + ')'
    return ('-' if v[nz[0]] < 0 else '+') + 'xyz'[nz[0]]

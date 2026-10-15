"""Shared loader for the 2026-10-12 scans (v1.83 / v1.912 FSE and the lab EPI; ex-vivo rat brain
in PBS with the volume coil, then in-vivo rat brain with the surface coil).

Import from other oct12_* scripts:  from oct12_load import load, SCANS, EPI_SCANS
Reads the MRDs read-only. FSE reconstruction is plain centric-reordered 2D FFT. Three variants:
  'off'   : no navigator correction (primary, same as the Oct 10/11 analyses)
  'shot'  : nav_on=2 per-shot constant+linear phase correction (shot_navigator.correct_shot_phase)
The volume navigator train (first ETL raw views; nav_on 1 and 2) is returned per volume/slice,
and for nav_on=2 the per-shot navigator echo (one unencoded echo after each imaging shot).

Orientation: image[row, col]; col = readout (logical x), row = phase encode (logical y).
"""
from pathlib import Path
import ast, re, sys, hashlib
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scanner/recon'))
from get_mrd_3d4 import get_mrd_3d4  # noqa: E402
from shot_navigator import split_mode2, correct_shot_phase  # noqa: E402

SRC = ROOT/'scanner/recon/bare_bones_recon_fse.py'
ns = dict(np=np, re=re)
_tree = ast.parse(SRC.read_text())
exec(compile(ast.Module(body=[n for n in _tree.body if isinstance(n, ast.FunctionDef)], type_ignores=[]), str(SRC), 'exec'), ns)

EXP = ROOT/'experiments'
# key -> folder name (FSE). Ex-vivo first (volume coil), in-vivo (surface coil) last.
SCANS = {
    'A': 'FSE-DWI_10-12-2026_v183_testA', 'B': 'FSE-DWI_10-12-2026_v183_testB',
    'C': 'FSE-DWI_10-12-2026_v1912_testC',
    'D': 'FSE-DWI_10-12-2026_v183_testD', 'E': 'FSE-DWI_10-12-2026_v183_testE',
    'F': 'FSE-DWI_10-12-2026_v183_testF', 'G': 'FSE-DWI_10-12-2026_v183_testG',
    'M': 'FSE-DWI_10-12-2026_v183_testM', 'MM': 'FSE-DWI_10-12-2026_v183_testMM',
    'N': 'FSE-DWI_10-12-2026_v183_testN',
    'O': 'FSE-DWI_10-12-2026_v1912_testO',
    'Q': 'FSE-DWI_10-12-2026_v183_testQ', 'Q1': 'FSE-DWI_10-12-2026_v183_testQ1',
    'QQ': 'FSE-DWI_10-12-2026_v183_testQQ', 'QQQ': 'FSE-DWI_10-12-2026_v183_testQQQ',
    'R': 'FSE-DWI_10-12-2026_v1912_testR',
    'iA': 'FSE-DWI_10-12-2026_v183_invivoA', 'iB': 'FSE-DWI_10-12-2026_v1912_invivoB',
    'iC': 'FSE-DWI_10-12-2026_v1912_invivoC', 'iD': 'FSE-DWI_10-12-2026_v183_invivoD',
    'iE': 'FSE-DWI_10-12-2026_v183_invivoE', 'iF': 'FSE-DWI_10-12-2026_v183_invivoF',
}
EPI_SCANS = {'epi0': 'EPI-DWI_10-12-2026_test0', 'epiA': 'EPI-DWI_10-12-2026_invivoA'}


def folder(key):
    return EXP/(SCANS.get(key) or EPI_SCANS[key])


def mrd_path(key):
    f = folder(key)
    c = [p for p in f.glob('*.MRD') if not p.stem.endswith('_o')]
    return c[0] if c else None


def header_text(mrd):
    b = Path(mrd).read_bytes()
    return b, b[b.find(b':PPL'):].decode('latin1')


def var(text, key, default=None):
    m = re.search(rf'^:VAR\s+{re.escape(key)},\s*(-?[\d.]+)', text, re.M)
    return float(m.group(1)) if m else default


def version_of(ppl):
    m = re.search(r'twoTE-(\d\.\d+)\.ppl', ppl)
    return ('v' + m.group(1)) if m else ('EPI' if 'epi' in ppl.lower() else ppl)


def load(key, recon=True, shot_mode='constant+linear'):
    mrd = mrd_path(key)
    binary, text = header_text(mrd)
    raw, dims, params = get_mrd_3d4(mrd)
    E, S, V, nsamp = dims[0], dims[2], dims[4], dims[5]
    nav = int(var(text, 'nav_on', 0))
    vps = int(var(text, 'views_per_seg', params['views_per_seg']))
    L = vps - 1 if nav == 2 else vps
    N = (V // (L + 1) - 1) * L if nav == 2 else V - nav * L
    pe = int(var(text, 'PE_order'))
    rows = ns['pe_rows'](N, L, pe)
    n = int(var(text, 'no_diff_acq', E))
    b = ns['ppr_array'](text, 'acq_b')[:n]
    vec = np.stack([ns['ppr_array'](text, f'acq_{a}')[:n] for a in 'xyz'], 1)/1000.0
    ppl = re.search(r'^:PPL\s+(.*)$', text, re.M).group(1).strip()
    def g(fld):
        m = re.search(rf'^:_{fld}\s+(-?[\d.]+)', text, re.M)
        return float(m.group(1)) if m else None
    gains = dict(rx=g('ObserveReceiverGain'), tx=g('ObserveTransmitGain'))
    sp = np.atleast_1d(params['sample_period'])
    offs = ns['read_slice_offsets'](text)
    m_ro = re.search(r':FOV_READ_OFF\s+\w+,\s*\d+,\s*(-?\d+)', text)
    m_po = re.search(r':FOV_PHASE_OFF\s+\w+,\s*\d+,\s*(-?\d+)', text)
    s = dict(key=key, folder=folder(key), mrd=mrd, text=text, dims=dims, E=E, S=S, V=V, N=N, L=L, nav=nav,
             nsamp=nsamp, pe=pe, rows=rows, b=b, vec=vec, ppl=ppl, version=version_of(ppl), gains=gains,
             dwell_us=float(sp[-1]), esp=var(text, 'esp'), te=var(text, 'te'), tr=var(text, 'tr'),
             big_delta_ms=(var(text, 'big_delta') or 0)/1000, small_delta_ms=(var(text, 'sm_delta') or 0)/1000,
             offsets_mm=[float(x) for x in offs], fov_mm=ns['read_geometry'](text)[0],
             thickness_mm=ns['read_thickness'](text),
             fov_read_off_dac=int(m_ro.group(1)) if m_ro else 0, fov_phase_off_dac=int(m_po.group(1)) if m_po else 0,
             phmode=var(text, 'v183_phmode'), phcal=var(text, 'v183_phcal'),
             mrd_sha256=hashlib.sha256(binary).hexdigest(), raw=raw[:, 0, :, 0])
    if recon:
        img = np.zeros((E, S, N, nsamp)); kimg = np.zeros((E, S, N, nsamp), complex)
        navs = np.zeros((E, S, L, nsamp), complex)
        img_shot = None; shot_navs = None; shot_qa = []
        if nav == 2:
            img_shot = np.zeros_like(img); shot_navs = np.zeros((E, S, N//L, nsamp), complex)
        for e in range(E):
            for sl in range(S):
                k = s['raw'][e, sl]
                if nav == 2:
                    vnav, k_img, snav = split_mode2(k, L, N)
                    navs[e, sl] = vnav; shot_navs[e, sl] = snav
                    kc, qa = correct_shot_phase(k_img, snav, L, shot_mode)
                    qa.update(Experiment=e, Slice=sl); shot_qa.append(qa)
                    kk2 = np.zeros((N, nsamp), complex); kk2[rows] = kc
                    img_shot[e, sl] = abs(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(kk2))))
                else:
                    k_img = k[nav*L:]
                    if nav:
                        navs[e, sl] = k[:L]
                kk = np.zeros((N, nsamp), complex); kk[rows] = k_img
                kimg[e, sl] = kk
                img[e, sl] = abs(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(kk))))
        s.update(img=img, kspace=kimg, navs=navs, img_shot=img_shot, shot_navs=shot_navs, shot_qa=shot_qa)
    return s


def load_epi_nifti(key):
    """Vendor-reconstructed EPI magnitude (the _o.nii.gz written by the console)."""
    import nibabel as nib
    f = next(folder(key).glob('*_o.nii.gz'))
    im = nib.load(str(f))
    return np.asarray(im.dataobj).astype(float), im


def load_epi(key):
    """Lab EPI (16-shot interleaved, 8 echoes/shot, 200 kHz). Plain 2D FFT of the vendor-processed
    k-space (<stem>_o.MRD: regridded/ghost-corrected, 128 PE x 168 read, k-centre at PE row 28),
    no apodisation, so the background is ordinary Rician noise. Returns complex images (E,S,128,168)
    and a magnitude copy resampled to the FSE 128x128 grid (read axis 168 -> 128 by linear interp).
    Directions/b-values decoded from b_steps_array / diff_grad_dir (the vendor btable lists +x for all)."""
    from scipy import ndimage as ndi
    f = folder(key)
    raw, dims, _ = get_mrd_3d4(next(f.glob('*_o.MRD')))
    k = raw[:, 0, :, 0]
    cimg = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(k, axes=(-2, -1))), axes=(-2, -1))
    cimg = cimg[..., ::-1]   # read axis reversed vs the FSE/vendor display (verified: r=0.99 after flip, 0 px PE shift)
    mag = np.abs(cimg)
    E, S, ny, nx = mag.shape
    img128 = np.stack([[ndi.zoom(mag[e, s], (1, 128/nx), order=1) for s in range(S)] for e in range(E)])
    _, text = header_text(mrd_path(key))
    nb = int(var(text, 'no_b_steps'))
    b = ns['ppr_array'](text, 'b_steps_array')[:nb]
    dg = ns['ppr_array'](text, 'diff_grad_dir')
    vec = dg[:3*nb].reshape(nb, 3)/1000.0
    sp = np.atleast_1d(get_mrd_3d4(mrd_path(key))[2]['sample_period'])
    return dict(key=key, cimg=cimg, mag=mag, img=img128, b=b, vec=vec, text=text, E=E, S=S,
                te=var(text, 'te'), tr=var(text, 'tr'), big_delta_ms=var(text, 'big_delta')/1000,
                small_delta_ms=var(text, 'sm_delta')/1000, offsets_mm=[float(x) for x in ns['read_slice_offsets'](text)],
                thickness_mm=ns['read_thickness'](text), shots=16, echoes_per_shot=8, read_px=nx)


def direction_label(v):
    if not np.any(v):
        return '0'
    nz = np.flatnonzero(np.abs(v) > 1e-6)
    if len(nz) > 1:
        return '(' + ','.join(f'{x:+.2f}' for x in v) + ')'
    return ('-' if v[nz[0]] < 0 else '+') + 'xyz'[nz[0]]

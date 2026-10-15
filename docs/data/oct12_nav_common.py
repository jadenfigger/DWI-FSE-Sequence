"""Shared helpers for the 2026-10-12 navigator / ghosting / per-echo-ADC analysis (see oct12_navigators.py).

Everything reads the MRDs read-only through docs/data/oct12_load.py. Scan N (v1.83, nav_on=2) needs a different raw-view
layout than the one the loader/recon assume; `load_scan('N')` applies the layout recovered from the data (see
oct12_navigators.py, section 1):

  * the MRD holds 4 x 153 view slots but the scanner only wrote 4 x 119 views (17 shots x 7 echoes per volume, contiguous
    across volumes, then zeros), so volume j = stream[119 j : 119 (j+1)];
  * per volume: views 0..6 = unencoded volume-navigator train (7 echoes), then 16 imaging shots x 7 echoes;
  * each shot wrote its first 7 imaging echoes from the planned 8-echo table. Their rows are
    pe_rows(128, 8, 1).reshape(16, 8)[:, :7].ravel(); the omitted 8th echo leaves 16 zero-filled ky rows.
    This line order equals pe_rows(112, 7, 1) after subtracting a common 8-row offset. The sparse 128-row grid keeps
    scanner/header coordinates; a 112-row compact FFT represents a different sampled FOV and needs explicit rescaling.
"""
import sys
from pathlib import Path
import numpy as np
from scipy import ndimage

DATA = Path(__file__).resolve().parent
ROOT = DATA.parents[1]
sys.path.insert(0, str(DATA))
from oct12_load import load, ns, direction_label, SCANS  # noqa: E402,F401
from shot_navigator import split_mode2, correct_shot_phase, readout_projection  # noqa: E402,F401

FIG = ROOT/'docs/figures/physical_scanner_2026-10-12'
FIG.mkdir(parents=True, exist_ok=True)

EXVIVO = ['M', 'N', 'O', 'Q', 'Q1', 'R', 'C']
INVIVO = ['iA', 'iB', 'iC', 'iD', 'iE', 'iF']
N_STORED, N_ETL, N_ACQUIRED_LINES, N_LINES = 119, 7, 112, 128


def nav2_imaging_rows():
    """PE rows present in v1.83 nav-mode-2 scan N's seven acquired echoes per 8-echo shot."""
    table = ns['pe_rows'](N_LINES, 8, 1).reshape(16, 8)
    return table[:, :N_ETL].ravel()


def fft_img(kk):
    return np.abs(np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(kk))))


def load_scan(key):
    """load() with the recovered raw layout for scan N (all other scans unchanged)."""
    if key != 'N':
        return load(key)
    s = load('N', recon=False)
    E, S, nsamp = s['E'], s['S'], s['nsamp']
    flat = s['raw'][:, 0].reshape(-1, nsamp)[:E*N_STORED].reshape(E, N_STORED, nsamp)
    rows = nav2_imaging_rows()
    navs = np.zeros((E, 1, N_ETL, nsamp), complex)
    kimg = np.zeros((E, 1, N_LINES, nsamp), complex)
    img = np.zeros((E, 1, N_LINES, nsamp))
    for e in range(E):
        navs[e, 0] = flat[e, :N_ETL]
        kimg[e, 0][rows] = flat[e, N_ETL:]
        img[e, 0] = fft_img(kimg[e, 0])
    s.update(raw=flat[:, None], V=N_STORED, N=N_LINES, L=N_ETL, nav=1, rows=rows, navs=navs, kspace=kimg, img=img,
             img_shot=None, shot_navs=None, shot_qa=[], nav_requested=2)
    return s


def centre_slice(s):
    """Index of the slice closest to isocentre (offset 0 where present)."""
    off = np.asarray(s['offsets_mm'] if len(s['offsets_mm']) == s['S'] else np.zeros(s['S']), float)
    return int(np.argmin(np.abs(off)))


def slice_offset(s, sl):
    off = s['offsets_mm']
    return float(off[sl]) if len(off) == s['S'] else 0.0


# ---------------------------------------------------------------- noise
def outer_noise_power(s):
    """Noise power per complex k-space sample (E|n|^2): median |k|^2 over the 16x16-sample outer corners / ln 2, per
    volume and slice; the scan value is the median (same definition as oct11_navigator_analysis.py)."""
    k = s['kspace']; N, n = k.shape[2], k.shape[3]
    rows = np.r_[0:16, N-16:N]; cols = np.r_[0:16, n-16:n]
    p = np.abs(k[:, :, rows][:, :, :, cols])**2
    est = np.median(p.reshape(p.shape[0], p.shape[1], -1), axis=2)/np.log(2)
    return float(np.median(est)), est


# ---------------------------------------------------------------- masks / ghosts
def sigma_img_from_k(k):
    """Per-component image-domain noise SD from the k-space periphery (as oct11_roi_analysis.sigma_img)."""
    n, m = k.shape; r = np.r_[0:n//16, n-n//16:n]; c = np.r_[0:m//16, m-m//16:m]
    return float(np.sqrt(np.mean(abs(k[np.ix_(r, c)])**2)/2)/np.sqrt(n*m))


def object_mask(im, sigma_noise=None, frac=0.2, smooth=1.5, snr_floor=2.5):
    """Largest connected blob of the smoothed image above max(frac * p99, snr_floor * sigma_noise), holes filled.
    Empty when nothing stands out of the noise."""
    sm = ndimage.gaussian_filter(im, smooth)
    thr = frac*np.percentile(sm, 99)
    if sigma_noise is not None:
        thr = max(thr, snr_floor*sigma_noise)
    m = ndimage.binary_fill_holes(sm > thr)
    lab, k = ndimage.label(m)
    if k > 1:
        m = lab == (1+np.argmax(ndimage.sum(m, lab, range(1, k+1))))
    return m


def ghost_metrics(im, own_mask, excl_mask, dil_frac=0.04, min_px=40, min_obj=12):
    """Phase-encode ghost metric and readout control for one magnitude image (rows = phase encode, cols = readout).

    excl_mask is the object that defines the zones: 'ref' variant = own mask U the b10 mask of the same slice (outside the
    whole tube / head); 'own' variant = the volume's own mask only (at b >= 3000 in the ex-vivo tube the PBS is gone, so the
    tube interior beside the brain is a valid ghost zone).
    PE zone : pixels in the columns that span excl_mask, outside its dilation (4 % of the rows).
    RO zone : pixels in the rows that span excl_mask, outside its dilation (beside the object along readout = control).
    ghost_pe / ghost_ro = mean |I| in the zone / mean |I| over the volume's own object mask;
    ghost_excess        = (mean PE zone - mean RO zone) / mean object (noise-subtracted);
    ghost_p90_excess    = (90th percentile PE zone - 90th percentile RO zone) / mean object (sensitive to localised ghosts);
    ghost_rms_excess    = sqrt(max(mean PE^2 - mean RO^2, 0)) / rms object.
    """
    n, m = im.shape
    union = excl_mask
    nan = np.nan
    empty = dict(n_pe_px=0, n_ro_px=0, n_obj_px=int(own_mask.sum()), obj_mean=float(im[own_mask].mean()) if own_mask.any() else nan,
                 ghost_pe=nan, ghost_ro=nan, ghost_excess=nan, ghost_p90_excess=nan, ghost_rms_excess=nan, ghost_excess_se=nan)
    if not union.any() or own_mask.sum() < min_obj:
        return empty
    dil = ndimage.binary_dilation(union, iterations=max(1, int(round(dil_frac*n))))
    cols = np.flatnonzero(union.any(0)); rws = np.flatnonzero(union.any(1))
    pe = np.zeros_like(union); pe[:, cols.min():cols.max()+1] = True; pe &= ~dil
    ro = np.zeros_like(union); ro[rws.min():rws.max()+1, :] = True; ro &= ~dil
    out = dict(n_pe_px=int(pe.sum()), n_ro_px=int(ro.sum()), n_obj_px=int(own_mask.sum()))
    if pe.sum() < min_px or ro.sum() < min_px:
        empty.update(n_pe_px=int(pe.sum()), n_ro_px=int(ro.sum()))
        return empty
    obj = float(im[own_mask].mean()); rms_obj = float(np.sqrt(np.mean(im[own_mask]**2)))
    mpe, mro = float(im[pe].mean()), float(im[ro].mean())
    sig = mro/1.2533                                           # Rayleigh mean = 1.2533 sigma
    se = 0.655*sig*np.sqrt(1/pe.sum()+1/ro.sum())/obj            # SE of a noise-only difference (ignores correlation)
    out.update(obj_mean=obj, ghost_pe=mpe/obj, ghost_ro=mro/obj, ghost_excess=(mpe-mro)/obj,
               ghost_p90_excess=float((np.percentile(im[pe], 90)-np.percentile(im[ro], 90))/obj),
               ghost_rms_excess=float(np.sqrt(max(np.mean(im[pe]**2)-np.mean(im[ro]**2), 0))/rms_obj), ghost_excess_se=float(se))
    return out


# ---------------------------------------------------------------- per-shot recon variants (nav_on = 2)
def recon_shot_variant(s, e, sl, mode='constant+linear', **kw):
    """Per-shot corrected image + QA for volume e, slice sl (scan with nav_on=2 and the standard layout)."""
    L, N, nsamp = s['L'], s['N'], s['nsamp']
    vnav, k_img, snav = split_mode2(s['raw'][e, sl], L, N)
    kc, qa = correct_shot_phase(k_img, snav, L, mode, **kw)
    kk = np.zeros((N, nsamp), complex); kk[s['rows']] = kc
    return fft_img(kk), qa


# ---------------------------------------------------------------- navigator echo statistics
def echo_stats(nav, sigma2):
    """nav: (E, nsamp) complex k-space lines. Noise-subtracted amplitude etc. (definitions as oct11_navigator_analysis)."""
    nsamp = nav.shape[1]
    p = np.abs(nav)**2
    tot = p.sum(1)
    excess = tot-nsamp*sigma2
    amp = np.sqrt(np.maximum(excess, 0.0))
    ip = nav @ nav[0].conj()
    dc = nav.sum(1)
    # SD of the energy estimate for signal energy S2 in complex Gaussian noise: Var = N sigma^4 + 2 sigma^2 S2
    sd_energy = np.sqrt(nsamp*sigma2**2+2*sigma2*np.maximum(excess, 0))
    sd_amp = np.where(amp > 0, sd_energy/(2*np.maximum(amp, 1e-12)), np.sqrt(sd_energy))
    return dict(norm=np.sqrt(tot), amp=amp, sd_amp=sd_amp, snr=amp/np.sqrt(sigma2),
                ip_phase=np.degrees(np.angle(ip)), dc_phase=np.degrees(np.angle(dc*np.conj(dc[0]))), peak=np.argmax(np.abs(nav), axis=1))


def wrap(x):
    return (np.asarray(x, float)+180.0) % 360.0-180.0


def fit_ramp_alternation(ip_deg):
    """phi_e = a + s*e + h*(-1)^e (e = 0..E-1): grid-search h, unwrap, fit ramp (as oct11_slice_phase.py).
    Returns ramp deg/echo, half alternation deg, rms residual deg."""
    ph = np.radians(np.asarray(ip_deg, float)); E = len(ph); e = np.arange(E)
    best = None
    A = np.stack([np.ones(E), e], 1)
    for h in np.radians(np.arange(-90, 91, 1)):
        u = np.unwrap(ph-h*(-1.0)**e)
        p, *_ = np.linalg.lstsq(A, u, rcond=None)
        res = float(np.sqrt(np.mean((u-A@p)**2)))
        if best is None or res < best[0]:
            best = (res, h, p)
    res, h, p = best
    return float(np.degrees(p[1])), float(np.degrees(h)), float(np.degrees(res))


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return jsonable(o.tolist())
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (int, np.integer)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return float(o) if np.isfinite(o) else None
    return o

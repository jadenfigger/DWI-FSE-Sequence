"""Reproduce Oct 10 scan measurements (v1.81 / v1.911 first scanner acquisitions).

Run: python docs/data/physical_scanner_analysis_2026-10-10.py [--metrics-only]
Reads the original acquisitions without modification. Reconstruction function
definitions are loaded from scanner/recon/bare_bones_recon_fse.py without its
executable driver (same method as the Oct 7 analysis). Primary comparisons use
uncorrected complex k-space ('off'); navigator corrections are explicit ablations
and are used only to reproduce the saved NIfTI images.

Differences from the Oct 7 script: multi-slice (scan K), 8-volume direction scans,
per-scan sample period (scan J), gains are read and recorded rather than asserted,
ROI is the Oct 10 phantom (measured, see ROI constants), an edge-line ROI for the
thin bright line on the upper-left phantom boundary, per-echo navigator tables,
and noise-floor-subtracted navigator amplitudes.
Attenuation/ADC fits live in docs/data/oct10_attenuation_analysis.py.

Orientation: every array here is image[row, col]. Following the Oct 7 script,
x is the column index (readout / ADC-sample axis), y is the row index
(phase-encode axis). The saved NIfTI volumes are the transpose of these arrays.
"""
from pathlib import Path
import ast, re, sys, json, csv, hashlib, io, importlib.util
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import ndimage
import nibabel as nib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scanner/recon'))
from get_mrd_3d4 import get_mrd_3d4
SRC = ROOT/'scanner/recon/bare_bones_recon_fse.py'
ns = dict(np=np, re=re)
tree = ast.parse(SRC.read_text())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)], type_ignores=[]), str(SRC), 'exec'), ns)
OUT = ROOT/'docs/figures/physical_scanner_2026-10-10'
DATA = ROOT/'docs/data'
# letter -> folder suffix (version tag as written in the folder name)
LETTERS = {'A': 'v181_testA', 'B': 'v1911_testB', 'C': 'v18_testC', 'D': 'v191_testD', 'E': 'v181_testE', 'G': 'v1911_testG',
           'H': 'v181_testH', 'I': 'v1911_testI', 'J': 'v181_testJ', 'K': 'v181_testK'}
NAMES = list(LETTERS)
MODES = ('off', 'deramp_mag', 'deramp')
LABELS = {'off': 'No correction', 'deramp_mag': 'Amplitude only', 'deramp': 'Amplitude + phase'}
VERSION = {'A': 'v1.81', 'B': 'v1.911', 'C': 'v1.8', 'D': 'v1.91', 'E': 'v1.81', 'G': 'v1.911', 'H': 'v1.81', 'I': 'v1.911', 'J': 'v1.81', 'K': 'v1.81'}
SEQ = {'A': 'v181', 'B': 'v1911', 'C': 'v18', 'D': 'v191', 'E': 'v181', 'G': 'v1911', 'H': 'v181', 'I': 'v1911', 'J': 'v181', 'K': 'v181'}
SHORT = {'A': 'v1.81 7b', 'B': 'v1.911 7b', 'C': 'v1.8 7b', 'D': 'v1.91 7b', 'E': 'v1.81 dirs', 'G': 'v1.911 dirs', 'H': 'v1.81 crush-eq-selector',
         'I': 'v1.911 delta30/TE44', 'J': 'v1.81 40 kHz', 'K': 'v1.81 3-slice 40 kHz'}

# ---- Fixed ROIs (Oct 10 phantom). Coordinates are (x=column, y=row) of image[row, col]. ----
# Phantom: bright disk, equivalent radius 47 px, centroid (61.1, 73.2) of the >45%-of-max region in every scan.
ROI = dict(cx=61.0, cy=73.0, r_int=34, rim=(41, 47), outside=(53, 60))
BACKGROUND = 'y<20 and (x<16 or x>=112)'
# Thin bright line on the upper-left phantom boundary: least-squares line col = a + m*row through the per-row peak centroid
# of the b1000 images (rows 36-58, max residual 0.7 px). ROI = pixels within hw of the line for rows 37..56;
# reference = parallel strip 4..7 px toward the interior (+x side).
EDGE_LINE = dict(col_intercept=55.95035, col_slope=-0.678666, rows=(37, 56), half_width=1.0, ref_offset=(4.0, 7.0), line_zone_x=(17, 33), nav_ref_zone_x=(40, 100))
STREAK = dict(half_angle_deg=4.0, radius=(12, 60))
NSAMP = 128

# ---- Modeled effective b (docs/v181_v1911/FINAL_REPORT.md section 8; E1..E8 trace, diffusion +X) ----
BEFF_TABLE = {
    'v18': {0: [12.03, 14.69, 17.44, 20.28, 23.27, 26.42, 29.80, 33.40], 100: [165.03, 167.70, 170.44, 173.28, 176.27, 179.43, 182.80, 186.40],
            1000: [1175.93, 1178.60, 1181.35, 1184.19, 1187.18, 1190.33, 1193.70, 1197.31], 6000: [6398.16, 6400.82, 6403.57, 6406.41, 6409.40, 6412.55, 6415.92, 6419.53]},
    'v181': {0: [4.00, 6.67, 9.42, 12.26, 15.25, 18.40, 21.77, 25.38], 100: [104.05, 106.72, 109.46, 112.30, 115.29, 118.45, 121.82, 125.42],
             1000: [1000.71, 1003.38, 1006.12, 1008.97, 1011.95, 1015.11, 1018.48, 1022.08], 6000: [5980.67, 5983.34, 5986.09, 5988.93, 5991.92, 5995.07, 5998.44, 6002.05]},
    'v191': {0: [20.30, 30.97, 43.41, 55.01, 66.93, 79.61, 91.15, 105.04], 100: [120.10, 130.77, 143.21, 154.81, 166.73, 179.40, 190.95, 204.83],
             1000: [1014.55, 1025.21, 1037.65, 1049.25, 1061.18, 1073.85, 1085.39, 1099.28], 6000: [5982.20, 5992.87, 6005.31, 6016.91, 6028.83, 6041.51, 6053.05, 6066.93]},
    'v1911': {0: [20.44, 31.62, 44.40, 56.46, 68.78, 81.86, 93.86, 108.09], 100: [120.23, 131.41, 144.20, 156.26, 168.58, 181.66, 193.65, 207.89],
              1000: [1014.68, 1025.86, 1038.64, 1050.70, 1063.02, 1076.10, 1088.10, 1102.33], 6000: [5982.33, 5993.51, 6006.30, 6018.36, 6030.68, 6043.76, 6055.75, 6069.99]}}
# Decomposition at E1 (v1.8 / v1.81): diffusion lobes alone are b*f with f from the table below; cross term scales as sqrt(b).
LOBE_KNOTS = ([0, 100, 1000, 6000], [1.0, 99.97/100, 996.47/1000, 5976.08/6000])
CROSS_X = {'v18': 167.45, 'v181': 0.25}      # s/mm2 at nominal b1000, +x (read) diffusion
Z_CROSS = 37.3                                # s/mm2 at nominal b1000, slice-direction diffusion (report: 37.3 / 91.2 at b1000 / b6000)
B_ASSUMPTIONS = ('E1 b(b_nominal) = lobes(b) + self + cross(b) for v1.8/v1.81, with lobes = b*f(b) (f piecewise-linear between the 100/1000/6000 '
                 'knots of 0.9997/0.99647/0.99601), self = table b0 row, cross = c*sqrt(b/1000) (c = 167.45 or 0.25 for +x; sign flipped for -x on v1.8; '
                 'absent for y; slice direction adds +37.3*sqrt(b/1000) on both). v1.91/v1.911: dev(b)=b_eff-b is fitted as s+alpha*b+beta*sqrt(b) to the '
                 'four E1 table rows (residual reported by beff_fit_residuals). Echo e adds the b-independent offset (b0 row echo e - echo 1). '
                 'Slice-direction cross term for v1.911 and y/-x terms for v1.911 are NOT in the report: assumed equal to the +x row / v1.81 value. '
                 'Delta30 (scan I), 40 kHz readout (J, K) are not modeled: Delta40 / 50 us tables are used.')


def _dev_fit(seq):
    tab = BEFF_TABLE[seq]; bs = np.array([0, 100, 1000, 6000], float); dev = np.array([tab[int(b)][0]-b for b in bs])
    A = np.stack([np.ones(4), bs, np.sqrt(bs)], 1)
    p, *_ = np.linalg.lstsq(A, dev, rcond=None)
    return p, float(np.abs(A@p-dev).max())


def beff_fit_residuals():
    return {seq: _dev_fit(seq)[1] for seq in ('v191', 'v1911')}


def effective_b(seq, b, direction='x', echo=1):
    """Modeled trace b (s/mm2) for nominal b, direction in {'x','-x','y','z'}, 1-based echo (see B_ASSUMPTIONS)."""
    b = np.asarray(b, float); tab = BEFF_TABLE[seq]
    if seq in ('v18', 'v181'):
        sign = {'x': 1, '-x': -1 if seq == 'v18' else 1, 'y': 0, 'z': 0}[direction]
        e1 = b*np.interp(b, *LOBE_KNOTS) + tab[0][0] + sign*CROSS_X[seq]*np.sqrt(b/1000)
    else:
        p, _ = _dev_fit(seq)
        e1 = b + p[0] + p[1]*b + p[2]*np.sqrt(b)
        e1 = np.where(b == 0, tab[0][0], e1)
    if direction == 'z':
        e1 = e1 + Z_CROSS*np.sqrt(b/1000)
    return e1 + (tab[0][echo-1]-tab[0][0])


# ---- Predicted v1.911 / v1.91 coherent wanted-echo ratio, FINAL_REPORT section 10 (E1..E8) ----
BD_PRED = {'T2_32_D002_grid': [1.0315, 1.0529, 1.0802, 1.0972, 1.1159, 1.1329, 1.1488, 1.1652],
           'T2_32_D0': [1.0317, 1.0488, 1.0742, 1.0877, 1.1042, 1.1156, 1.1290, 1.1371],
           'T2_60_D002': [1.0165, 1.0301, 1.0453, 1.0571, 1.0694, 1.0806, 1.0910, 1.1018],
           'no_relax_D002': [0.9997, 1.0024, 1.0058, 1.0096, 1.0138, 1.0172, 1.0203, 1.0236]}


def save_figure(fig, path, dpi=120):
    out = io.BytesIO(); fig.savefig(out, format='png', dpi=dpi); path.write_bytes(out.getvalue()); plt.close(fig)


def read_header(mrd):
    binary = mrd.read_bytes()
    return binary, binary[binary.find(b':PPL'):].decode('latin1')


def navigator_metrics(lines, amp, ph, L, nsamp):
    norms = np.linalg.norm(lines, axis=1)
    coef = (lines @ lines[0].conj())/np.vdot(lines[0], lines[0]).real
    residual = np.linalg.norm(lines-coef[:, None]*lines[0], axis=1)/norms
    power = abs(lines)**2
    center = np.arange(56, 73); edge = np.r_[0:12, 116:128]; noise_window = np.r_[16:48, 80:112]
    noise = float(np.median(power[:, noise_window])/np.log(2))
    projection = np.fft.fftshift(np.fft.ifft(np.fft.ifftshift(lines, axes=1), axis=1), axes=1)
    refmag = abs(projection[0]); support = refmag > .25*refmag.max()
    shape_mag = np.linalg.norm(abs(projection)-np.linalg.norm(projection, axis=1)[:, None]/np.linalg.norm(projection[0])*refmag, axis=1)/norms*np.sqrt(nsamp)
    pixphase = np.angle(projection[:, support]*projection[0, support].conj())
    pixweight = abs(projection[:, support]*projection[0, support].conj())
    coherence = abs((pixweight*np.exp(1j*pixphase)).sum(1))/pixweight.sum(1)
    # sub-sample echo peak position (power-weighted centroid of 5 samples around the argmax)
    peaks = np.argmax(abs(lines), axis=1)
    frac = []
    for line, p in zip(abs(lines), peaks):
        lo, hi = max(p-2, 0), min(p+3, nsamp); w = line[lo:hi]**2
        frac.append(float((np.arange(lo, hi)*w).sum()/w.sum()))
    z0, z1 = EDGE_LINE['line_zone_x']; r0, r1 = EDGE_LINE['nav_ref_zone_x']
    zone = abs(projection[:, z0:z1+1])**2; ref = abs(projection[:, r0:r1+1])**2
    return dict(norm=norms.tolist(), ratio=amp.tolist(), phase_deg=np.degrees(ph).tolist(),
                inner_product_phase_deg=np.degrees(np.angle(coef)).tolist(), shape_residual=residual.tolist(),
                magnitude_projection_shape_residual=shape_mag.tolist(), projection_phase_coherence=coherence.tolist(),
                peak_sample=peaks.tolist(), peak_centroid=frac, noise_power_approx=noise,
                edge_excess=np.sqrt(np.maximum(power[:, edge].sum(1)-len(edge)*noise, 0)).tolist(),
                centre_excess=np.sqrt(np.maximum(power[:, center].sum(1)-len(center)*noise, 0)).tolist(),
                edge_power_fraction=(power[:, edge].sum(1)/power.sum(1)).tolist(),
                centre_power_fraction=(power[:, center].sum(1)/power.sum(1)).tolist(),
                proj_line_zone_rms=np.sqrt(zone.mean(1)).tolist(), proj_ref_zone_rms=np.sqrt(ref.mean(1)).tolist())


def load_scans():
    scans = {}
    for letter, tag in LETTERS.items():
        folder = next(p for p in (ROOT/'experiments').glob('FSE-DWI_10-10-2026_*') if p.name.endswith('_'+tag))
        mrd = next(folder.glob('*.MRD')); binary, header = read_header(mrd)
        gains = {key: float(re.search(rf'^:_{field}\s+(-?[\d.]+)', header, re.M).group(1)) for key, field in [('rx', 'ObserveReceiverGain'), ('tx', 'ObserveTransmitGain'), ('decouple', 'DecoupleTransmitGain')]}
        raw, dims, params = get_mrd_3d4(mrd)
        assert dims[1] == 1 and dims[3] == 1, (letter, dims)   # echoes, views_2
        E, S = dims[0], dims[2]
        var = lambda key, default=0: ns['ppr_var'](header, key, default)
        L = int(var('views_per_seg', params['views_per_seg'])); nav = int(var('nav_on')); N = dims[4]-nav*L; nsamp = dims[5]; pe = int(var('PE_order'))
        rows = ns['pe_rows'](N, L, pe)
        assert len(np.unique(rows)) == N and rows.min() == 0 and rows.max() == N-1
        b = ns['ppr_array'](header, 'acq_b')[:E]
        assert len(b) == E, (letter, b, dims)
        sp = np.atleast_1d(params['sample_period'])
        data = raw[:, 0, :, 0]  # (E, S, views, samples)
        images = {}; navigators = {}; corrections = {}
        for e in range(E):
            for sl in range(S):
                k = data[e, sl]; ims = {}; corrs = {}
                amp, ph, lines = ns['nav_envelope'](k, L)
                for mode in MODES:
                    corr = np.ones(N, dtype=complex) if mode == 'off' else ns['nav_correction'](amp, ph, np.arange(N) % L, rows, N, 'deramp', mode == 'deramp', .01, pe)
                    kk = np.zeros((N, nsamp), complex); kk[rows] = k[nav*L:]*corr[:, None]
                    ims[mode] = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(kk)))
                    corrs[mode] = corr
                images[(e, sl)] = ims; corrections[(e, sl)] = corrs
                navigators[(e, sl)] = navigator_metrics(lines, amp, ph, L, nsamp)
        nifti_errors = {}; niftimeta = None
        paths = list(folder.glob('*.nii.gz'))
        if paths:
            nii = nib.load(paths[0]); vol = nii.get_fdata()
            niftimeta = dict(shape=list(vol.shape), zooms=[float(z) for z in nii.header.get_zooms()])
            for mode in MODES:
                expected = np.stack([np.stack([abs(images[(e, sl)][mode]).T for sl in range(S)], axis=-1) for e in range(E)], axis=-1)
                assert expected.shape == vol.shape, (letter, expected.shape, vol.shape)
                nifti_errors[mode] = float(np.linalg.norm(vol-expected)/np.linalg.norm(vol))
        keys = ('crush_amp', 'diff_crush_amp', 'crusher_schedule', 'esp', 'te', 'tr', 'v19_on', 'big_delta', 'little_delta', 'tcrush', 'diff_tcrush')
        values = {key: var(key) for key in keys}
        values.update(sample_period_params=[float(x) for x in sp], dwell_us=float(sp[-1]) if len(sp) == 4 else None,
                      no_samples=nsamp, slice_offsets_mm=[float(x) for x in ns['read_slice_offsets'](header)],
                      fov_mm=ns['read_geometry'](header)[0], slice_separation_mm=ns['read_geometry'](header)[1], slice_thickness_mm=ns['read_thickness'](header))
        scans[letter] = dict(folder=folder, raw=data, header=header, images=images, b=b, L=L, nav=nav, N=N, pe=pe, rows=rows, dims=dims, E=E, S=S, nsamp=nsamp,
                             navigators=navigators, nifti_errors=nifti_errors, nifti=niftimeta, parameters=values, gains=gains,
                             mrd_sha256=hashlib.sha256(binary).hexdigest(), corrections=corrections,
                             bvec=np.loadtxt(next(folder.glob('*.bvec'))).reshape(3, -1).T)
    return scans


def bindex(s, b, direction=None):
    match = np.flatnonzero(s['b'] == b)
    if direction is not None:
        match = [m for m in match if np.allclose(s['bvec'][m], direction)]
    return int(match[0]) if len(match) else None


def direction_label(s, e):
    d = s['bvec'][e]
    if not d.any():
        return 'none'
    axis = 'xyz'[int(np.argmax(abs(d)))]
    return ('-' if d.sum() < 0 else '+')+axis


def direction_code(label):
    return {'+x': 'x', '-x': '-x', '+y': 'y', '+z': 'z', 'none': 'x'}[label]


def sorted_kspace(s, e, sl=0, mode='off'):
    k = np.zeros((s['N'], s['nsamp']), complex); k[s['rows']] = s['raw'][e, sl, s['nav']*s['L']:]*s['corrections'][(e, sl)][mode][:, None]
    if mode == 'off':
        assert np.isclose((abs(k)**2).sum(), (abs(s['raw'][e, sl, s['L']:].astype(complex))**2).sum(), rtol=1e-12)
    return k


def roi_masks():
    yy, xx = np.indices((128, 128)); radius = np.hypot(xx-ROI['cx'], yy-ROI['cy'])
    background = (yy < 20) & ((xx < 16) | (xx >= 112))
    hw = EDGE_LINE['half_width']; r0, r1 = EDGE_LINE['rows']; o0, o1 = EDGE_LINE['ref_offset']
    # signed perpendicular distance from the line col = a + m*row (positive toward +x, the phantom interior)
    d = (xx-EDGE_LINE['col_intercept']-EDGE_LINE['col_slope']*yy)/np.hypot(1, EDGE_LINE['col_slope'])
    inrows = (yy >= r0) & (yy <= r1)
    edge = (abs(d) <= hw) & inrows; ref = (d >= o0) & (d <= o1) & inrows
    rim = (radius >= ROI['rim'][0]) & (radius <= ROI['rim'][1])
    near_edge = (abs(d) <= hw+2) & (yy >= r0-3) & (yy <= r1+3)
    return dict(interior=radius <= ROI['r_int'], rim=rim, rim_excl_edge=rim & ~near_edge, background=background, edge_line=edge, edge_ref=ref,
                outside_ring=(radius >= ROI['outside'][0]) & (radius <= ROI['outside'][1]))


def noise_floors(scans):
    """Per-scan complex-sample noise power: median navigator-window estimate over volumes with b>=3000 (signal-free).
    K has no such volume (b1000 max): it takes J's value (same dwell 25 us, same gains, same acquisition session)."""
    floors = {}; sources = {}
    for n, s in scans.items():
        vals = [s['navigators'][(e, sl)]['noise_power_approx'] for e in range(s['E']) for sl in range(s['S']) if s['b'][e] >= 3000]
        if vals:
            floors[n] = float(np.median(vals)); sources[n] = f'median of {len(vals)} navigator-window estimates at b>=3000'
    floors['K'] = floors['J']; sources['K'] = 'borrowed from J (same dwell/gains; K has no b>=3000 volume)'
    return floors, sources


def image_metrics(im, masks):
    smooth = ndimage.gaussian_filter(im, 2)
    bg_power = float(np.mean(im[masks['background']]**2)); bg_rms = np.sqrt(bg_power)
    interior = im[masks['interior']]; mu = float(interior.mean()); power = float(np.mean(interior**2))
    hp = float(np.sqrt(np.mean((im-smooth)[masks['interior']]**2)))
    edge = im[masks['edge_line']]; ref = im[masks['edge_ref']]
    excess = lambda x: float(np.sqrt(max(np.mean(x**2)-bg_power, 0)))
    return dict(interior_mean=mu, interior_median=float(np.median(interior)), interior_rms=float(np.sqrt(power)), interior_excess_rms=excess(interior),
                rim_mean=float(im[masks['rim']].mean()), rim_excl_edge_mean=float(im[masks['rim_excl_edge']].mean()),
                edge_line_mean=float(edge.mean()), edge_line_max=float(edge.max()), edge_line_excess_rms=excess(edge), edge_ref_mean=float(ref.mean()), edge_ref_excess_rms=excess(ref),
                edge_line_over_ref=float(edge.mean()/ref.mean()), edge_line_over_interior=float(edge.mean()/mu),
                edge_line_over_background_mean=float(edge.mean()/im[masks['background']].mean()),
                background_mean=float(im[masks['background']].mean()), background_std=float(im[masks['background']].std()), background_rms=float(bg_rms),
                interior_over_background_rms=mu/float(bg_rms), outside_ring_mean=float(im[masks['outside_ring']].mean()),
                interior_smooth_cv=float(smooth[masks['interior']].std()/smooth[masks['interior']].mean()),
                interior_highpass_rms=hp, interior_highpass_over_mean=hp/mu, interior_cv=float(interior.std()/mu))


def streak_masks():
    v, u = np.indices((128, 128)); u = u-64.0; v = v-64.0; r = np.hypot(u, v); ang = np.degrees(np.arctan2(v, u))
    in_r = (r >= STREAK['radius'][0]) & (r <= STREAK['radius'][1])
    def wedge(center):
        diff = (ang-center+90) % 180-90      # lines through the origin: angle modulo 180
        return in_r & (abs(diff) <= STREAK['half_angle_deg'])
    normal = np.degrees(np.arctan2(-EDGE_LINE['col_slope'], 1.0))      # k-space direction normal to the image line (x=col, y=row)
    return dict(normal=wedge(normal), mirror=wedge(-normal), orthogonal=wedge(normal+90), normal_angle_deg=float(normal))


def kspace_metrics(k, floor_k, masks):
    p = abs(k)**2; total = float(p.sum()); edge = float(p[:, np.r_[0:12, 116:128]].sum()); centre = float(p[:, 56:73].sum())
    corner = p[np.r_[0:8, 120:128]][:, np.r_[0:8, 120:128]]
    noise = float(np.median(corner)/np.log(2))
    mean_n = float(p[masks['normal']].mean()); ctrl = float((p[masks['mirror']].mean()+p[masks['orthogonal']].mean())/2)
    return dict(total_power=total, total_l2=float(np.sqrt(total)), readout_edge_power_fraction=edge/total, readout_center_power_fraction=centre/total,
                central_ky_band_power_fraction=float(p[56:72].sum()/total), all_ky_edge_sample_l2=float(np.sqrt(edge)), all_ky_center_sample_l2=float(np.sqrt(centre)),
                corner_noise_power=noise, streak_normal_wedge_power=mean_n, streak_control_wedge_power=ctrl,
                streak_normal_over_control=mean_n/ctrl, streak_excess_over_floor=(mean_n-ctrl)/floor_k)


def edge_profile(im, angles_deg, cx=None, cy=None, r=np.arange(20, 70, .25)):
    cx = ROI['cx'] if cx is None else cx; cy = ROI['cy'] if cy is None else cy
    profs = []
    for a in angles_deg:
        t = np.radians(a); xs = cx+r*np.cos(t); ys = cy+r*np.sin(t)
        profs.append(ndimage.map_coordinates(im, [ys, xs], order=1, mode='nearest'))
    return r, np.median(profs, axis=0)


def edge_width(r, prof):
    top = np.median(prof[(r >= 25) & (r <= 35)]); low = np.median(prof[(r >= 58) & (r <= 66)])
    q = (prof-low)/(top-low)
    i50 = int(np.argmax((q < .5) & (r > 35)))
    def cross(level):
        j = int(np.argmax((q < level) & (r > 35)))
        return float(r[j-1]+(q[j-1]-level)/(q[j-1]-q[j])*(r[j]-r[j-1]))
    r90, r50, r10 = cross(.9), cross(.5), cross(.1)
    return dict(r90=r90, r50=r50, r10=r10, width_10_90=r10-r90, plateau=float(top), floor=float(low))


EDGE_ANGLES = dict(x=list(np.r_[np.arange(-8, 9, 2), np.arange(172, 189, 2)]), y=list(np.r_[np.arange(82, 99, 2), np.arange(-98, -81, 2)]))


def bright_edge_detect(im, bgmask, centre, ring=(38, 54), nsigma_rms=4.0):
    yy, xx = np.indices(im.shape); R = np.hypot(xx-centre[0], yy-centre[1]); bg_rms = float(np.sqrt(np.mean(im[bgmask]**2)))
    hot = (R >= ring[0]) & (R <= ring[1]) & (im > nsigma_rms*bg_rms)
    if not hot.any():
        return dict(n_pixels=0, max_over_bg_rms=float((im[(R >= ring[0]) & (R <= ring[1])].max())/bg_rms), x=None, y=None)
    return dict(n_pixels=int(hot.sum()), max_over_bg_rms=float(im[hot].max()/bg_rms), x=float(xx[hot].mean()), y=float(yy[hot].mean()),
                x_range=[int(xx[hot].min()), int(xx[hot].max())], y_range=[int(yy[hot].min()), int(yy[hot].max())])


def compute_all(scans):
    masks = roi_masks(); smasks = streak_masks(); floors, floor_sources = noise_floors(scans)
    img = []; kr = []; nav = []; widths = []; detect = []
    for n, s in scans.items():
        floor = floors[n]; L = s['L']
        for sl in range(s['S']):
            nav0 = np.array(s['navigators'][(0, sl)]['norm'])
            amp0 = np.sqrt(np.maximum(nav0**2-NSAMP*floor, 0))
            ref_img = {mode: image_metrics(abs(s['images'][(0, sl)][mode]), masks) for mode in MODES}
            for e, b in enumerate(s['b']):
                lab = direction_label(s, e); code = direction_code(lab); seq = SEQ[n]
                base = dict(scan=n, version=VERSION[n], volume=e+1, b=float(b), direction=lab, slice=sl+1, slice_offset_mm=s['parameters']['slice_offsets_mm'][sl])
                nv = s['navigators'][(e, sl)]; norms = np.array(nv['norm']); amps = np.sqrt(np.maximum(norms**2-NSAMP*floor, 0))
                for j in range(L):
                    nav.append(dict(scan=n, version=VERSION[n], volume=e+1, b=float(b), direction=lab, slice=sl+1, echo=j+1, norm=float(norms[j]),
                                    ratio_to_b0_echo1=float(norms[j]/nav0[0]), ratio_to_b0_same_echo=float(norms[j]/nav0[j]), ratio_to_first_echo=float(norms[j]/norms[0]),
                                    peak_sample=int(nv['peak_sample'][j]), peak_centroid=float(nv['peak_centroid'][j]), noise_power_window_volume=float(nv['noise_power_approx']),
                                    noise_power_floor_scan=floor, noise_sub_amp=float(amps[j]), noise_sub_ratio_to_b0_echo1=float(amps[j]/amp0[0]),
                                    noise_sub_ratio_to_b0_same_echo=float(amps[j]/amp0[j]) if amp0[j] > 0 else None,
                                    noise_sub_ratio_to_first_echo=float(amps[j]/amps[0]) if amps[0] > 0 else None,
                                    b_eff_model=float(effective_b(seq, b, code, j+1)) if seq in BEFF_TABLE else None,
                                    proj_line_zone_rms=float(nv['proj_line_zone_rms'][j]), proj_ref_zone_rms=float(nv['proj_ref_zone_rms'][j])))
                for mode in MODES:
                    im = abs(s['images'][(e, sl)][mode]); m = image_metrics(im, masks); r0 = ref_img[mode]
                    img.append(dict(base, mode=mode, **m, interior_ratio_to_b0=m['interior_mean']/r0['interior_mean'], interior_excess_ratio_to_b0=m['interior_excess_rms']/r0['interior_excess_rms'],
                                    edge_line_excess_ratio_to_b0=m['edge_line_excess_rms']/r0['edge_line_excess_rms']))
                    km = kspace_metrics(sorted_kspace(s, e, sl, mode), floor, smasks)
                    kr.append(dict(base, mode=mode, **km, nav_first_norm=float(norms[0]), nav_last_norm=float(norms[-1]), nav_last_over_first=float(norms[-1]/norms[0]),
                                   nav_first_ratio_to_b0=float(norms[0]/nav0[0]), nav_first_noise_sub_amp=float(amps[0]), nav_first_noise_sub_ratio_to_b0=float(amps[0]/amp0[0]),
                                   nav_peak_centroid_echo1=float(nv['peak_centroid'][0]), nav_peak_centroid_mean=float(np.mean(nv['peak_centroid'])),
                                   nav_proj_line_zone_rms_echo1=float(nv['proj_line_zone_rms'][0]), nav_proj_ref_zone_rms_echo1=float(nv['proj_ref_zone_rms'][0]),
                                   nav_proj_line_zone_over_floor_echo1=float(nv['proj_line_zone_rms'][0]**2/ (floor/ NSAMP))))
                im = abs(s['images'][(e, sl)]['off'])
                if b in (0, 1000):
                    for axis in ('x', 'y'):
                        r, p = edge_profile(im, EDGE_ANGLES[axis]); widths.append(dict(base, axis=axis, **edge_width(r, p)))
                det = bright_edge_detect(im, masks['background'], (ROI['cx'], ROI['cy']))
                detect.append(dict(base, **det))
    return dict(masks=masks, smasks=smasks, floors=floors, floor_sources=floor_sources, image=img, kspace=kr, nav=nav, widths=widths, detect=detect,
                img_idx={(r['scan'], r['volume']-1, r['slice']-1, r['mode']): r for r in img},
                nav_idx={(r['scan'], r['volume']-1, r['slice']-1, r['echo']-1): r for r in nav},
                k_idx={(r['scan'], r['volume']-1, r['slice']-1, r['mode']): r for r in kr})


# ---------------- Oct 7 reference data (read from the saved Oct 7 products) ----------------
V07 = {'test0': 'v1.8', 'test1': 'v1.8', 'test1b': 'v1.8', 'test2': 'v1.91', 'test2b': 'v1.91', 'test2c': 'v1.91', 'test3': 'v1.92', 'test3b': 'v1.92', 'test3c': 'v1.92', 'test3d': 'v1.92'}
SEQ07 = {'v1.8': 'v18', 'v1.91': 'v191'}


def load_oct07():
    d = json.loads((DATA/'physical_scanner_analysis_2026-10-07.json').read_text())
    with (DATA/'oct07_image_measurements.csv').open(encoding='utf-8-sig') as f:
        rows = [r for r in csv.DictReader(f) if r['mode'] == 'off']
    out = {}
    for n, sc in d['scans'].items():
        b = np.array(sc['b_values'], float); norms = np.array([v['norm'] for v in sc['navigators']]); win = np.array([v['noise_power_approx'] for v in sc['navigators']])
        floor = float(np.median(win[b >= 3000]))
        img = {float(r['b']): {k: float(v) for k, v in r.items() if k not in ('scan', 'mode')} for r in rows if r['scan'] == n}
        amps = np.sqrt(np.maximum(norms**2-NSAMP*floor, 0))
        out[n] = dict(version=V07[n], seq=SEQ07.get(V07[n]), b=b, L=sc['L'], esp=sc['parameters']['esp'], nav_norm=norms, nav_amp=amps, noise_floor=floor, img=img, gains=sc['gains'],
                      peak_centroid=None)
    return out


def load_oct07_images():
    spec = importlib.util.spec_from_file_location('oct07_analysis', DATA/'physical_scanner_analysis_2026-10-07.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.load_scans()


# ---------------- comparisons ----------------
def comparisons(scans, ctx, o7):
    rows = []; I = ctx['img_idx']; N = ctx['nav_idx']
    def add(pair, metric, num, den, vnum, vden, b=None, echo=None, lo=None, hi=None, basis='', note='', direction=None):
        rows.append(dict(pair=pair, metric=metric, b=b, echo=echo, direction=direction, numerator=num, denominator=den, value_numerator=vnum, value_denominator=vden,
                         ratio_num_over_den=(vnum/vden if (vnum is not None and vden not in (None, 0)) else None), prediction_low=lo, prediction_high=hi, prediction_basis=basis, note=note))
    def ie(n, b, d=None, sl=0):
        return bindex(scans[n], b, d)
    img = lambda n, b, key, sl=0, mode='off', d=None: I[(n, ie(n, b, d), sl, mode)][key]
    nv = lambda n, b, j, key='norm', sl=0, d=None: N[(n, ie(n, b, d), sl, j)][key]
    # 1) A vs C: b correction
    for key, label in [('interior_mean', 'image interior mean'), ('interior_excess_rms', 'image interior noise-corrected rms')]:
        for b in (100, 500, 1000, 2000, 3000):
            ra, rc = img('A', b, key)/img('A', 0, key), img('C', b, key)/img('C', 0, key)
            add('A_vs_C', f'{label} b/b0', 'A', 'C', ra, rc, b=b, lo=1.358 if b == 1000 else None, hi=1.375 if b == 1000 else None,
                basis='v1.81 b1000/b0 0.158-0.161 over v1.8 0.116-0.119 (FINAL_REPORT 8.1): ratio of ratios 1.33-1.39' if b == 1000 else '')
    for b in (100, 500, 1000, 2000, 3000):
        ra, rc = nv('A', b, 0, 'noise_sub_amp')/nv('A', 0, 0, 'noise_sub_amp'), nv('C', b, 0, 'noise_sub_amp')/nv('C', 0, 0, 'noise_sub_amp')
        add('A_vs_C', 'nav E1 noise-sub amp b/b0', 'A', 'C', ra, rc, b=b, basis='' if b != 1000 else 'predicted b1000/b0: A 0.158-0.161, C 0.116-0.119 (water D~0.0020-0.0023 effective-b)')
    add('A_vs_C', 'image interior b1000/b0 (A)', 'A', 'A', img('A', 1000, 'interior_mean')/img('A', 0, 'interior_mean'), 1.0, b=1000, lo=0.158, hi=0.161, basis='predicted v1.81 0.158-0.161')
    add('A_vs_C', 'image interior b1000/b0 (C)', 'C', 'C', img('C', 1000, 'interior_mean')/img('C', 0, 'interior_mean'), 1.0, b=1000, lo=0.116, hi=0.119, basis='predicted v1.8 0.116-0.119')
    add('A_vs_C', 'nav E1 raw L2 b1000/b0 (A)', 'A', 'A', nv('A', 1000, 0)/nv('A', 0, 0), 1.0, b=1000, lo=0.158, hi=0.161, basis='predicted v1.81 0.158-0.161')
    add('A_vs_C', 'nav E1 raw L2 b1000/b0 (C)', 'C', 'C', nv('C', 1000, 0)/nv('C', 0, 0), 1.0, b=1000, lo=0.116, hi=0.119, basis='predicted v1.8 0.116-0.119')
    for b in (0, 1000):
        add('A_vs_C', 'absolute image interior mean', 'A', 'C', img('A', b, 'interior_mean'), img('C', b, 'interior_mean'), b=b, lo=1.0, hi=1.02 if b == 0 else None, basis='b0: v1.81 about +1.6% vs v1.8 (FINAL_REPORT 10), different RF drift not excluded')
        add('A_vs_C', 'absolute nav E1 L2', 'A', 'C', nv('A', b, 0), nv('C', b, 0), b=b)
    # 2) B vs D per-echo
    for b in (0, 1000):
        for j in range(8):
            vb, vd = nv('B', b, j), nv('D', b, j)
            add('B_vs_D', 'nav L2 per echo (absolute)', 'B', 'D', vb, vd, b=b, echo=j+1, lo=BD_PRED['no_relax_D002'][j], hi=BD_PRED['T2_60_D002'][j],
                basis='FINAL_REPORT 10: low = no relaxation D0.002 (water, long T2); high = T2 60 ms; T2 32 ms row: %.4f' % BD_PRED['T2_32_D002_grid'][j])
            add('B_vs_D', 'nav noise-sub amp per echo (absolute)', 'B', 'D', nv('B', b, j, 'noise_sub_amp'), nv('D', b, j, 'noise_sub_amp'), b=b, echo=j+1, lo=BD_PRED['no_relax_D002'][j], hi=BD_PRED['T2_60_D002'][j], basis='same')
    for b in (0, 100, 500, 1000, 2000, 3000):
        add('B_vs_D', 'image interior mean', 'B', 'D', img('B', b, 'interior_mean'), img('D', b, 'interior_mean'), b=b, lo=BD_PRED['no_relax_D002'][0], hi=BD_PRED['T2_60_D002'][0], basis='centric: image contrast ~ E1-E2 weighted')
    # 3) E vs A, G vs B (repeat protocol except extra volumes)
    for pair, x, y in [('E_vs_A', 'E', 'A'), ('G_vs_B', 'G', 'B')]:
        for b in (0, 1000, 3000):
            d = None if b == 0 else (1, 0, 0)
            add(pair, 'image interior mean (+x)', x, y, img(x, b, 'interior_mean', d=d), img(y, b, 'interior_mean'), b=b, direction='+x')
            add(pair, 'nav E1 L2 (+x)', x, y, nv(x, b, 0, d=d), nv(y, b, 0), b=b, direction='+x')
            add(pair, 'nav E1 noise-sub amp (+x)', x, y, nv(x, b, 0, 'noise_sub_amp', d=d), nv(y, b, 0, 'noise_sub_amp'), b=b, direction='+x')
        for j in range(8):
            add(pair, 'nav L2 per echo b1000 (+x)', x, y, nv(x, 1000, j, d=(1, 0, 0)), nv(y, 1000, j), b=1000, echo=j+1, direction='+x')
    # 4) H vs A
    for b in (0, 1000, 3000):
        for key in ('interior_mean', 'interior_excess_rms', 'rim_mean', 'rim_excl_edge_mean', 'edge_line_mean', 'edge_line_excess_rms', 'edge_ref_mean', 'background_mean', 'background_rms',
                    'interior_highpass_over_mean', 'interior_smooth_cv', 'outside_ring_mean'):
            add('H_vs_A', key, 'H', 'A', img('H', b, key), img('A', b, key), b=b)
        for key in ('edge_line_over_interior', 'edge_line_over_background_mean'):
            add('H_vs_A', key, 'H', 'A', img('H', b, key), img('A', b, key), b=b)
        add('H_vs_A', 'nav E1 L2', 'H', 'A', nv('H', b, 0), nv('A', b, 0), b=b)
        add('H_vs_A', 'nav E8 L2', 'H', 'A', nv('H', b, 7), nv('A', b, 7), b=b)
        add('H_vs_A', 'nav E8/E1 (train decay)', 'H', 'A', nv('H', b, 7)/nv('H', b, 0), nv('A', b, 7)/nv('A', b, 0), b=b)
        kh, ka = ctx['k_idx'][('H', ie('H', b), 0, 'off')], ctx['k_idx'][('A', ie('A', b), 0, 'off')]
        for key in ('readout_edge_power_fraction', 'streak_excess_over_floor', 'total_l2'):
            add('H_vs_A', 'kspace '+key, 'H', 'A', kh[key], ka[key], b=b)
    # 5) I vs B
    for b in (0, 1000, 3000):
        for key in ('interior_mean', 'interior_excess_rms', 'background_rms', 'edge_line_excess_rms'):
            add('I_vs_B', key, 'I', 'B', img('I', b, key), img('B', b, key), b=b, basis='delta30/TE44: +37% (T2 32) / +18% (T2 60) prep signal; water T2 long -> expect small gain', lo=1.0, hi=1.37 if key == 'interior_mean' else None)
        for j in range(8):
            add('I_vs_B', 'nav L2 per echo', 'I', 'B', nv('I', b, j), nv('B', b, j), b=b, echo=j+1, lo=1.0, hi=1.37)
            add('I_vs_B', 'nav noise-sub amp per echo', 'I', 'B', nv('I', b, j, 'noise_sub_amp'), nv('B', b, j, 'noise_sub_amp'), b=b, echo=j+1)
    for j in range(8):
        add('I_vs_B', 'nav L2 b1000/b0 per echo (I)', 'I', 'B', nv('I', 1000, j)/nv('I', 0, j), nv('B', 1000, j)/nv('B', 0, j), b=1000, echo=j+1, note='diffusion time differs (30 vs 40 ms): attenuation not directly comparable')
    # 6) J vs A (and K slice 2 vs J)
    for b in (0, 1000, 3000):
        for key in ('interior_mean', 'interior_excess_rms', 'background_mean', 'background_std', 'background_rms', 'interior_over_background_rms', 'interior_highpass_over_mean', 'interior_smooth_cv', 'edge_line_excess_rms'):
            add('J_vs_A', key, 'J', 'A', img('J', b, key), img('A', b, key), b=b,
                lo=(1/np.sqrt(2) if key == 'interior_over_background_rms' else (np.sqrt(2) if key in ('background_rms', 'background_std', 'background_mean') else None)),
                basis='40 kHz doubles noise bandwidth: noise rms x sqrt2, SNR /sqrt2 at equal signal' if key in ('interior_over_background_rms', 'background_rms', 'background_std', 'background_mean') else '')
        add('J_vs_A', 'nav E1 L2', 'J', 'A', nv('J', b, 0), nv('A', b, 0), b=b)
        add('J_vs_A', 'nav E8/E1 echo-train decay (by echo index)', 'J', 'A', nv('J', b, 7)/nv('J', b, 0), nv('A', b, 7)/nv('A', b, 0), b=b)
        add('J_vs_A', 'nav E4/E1', 'J', 'A', nv('J', b, 3)/nv('J', b, 0), nv('A', b, 3)/nv('A', b, 0), b=b)
        add('J_vs_A', 'nav noise floor power per sample', 'J', 'A', ctx['floors']['J'], ctx['floors']['A'], b=b, lo=2.0, hi=2.0, basis='noise power per complex sample doubles with 2x bandwidth')
    for axis in ('x', 'y'):
        for b in (0, 1000):
            wj = next(w for w in ctx['widths'] if w['scan'] == 'J' and w['b'] == b and w['axis'] == axis)['width_10_90']
            wa = next(w for w in ctx['widths'] if w['scan'] == 'A' and w['b'] == b and w['axis'] == axis)['width_10_90']
            add('J_vs_A', f'edge 10-90% width px ({axis}-rays)', 'J', 'A', wj, wa, b=b, note='radial median profile; centre (61,73)')
    # 7) K slices vs A / J
    for sl in range(3):
        for b in (0, 1000):
            add('K_vs_A', f'slice{sl+1} interior mean', 'K', 'A', img('K', b, 'interior_mean', sl=sl), img('A', b, 'interior_mean'), b=b, note='K and J use dwell 25 / ESP 11; A dwell 50 / ESP 14')
            add('K_vs_J', f'slice{sl+1} interior mean', 'K', 'J', img('K', b, 'interior_mean', sl=sl), img('J', b, 'interior_mean'), b=b, note='same dwell/ESP')
            add('K_vs_J', f'slice{sl+1} nav E1 L2', 'K', 'J', nv('K', b, 0, sl=sl), nv('J', b, 0), b=b)
        add('K_vs_A', f'slice{sl+1} interior b1000/b0', 'K', 'A', img('K', 1000, 'interior_mean', sl=sl)/img('K', 0, 'interior_mean', sl=sl), img('A', 1000, 'interior_mean')/img('A', 0, 'interior_mean'), b=1000, lo=0.158, hi=0.161, basis='v1.81 prediction')
        add('K_vs_A', f'slice{sl+1} nav E1 L2 b1000/b0', 'K', 'A', nv('K', 1000, 0, sl=sl)/nv('K', 0, 0, sl=sl), nv('A', 1000, 0)/nv('A', 0, 0), b=1000)
    for b in (0, 1000):
        for sl in (0, 2):
            add('K_crosstalk', f'slice{sl+1}/slice2 interior mean', 'K', 'K', img('K', b, 'interior_mean', sl=sl), img('K', b, 'interior_mean', sl=1), b=b, note='slice offsets -1.2/0/+1.2 mm, 1.0 mm thick; uniform object so a systematic deficit of an outer slice indicates cross-talk/saturation or coil profile')
            add('K_crosstalk', f'slice{sl+1}/slice2 nav E1 L2', 'K', 'K', nv('K', b, 0, sl=sl), nv('K', b, 0, sl=1), b=b)
    # 8) cross-day (ratios; gains differ: RX30 both days, TX -195 on Oct 7 vs -203 Oct 10)
    def day7(name, b, key):
        s = o7[name]; i = int(np.flatnonzero(s['b'] == b)[0])
        return {'nav_L2': s['nav_norm'][i, 0], 'nav_amp': s['nav_amp'][i, 0], 'nav_L2_last8': s['nav_norm'][i, 7], 'img': s['img'][b]['interior_mean'], 'img_excess': s['img'][b]['interior_excess_rms_approx'], 'bg': s['img'][b]['background_rms']}[key]
    for today, old, bs in [('C', 'test1b', (100, 500, 1000, 2000, 3000, 6000)), ('C', 'test1', (1000, 6000)), ('D', 'test2c', (100, 500, 1000, 2000, 3000, 6000)), ('D', 'test2', (1000, 6000)),
                           ('A', 'test1b', (1000, 6000)), ('A', 'test1', (1000, 6000)), ('B', 'test2c', (1000, 6000)), ('B', 'test2', (1000, 6000))]:
        for b in bs:
            if bindex(scans[today], b) is None:
                continue
            vt = nv(today, b, 0)/nv(today, 0, 0); vo = day7(old, b, 'nav_L2')/day7(old, 0, 'nav_L2')
            add(f'xday_{today}_vs_{old}', 'nav E1 raw L2 b/b0', today, old, vt, vo, b=b, note=f'{VERSION[today]} {scans[today]["L"]}-echo today vs {o7[old]["version"]} {o7[old]["L"]}-echo Oct 7')
            vt = nv(today, b, 0, 'noise_sub_amp')/nv(today, 0, 0, 'noise_sub_amp'); vo = day7(old, b, 'nav_amp')/day7(old, 0, 'nav_amp')
            add(f'xday_{today}_vs_{old}', 'nav E1 noise-sub amp b/b0', today, old, vt, vo, b=b)
            vt = img(today, b, 'interior_mean')/img(today, 0, 'interior_mean'); vo = day7(old, b, 'img')/day7(old, 0, 'img')
            add(f'xday_{today}_vs_{old}', 'image interior mean b/b0', today, old, vt, vo, b=b)
            vt = img(today, b, 'interior_excess_rms')/img(today, 0, 'interior_excess_rms'); vo = day7(old, b, 'img_excess')/day7(old, 0, 'img_excess')
            add(f'xday_{today}_vs_{old}', 'image interior noise-corrected rms b/b0', today, old, vt, vo, b=b)
        for b in (0, 1000):
            vt = nv(today, b, 7)/nv(today, b, 0); vo = day7(old, b, 'nav_L2_last8')/day7(old, b, 'nav_L2')
            add(f'xday_{today}_vs_{old}', 'nav E8/E1', today, old, vt, vo, b=b, note='both ESP 14; old scan echo 8 of its own train')
            add(f'xday_{today}_vs_{old}', 'absolute nav E1 L2', today, old, nv(today, b, 0), day7(old, b, 'nav_L2'), b=b, note='different TX gain (-203 vs -195) and sample position')
    return rows


# ---------------- figures ----------------
def vmax_for(scans, cells, mode, kspace):
    vals = []
    for n, e, sl in cells:
        s = scans[n]
        vals.append(np.log10(1+abs(sorted_kspace(s, e, sl, mode))).max() if kspace else abs(s['images'][(e, sl)][mode]).max())
    return max(vals)


def sheet(scans, rows, col_titles, file, title, mode='off', kspace=False, note='', per_col=True, annotate=True, zoom=None):
    """rows: list of (row_label, [ (scan, e, sl) or None per column ]). Display scale shared within each column (absolute units)."""
    OUT.mkdir(parents=True, exist_ok=True)
    nc = len(col_titles); nr = len(rows)
    fig, axs = plt.subplots(nr, nc, figsize=(2.55*nc+1.2, 2.55*nr+1.3), squeeze=False, layout='constrained')
    vm = [max([vmax_for(scans, [r[1][c]], mode, kspace) for r in rows if r[1][c] is not None] or [1]) for c in range(nc)]
    for j, (label, cells) in enumerate(rows):
        for c, cell in enumerate(cells):
            ax = axs[j, c]
            if cell is None:
                ax.axis('off'); continue
            n, e, sl = cell; s = scans[n]
            arr = np.log10(1+abs(sorted_kspace(s, e, sl, mode))) if kspace else abs(s['images'][(e, sl)][mode])
            if zoom is not None and not kspace:
                arr = arr[zoom[0]:zoom[1], zoom[2]:zoom[3]]
            ax.imshow(arr, cmap='magma' if kspace else 'gray', vmin=0, vmax=vm[c], origin='upper', interpolation='nearest')
            ax.set_xticks([]); ax.set_yticks([])
            if c == 0:
                ax.set_ylabel(label, fontsize=9)
            if j == 0:
                ax.set_title(col_titles[c], fontsize=9)
            if annotate and not kspace:
                full = abs(s['images'][(e, sl)][mode]); yy, xx = np.indices(full.shape); inside = np.hypot(xx-ROI['cx'], yy-ROI['cy']) <= ROI['r_int']
                ax.text(.03, .03, f'int {full[inside].mean():.3g}', transform=ax.transAxes, color='yellow', fontsize=7, va='bottom')
    for c in range(nc):
        artists = [ax.images[0] for ax in axs[:, c] if len(ax.images)]
        if artists:
            fig.colorbar(artists[0], ax=axs[:, c].tolist(), shrink=.5, location='bottom', pad=.02, label=('log10(1+|K|)' if kspace else 'magnitude units'), fraction=.04)
    fig.suptitle(title+'\n'+LABELS[mode]+'; one absolute display scale per column; all RX 30 / TX -203; no registration or normalization'+(('\n'+note) if note else ''), fontsize=10)
    save_figure(fig, OUT/file)


def cells_by_b(scans, n, bs, sl=0, direction=(1, 0, 0)):
    out = []
    for b in bs:
        e = bindex(scans[n], b, None if b == 0 else direction)
        out.append((n, e, sl) if e is not None else None)
    return out


def figures(scans, ctx, o7, o7img):
    OUT.mkdir(parents=True, exist_ok=True)
    b7 = [0, 100, 500, 1000, 2000, 3000, 6000]; t7 = [f'b{b}' for b in b7]; t3 = ['b0', 'b1000', 'b3000']
    rowsA = lambda names, bs: [(f'{n}\n{SHORT[n]}', cells_by_b(scans, n, bs)) for n in names]
    # contact sheets of every scan/volume
    sheet(scans, rowsA(['A', 'C', 'B', 'D'], b7), t7, 'contact_7b_A_C_B_D.png', 'Contact sheet: seven-b scans A, C (v1.81/v1.8 water) and B, D (v1.911/v1.91)')
    vol_titles = lambda s: [f'b{b:g} {direction_label(s, e)}' if b else 'b0' for e, b in enumerate(s['b'])]
    sheet(scans, [(f'{n}\n{SHORT[n]}', [(n, e, 0) for e in range(8)]) for n in ('E', 'G')], vol_titles(scans['E']), 'contact_8vol_E_G.png', 'Contact sheet: eight-volume direction scans E (v1.81) and G (v1.911)')
    sheet(scans, rowsA(['H', 'I', 'J'], [0, 1000, 3000]), t3, 'contact_3b_H_I_J.png', 'Contact sheet: three-b scans H (crusher = selector), I (delta30/TE44), J (40 kHz)')
    sheet(scans, [(f'K slice {sl+1}\n({scans["K"]["parameters"]["slice_offsets_mm"][sl]:+.1f} mm)', [('K', 0, sl), ('K', 1, sl)]) for sl in range(3)], ['b0', 'b1000'], 'contact_K_slices.png', 'Contact sheet: scan K, three slices (v1.81, 40 kHz)')
    # pair figures
    sheet(scans, rowsA(['A', 'C'], b7), t7, 'A_vs_C_seven_b.png', 'A (v1.81) vs C (v1.8): seven-b series, b-value correction')
    sheet(scans, rowsA(['B', 'D'], b7), t7, 'B_vs_D_seven_b.png', 'B (v1.911, ESP 13) vs D (v1.91, ESP 14): seven-b series')
    dir_titles = vol_titles(scans['E'])
    sheet(scans, [(f'{n}\n{SHORT[n]}', [(n, e, 0) for e in range(8)]) for n in ('E', 'G')], dir_titles, 'E_vs_G_directions.png', 'Direction grid: E (v1.81) vs G (v1.911), b1000 +x, -x, +y, +z and b3000 +x, +y, +z')
    sheet(scans, rowsA(['A', 'H'], [0, 1000, 3000]), t3, 'H_vs_A.png', 'H (train crusher -2741 = selector) vs A (-8223)')
    sheet(scans, rowsA(['B', 'I'], [0, 1000, 3000]), t3, 'I_vs_B.png', 'I (delta 30 ms, TE 44) vs B (delta 40 ms, TE 54), v1.911')
    sheet(scans, [(f'K slice {sl+1}', [('K', 0, sl), ('K', 1, sl)]) for sl in range(3)] + [('A (slice 1)', [('A', 0, 0), ('A', 3, 0)])], ['b0', 'b1000'], 'K_three_slices.png', 'K three slices vs A (K: 40 kHz/ESP 11, A: 20 kHz/ESP 14)')
    figure_J(scans, ctx)
    figure_navigator(scans, ctx)
    figure_edge(scans, ctx, o7, o7img)
    # raw k-space panels
    sheet(scans, rowsA(['A', 'C', 'B', 'D', 'H', 'I', 'J'], [0, 1000, 3000]), t3, 'kspace_panels.png', 'Raw k-space (imaging ADC samples, navigator excluded)', kspace=True)
    sheet(scans, [(f'{n}\n{SHORT[n]}', [(n, e, 0) for e in range(8)]) for n in ('E', 'G')], dir_titles, 'kspace_panels_E_G.png', 'Raw k-space, direction scans E and G', kspace=True)
    figure_roi(scans, ctx)
    if o7 is not None:
        pass


def figure_roi(scans, ctx):
    m = ctx['masks']
    fig, axs = plt.subplots(2, 5, figsize=(16, 7), layout='constrained')
    for ax, n in zip(axs.flat, NAMES):
        s = scans[n]; e = bindex(s, 1000, (1, 0, 0)); im = abs(s['images'][(e, min(1, s['S']-1))]['off'])
        ax.imshow(im, cmap='gray', vmax=im.max()*.7)
        for key, color in [('interior', 'cyan'), ('rim', 'orange'), ('background', 'lime'), ('edge_line', 'red'), ('edge_ref', 'magenta')]:
            ax.contour(m[key], levels=[.5], colors=[color], linewidths=.7)
        ax.set_title(f'{n} b1000' + (' slice 2' if s['S'] > 1 else '')); ax.axis('off')
    fig.suptitle('Fixed ROI coordinates, identical for all scans and volumes; no registration\ncyan interior r<=34 (centre x=61, y=73); orange rim r41-47; green corner background; red edge-line ROI; magenta edge reference strip\nx = column (readout), y = row (phase encode); array orientation as displayed')
    save_figure(fig, OUT/'roi_placement.png')


def figure_J(scans, ctx):
    A, J = scans['A'], scans['J']; fig, axs = plt.subplots(3, 4, figsize=(18, 12), layout='constrained')
    bs = [0, 1000, 3000]
    vm = [max(abs(scans[n]['images'][(bindex(scans[n], b, None if b == 0 else (1, 0, 0)), 0)]['off']).max() for n in 'AJ') for b in bs]
    for r, n in enumerate('AJ'):
        for c, b in enumerate(bs):
            e = bindex(scans[n], b, None if b == 0 else (1, 0, 0)); axs[r, c].imshow(abs(scans[n]['images'][(e, 0)]['off']), cmap='gray', vmin=0, vmax=vm[c])
            axs[r, c].set_title(f'{n} ({SHORT[n]}) b{b}'); axs[r, c].axis('off')
    # noise maps: b3000 magnitude on a common noise-scale; histogram of corner background
    sig = {n: ctx['img_idx'][(n, bindex(scans[n], 3000), 0, 'off')]['background_rms'] for n in 'AJ'}
    for r, n in enumerate('AJ'):
        e = bindex(scans[n], 3000, (1, 0, 0)); im = abs(scans[n]['images'][(e, 0)]['off']); axs[r, 3].imshow(im, cmap='viridis', vmin=0, vmax=4*sig['A']); axs[r, 3].set_title(f'{n} b3000 noise map, shared scale 0-{4*sig["A"]:.3g}'); axs[r, 3].axis('off')
    x = np.arange(128)
    for c, b in enumerate([0, 1000]):
        for n, col in zip('AJ', ['tab:blue', 'tab:red']):
            e = bindex(scans[n], b, None if b == 0 else (1, 0, 0)); im = abs(scans[n]['images'][(e, 0)]['off']); axs[2, c].plot(x, im[70:77].mean(0), color=col, label=f'{n} rows 70-76')
        axs[2, c].set_title(f'b{b} horizontal profile through centre (x = readout)'); axs[2, c].set_xlabel('x (column)'); axs[2, c].legend(); axs[2, c].grid(alpha=.2)
    for n, col in zip('AJ', ['tab:blue', 'tab:red']):
        for ls, b in [('-', 0), ('--', 1000)]:
            e = bindex(scans[n], b, None if b == 0 else (1, 0, 0)); im = abs(scans[n]['images'][(e, 0)]['off'])
            for axis, ax in [('x', axs[2, 2]), ('y', axs[2, 3])]:
                r, p = edge_profile(im, EDGE_ANGLES[axis]); ax.plot(r, p/np.median(p[(r >= 25) & (r <= 35)]), color=col, ls=ls, label=f'{n} b{b}')
    for ax, t in [(axs[2, 2], 'normalized radial edge profile, x-rays'), (axs[2, 3], 'normalized radial edge profile, y-rays')]:
        ax.set_xlim(38, 58); ax.set_title(t); ax.set_xlabel('radius from (61,73) [px]'); ax.legend(fontsize=8); ax.grid(alpha=.2)
    wj = {(w['scan'], w['b'], w['axis']): w['width_10_90'] for w in ctx['widths']}
    fig.suptitle('J (40 kHz, 25 us dwell, ESP 11) vs A (20 kHz, 50 us dwell, ESP 14), v1.81\nnoise rms J/A at b3000 = %.3f; edge 10-90%% width b0 x-rays: A %.2f px, J %.2f px; y-rays: A %.2f, J %.2f' % (sig['J']/sig['A'], wj[('A', 0, 'x')], wj[('J', 0, 'x')], wj[('A', 0, 'y')], wj[('J', 0, 'y')]))
    save_figure(fig, OUT/'J_vs_A.png')


def figure_navigator(scans, ctx):
    N = ctx['nav_idx']; echo = np.arange(1, 9)
    fig, axs = plt.subplots(2, 3, figsize=(18, 10), layout='constrained')
    cols = dict(A='tab:blue', C='tab:cyan', E='tab:green', H='tab:olive', J='tab:red', K='tab:brown', B='tab:purple', D='tab:pink', G='tab:gray', I='tab:orange')
    for fam, ax, names in [('v1.8 family', axs[0, 0], 'ACEHJK'), ('ss-MGOT family', axs[0, 1], 'BDGI')]:
        for n in names:
            s = scans[n]
            for b, ls in [(0, '-'), (1000, '--')]:
                e = bindex(s, b, None if b == 0 else (1, 0, 0)); ax.plot(echo, [N[(n, e, min(1, s['S']-1) if n == 'K' else 0, j)]['norm'] for j in range(8)], ls, marker='.', color=cols[n], label=f'{n} b{b}')
        ax.set_yscale('log'); ax.set_title(fam+': navigator L2 per echo (solid b0, dashed b1000)'); ax.set_xlabel('echo'); ax.set_ylabel('L2 of one navigator line (raw units)'); ax.legend(fontsize=7, ncol=2); ax.grid(alpha=.2)
    for n in 'ACEHJKBDGI':
        s = scans[n]; e = bindex(s, 0); sl = 1 if n == 'K' else 0
        axs[0, 2].plot(echo, [N[(n, e, sl, j)]['ratio_to_first_echo'] for j in range(8)], marker='.', color=cols[n], label=n)
    axs[0, 2].set_title('b0: echo-train decay, L2 / echo 1'); axs[0, 2].set_xlabel('echo'); axs[0, 2].legend(ncol=2); axs[0, 2].grid(alpha=.2)
    for b, ax in [(0, axs[1, 0]), (1000, axs[1, 1])]:
        ratio = [N[('B', bindex(scans['B'], b), 0, j)]['norm']/N[('D', bindex(scans['D'], b), 0, j)]['norm'] for j in range(8)]
        ax.plot(echo, ratio, 'ko-', label='measured B/D')
        gz = [N[('G', bindex(scans['G'], b, None if b == 0 else (1, 0, 0)), 0, j)]['norm']/N[('D', bindex(scans['D'], b), 0, j)]['norm'] for j in range(8)]
        ax.plot(echo, gz, 's--', color='tab:gray', label='G(+x)/D')
        for key, col in [('no_relax_D002', 'tab:green'), ('T2_60_D002', 'tab:orange'), ('T2_32_D002_grid', 'tab:red')]:
            ax.plot(echo, BD_PRED[key], ':', color=col, label='predicted '+key)
        ax.set_title(f'B/D navigator L2 ratio per echo, b{b}, vs prediction'); ax.set_xlabel('echo'); ax.legend(fontsize=8); ax.grid(alpha=.2)
    for n in 'ACEHJKBDGI':
        s = scans[n]; sl = 1 if n == 'K' else 0
        e0, e1 = bindex(s, 0), bindex(s, 1000, (1, 0, 0))
        axs[1, 2].plot(echo, [N[(n, e1, sl, j)]['norm']/N[(n, e0, sl, j)]['norm'] for j in range(8)], marker='.', color=cols[n], label=n)
    axs[1, 2].set_title('b1000 / b0 navigator ratio per echo (own b0 each echo)'); axs[1, 2].set_xlabel('echo'); axs[1, 2].legend(ncol=2); axs[1, 2].grid(alpha=.2)
    fig.suptitle('Navigator echo trains (uncorrected complex navigator lines, ETL 8); scan K uses slice 2')
    save_figure(fig, OUT/'navigator_echo_trains.png')


def figure_edge(scans, ctx, o7, o7img):
    masks = ctx['masks']; I = ctx['img_idx']
    names = list(NAMES); ncol = 8
    fig, axs = plt.subplots(len(names), ncol, figsize=(2.2*ncol, 2.0*len(names)), layout='constrained', squeeze=False)
    sl_box = (22, 72, 8, 58)
    for r, n in enumerate(names):
        s = scans[n]; sl = 1 if n == 'K' else 0
        for c in range(ncol):
            ax = axs[r, c]; ax.axis('off')
            if c >= s['E']:
                continue
            im = abs(s['images'][(c, sl)]['off']); m = I[(n, c, sl, 'off')]
            vmax = 2.5*m['interior_mean'] if s['b'][c] < 1500 else 7*m['background_rms']
            ax.imshow(im[sl_box[0]:sl_box[1], sl_box[2]:sl_box[3]], cmap='gray', vmin=0, vmax=vmax)
            ax.contour(masks['edge_line'][sl_box[0]:sl_box[1], sl_box[2]:sl_box[3]], levels=[.5], colors=['red'], linewidths=.4)
            ax.set_title(f'{n} b{s["b"][c]:g} {direction_label(s, c)}', fontsize=7)
    fig.suptitle('Upper-left boundary edge line (crop rows 22-71, cols 8-57), correction off; b<1500: scale 2.5x interior mean, b>=1500: scale 7x noise rms\nred = ROI; scan K shown for slice 2')
    save_figure(fig, OUT/'edge_line_feature.png')
    # intensity vs b
    fig, axs = plt.subplots(2, 3, figsize=(17, 9), layout='constrained')
    cols = dict(A='tab:blue', C='tab:cyan', E='tab:green', H='tab:olive', J='tab:red', K='tab:brown', B='tab:purple', D='tab:pink', G='tab:gray', I='tab:orange')
    for n in NAMES:
        s = scans[n]; sl = 1 if n == 'K' else 0
        es = [e for e in range(s['E']) if direction_label(s, e) in ('none', '+x')]
        bs = np.array([s['b'][e] for e in es]); edge = np.array([I[(n, e, sl, 'off')]['edge_line_excess_rms'] for e in es]); inter = np.array([I[(n, e, sl, 'off')]['interior_excess_rms'] for e in es])
        ref = np.array([I[(n, e, sl, 'off')]['edge_ref_excess_rms'] for e in es]); det = np.array([I[(n, e, sl, 'off')]['edge_line_over_background_mean'] for e in es])
        axs[0, 0].plot(bs, edge, 'o-', color=cols[n], label=n); axs[0, 1].plot(bs, edge/edge[0], 'o-', color=cols[n], label=n); axs[0, 2].plot(bs, inter/inter[0], 'o-', color=cols[n], label=n)
        axs[1, 0].plot(bs, np.where(inter > 0, edge/np.where(inter > 0, inter, 1), np.nan), 'o-', color=cols[n], label=n); axs[1, 1].plot(bs, det, 'o-', color=cols[n], label=n)
        axs[1, 2].plot(bs, [ctx['k_idx'][(n, e, sl, 'off')]['streak_excess_over_floor'] for e in es], 'o-', color=cols[n], label=n)
    grid = np.linspace(0, 6000, 200)
    for ax in (axs[0, 1], axs[0, 2]):
        ax.plot(grid, np.exp(-0.002*grid), 'k:', label='exp(-0.002 b)')
    axs[0, 0].set_title('edge-line ROI noise-corrected rms (abs. units)'); axs[0, 1].set_title('edge-line / own b0'); axs[0, 2].set_title('interior / own b0 (water decay)')
    axs[1, 0].set_title('edge-line / interior (noise-corrected)'); axs[1, 1].set_title('edge-line mean / background mean (1 = noise only)'); axs[1, 2].set_title('k-space streak: (normal wedge - control)/noise floor')
    for ax in axs.flat:
        ax.set_xlabel('requested b (s/mm^2)'); ax.grid(alpha=.2); ax.legend(fontsize=7, ncol=2)
    for ax in (axs[0, 0], axs[0, 1], axs[0, 2], axs[1, 0], axs[1, 2]):
        ax.set_yscale('log')
    axs[1, 1].axhline(1.25, color='k', ls=':')
    fig.suptitle('Edge-line feature versus b (b0 and +x volumes; K slice 2); noise-corrected using the corner-background rms')
    save_figure(fig, OUT/'edge_line_vs_b.png')
    # Oct 7 comparison crops
    if o7img is not None:
        sel = [('test0', 1000), ('test0', 6000), ('test1', 6000), ('test1b', 3000), ('test1b', 6000), ('test2c', 3000)]
        fig, axs = plt.subplots(2, 4, figsize=(15, 7.5), layout='constrained')
        axs = axs.ravel()
        for ax, (n, b) in zip(axs, sel):
            s = o7img[n]; e = bindex(s, b); im = abs(s['images'][e]['off']); yy, xx = np.indices(im.shape); bg = (yy < 20) & ((xx < 16) | (xx >= 112))
            ax.imshow(im, cmap='gray', vmin=0, vmax=7*np.sqrt(np.mean(im[bg]**2)) if b >= 3000 else 2.5*im[np.hypot(xx-61, yy-71) < 34].mean())
            ax.set_title(f'Oct 7 {n} b{b}'); ax.set_xlim(0, 80); ax.set_ylim(115, 20)
        for ax, (n, b) in zip(axs[6:], [('A', 3000), ('E', 3000)]):
            s = scans[n]; e = bindex(s, b, (1, 0, 0)); im = abs(s['images'][(e, 0)]['off']); bg = ctx['masks']['background']
            ax.imshow(im, cmap='gray', vmin=0, vmax=7*np.sqrt(np.mean(im[bg]**2))); ax.set_title(f'Oct 10 {n} b{b}'); ax.set_xlim(0, 80); ax.set_ylim(115, 20)
        fig.suptitle('Oct 7 (centre 61,71) vs Oct 10 (centre 61,73): boundary line features at high b, scale 7x noise rms for b>=3000; Oct 7 left half shown')
        save_figure(fig, OUT/'edge_line_oct07_comparison.png')


def alignment(scans):
    out = []
    for n, s in scans.items():
        base = abs(s['images'][(0, min(1, s['S']-1))]['off']); labels, num = ndimage.label(base > .45*base.max())   # b0 volume: the edge line is not the brightest feature there
        sizes = np.bincount(labels.ravel()); sizes[0] = 0; region = labels == sizes.argmax(); cy, cx = ndimage.center_of_mass(region)
        out.append(dict(scan=n, x=float(cx), y=float(cy), area_px=int(region.sum()), equivalent_radius_px=float(np.sqrt(region.sum()/np.pi))))
    return out


def write_csv(name, records):
    with (DATA/name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(records[0])); w.writeheader(); w.writerows(records)


def main():
    scans = load_scans()
    ctx = compute_all(scans)
    o7 = load_oct07()
    o7img = None if '--metrics-only' in sys.argv else load_oct07_images()
    pair_rows = comparisons(scans, ctx, o7)
    # Oct 7 edge-feature scan: every Oct 7 volume with b>=1000, bright pixels (>4x background rms) in the boundary band
    detect07 = []
    if o7img is None:
        o7img_for_detect = load_oct07_images()
    else:
        o7img_for_detect = o7img
    yy, xx = np.indices((128, 128)); bg07 = (yy < 20) & ((xx < 16) | (xx >= 112))
    for n, s in o7img_for_detect.items():
        for e, b in enumerate(s['b']):
            if b >= 1000:
                detect07.append(dict(scan=n, b=float(b), **bright_edge_detect(abs(s['images'][e]['off']), bg07, (61, 71), ring=(38, 54))))
    write_csv('oct10_image_measurements.csv', ctx['image'])
    write_csv('oct10_kspace_measurements.csv', ctx['kspace'])
    write_csv('oct10_navigator_echoes.csv', ctx['nav'])
    write_csv('oct10_pair_comparisons.csv', pair_rows)
    write_csv('oct10_edge_width.csv', ctx['widths'])
    np.savez_compressed(DATA/'oct10_roi_masks.npz', **ctx['masks'])
    summary = dict(reconstruction_sha256=hashlib.sha256(SRC.read_bytes()).hexdigest(), analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   loader_sha256=hashlib.sha256((ROOT/'scanner/recon/get_mrd_3d4.py').read_bytes()).hexdigest(),
                   scans={n: dict(letter=n, version=VERSION[n], folder=s['folder'].name, dims=s['dims'], L=s['L'], nav=s['nav'], N=s['N'], pe=s['pe'], nifti_errors=s['nifti_errors'], nifti=s['nifti'],
                                  parameters=s['parameters'], gains=s['gains'], mrd_sha256=s['mrd_sha256'], b_values=s['b'].tolist(), bvec=s['bvec'].tolist(),
                                  directions=[direction_label(s, e) for e in range(s['E'])],
                                  navigators=[dict(volume=e+1, slice=sl+1, **s['navigators'][(e, sl)]) for sl in range(s['S']) for e in range(s['E'])],
                                  noise_power_floor=ctx['floors'][n], noise_power_floor_source=ctx['floor_sources'][n]) for n, s in scans.items()})
    summary['roi'] = dict(center_xy=[ROI['cx'], ROI['cy']], interior_radius_px=ROI['r_int'], rim_radii_px=list(ROI['rim']), outside_ring_radii_px=list(ROI['outside']), background=BACKGROUND,
                          edge_line=EDGE_LINE, streak=dict(STREAK, normal_angle_deg=ctx['smasks']['normal_angle_deg']), counts={k: int(m.sum()) for k, m in ctx['masks'].items()},
                          orientation='image[row, col]; x = column (readout), y = row (phase encode); NIfTI is the transpose',
                          selection='Fixed across scans/modes/b after inspecting uncorrected b0/b1000 images of all ten scans; no registration. Phantom equivalent radius 47 px, centroid (61.1, 73.2). '
                                    'The Oct 7 centre was (61, 71). Interior excludes the boundary and the edge line; background is an empirical corner noise/artifact reference.')
    summary['effective_b_model'] = dict(assumptions=B_ASSUMPTIONS, table=BEFF_TABLE, fit_residuals_max_abs=beff_fit_residuals(),
                                        examples={seq: {str(b): float(effective_b(seq, b)) for b in (0, 100, 500, 1000, 2000, 3000, 6000)} for seq in BEFF_TABLE})
    summary['bd_prediction_table'] = BD_PRED
    summary['alignment'] = alignment(scans)
    summary['measurements'] = ctx['image']; summary['kspace'] = dict(measurements=ctx['kspace'])
    summary['navigator_echoes_csv'] = 'oct10_navigator_echoes.csv'
    summary['edge_widths'] = ctx['widths']; summary['pair_comparisons'] = pair_rows
    summary['edge_line_detection_oct10'] = ctx['detect']; summary['edge_line_detection_oct07'] = detect07
    summary['oct07_reference'] = {n: dict(version=v['version'], b=v['b'].tolist(), L=v['L'], esp=v['esp'], gains=v['gains'], noise_floor=v['noise_floor'], first_nav_norm=v['nav_norm'][:, 0].tolist(), first_nav_amp=v['nav_amp'][:, 0].tolist()) for n, v in o7.items()}
    summary['navigator_limits'] = ('Navigator noise floor is the median navigator-window power estimate (samples 16:48, 80:112, /ln2) over volumes with b>=3000 (no signal); '
                                   'amplitude = sqrt(max(L2^2 - 128*floor, 0)). Navigator L2 includes noise; peak centroid is the power-weighted centroid of 5 samples around the maximum.')
    if '--metrics-only' not in sys.argv:
        figures(scans, ctx, o7, o7img)
    (DATA/'physical_scanner_analysis_2026-10-10.json').write_text(json.dumps(summary, indent=2))
    print('Generated Oct 10 measurements', '' if '--metrics-only' in sys.argv else 'and figures', 'for', len(scans), 'scans;', len(ctx['image']), 'image rows,', len(ctx['kspace']), 'k-space rows,', len(ctx['nav']), 'navigator rows,', len(pair_rows), 'comparison rows')


if __name__ == '__main__':
    main()

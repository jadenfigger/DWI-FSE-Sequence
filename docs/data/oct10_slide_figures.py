"""Figures and numbers for the 2026-10-10 slide deck. Rerunnable; reads only saved NIfTIs, ROI masks and navigator CSV.

Signal S = sqrt(max(mean_ROI(I^2) - 2 sigma^2, 0)), sigma = sqrt(mean(I_bg^2)/2), interior disk ROI (docs/data/oct10_roi_masks.npz,
image orientation = NIfTI array transposed), background = corners rows<20 & (cols<16 or cols>=112).
SNR = mean(I_roi)/(std(I_bg)/0.655).  Effective b = effective_b() of physical_scanner_analysis_2026-10-10.py (E1, +x).
Outputs: docs/figures/oct10_slides/*.png (not sequence_*.png) and docs/data/oct10_slide_numbers.json.
"""
from pathlib import Path
import importlib.util, json
import numpy as np
import pandas as pd
import nibabel as nib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT/'docs/figures/oct10_slides'
OUT.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location('oct10', HERE/'physical_scanner_analysis_2026-10-10.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)

FOLDER = {'A': 'v181_testA', 'C': 'v18_testC', 'B': 'v1911_testB', 'D': 'v191_testD', 'E': 'v181_testE', 'G': 'v1911_testG'}
VERS = {'A': 'v1.81', 'C': 'v1.8', 'B': 'v1.911', 'D': 'v1.91', 'E': 'v1.81', 'G': 'v1.911'}
SEQ = {'A': 'v181', 'C': 'v18', 'B': 'v1911', 'D': 'v191', 'E': 'v181', 'G': 'v1911'}
FIT_NAME = {'A': 'fit_v181_A.png', 'C': 'fit_v18_C.png'}
masks = np.load(HERE/'oct10_roi_masks.npz')
ROI, BG = masks['interior'], masks['background']
RAYLEIGH_STD = 0.655


def load(n):
    d = ROOT/'experiments'/f'FSE-DWI_10-10-2026_{FOLDER[n]}'
    nii = np.asarray(nib.load(d/f'FSE-DWI_10-10-2026_{FOLDER[n]}.nii.gz').dataobj)[:, :, 0, :]   # slice 0
    ims = [nii[:, :, v].T.astype(float) for v in range(nii.shape[2])]                           # image orientation (row, col)
    b = np.loadtxt(d/f'FSE-DWI_10-10-2026_{FOLDER[n]}.bval').ravel()
    bvec = np.loadtxt(d/f'FSE-DWI_10-10-2026_{FOLDER[n]}.bvec').reshape(3, -1)
    return ims, b, bvec


def signal(im):
    sigma = float(np.sqrt(np.mean(im[BG]**2)/2))
    roi = im[ROI]
    raw = float(roi.mean()); S = float(np.sqrt(max(np.mean(roi**2)-2*sigma**2, 0)))
    snr = raw/(float(im[BG].std())/RAYLEIGH_STD)
    return dict(raw_mean=raw, S=S, sigma=sigma, bg_std=float(im[BG].std()), snr=float(snr))


def label(bvec, v, b):
    d = bvec[:, v]
    if b[v] == 0 or not d.any():
        return 'b0'
    return ('-' if d.sum() < 0 else '+')+'xyz'[int(np.argmax(abs(d)))]


def beff(n, b, d='x', echo=1):
    return float(A.effective_b(SEQ[n], b, d, echo))


def loglin(x, S):
    x = np.asarray(x, float); S = np.asarray(S, float)
    ok = S > 0
    sl, ic = np.polyfit(x[ok], np.log(S[ok]), 1)
    pred = sl*x[ok]+ic; y = np.log(S[ok])
    r2 = 1-np.sum((y-pred)**2)/np.sum((y-y.mean())**2)
    pl = np.exp(pred); r2lin = 1-np.sum((S[ok]-pl)**2)/np.sum((S[ok]-S[ok].mean())**2)
    return dict(adc=float(-sl), intercept=float(ic), r2=float(r2), r2_linear_space=float(r2lin), n=int(ok.sum()))


# ---------------------------------------------------------------- navigator
nav = pd.read_csv(HERE/'oct10_navigator_echoes.csv')


def nav_amp(scan, vol, echo):
    r = nav[(nav.scan == scan) & (nav.volume == vol) & (nav.echo == echo)]
    return float(r.noise_sub_amp.iloc[0])


def nav_adc(scan, vlo, vhi, blo, bhi, direction='x', echoes=range(2, 9)):
    nom, eff, ratios = [], [], []
    for e in echoes:
        r = nav_amp(scan, vhi, e)/nav_amp(scan, vlo, e); ratios.append(r)
        nom.append(-np.log(r)/(bhi-blo))
        eff.append(-np.log(r)/(beff(scan, bhi, direction, e)-beff(scan, blo, 'x', e)))
    return dict(nominal=float(np.median(nom)), effective=float(np.median(eff)), median_ratio=float(np.median(ratios)), echoes='2-8')


# ---------------------------------------------------------------- 7-b scans
R = {'meta': dict(signal='S=sqrt(max(mean(I_roi^2)-2 sigma^2,0)); sigma=sqrt(mean(I_bg^2)/2)', snr='mean(I_roi)/(std(I_bg)/0.655)',
                  roi='interior disk (oct10_roi_masks.npz) on nifti.T slice 0; background corners rows<20 & (cols<16|cols>=112)',
                  r2='R^2 of ln S vs b (linear regression); r2_linear_space also stored',
                  units='ADC in mm^2/s (x1e-3 -> *1000)')}
seven = {}
data = {}
for n in 'ACBD':
    ims, b, bvec = load(n); data[n] = (ims, b, bvec)
    assert list(b) == [0, 100, 500, 1000, 2000, 3000, 6000]
    sig = [signal(im) for im in ims]
    S = np.array([s['S'] for s in sig]); bn = b.copy()
    be = np.array([beff(n, x) for x in b])
    fsel = (b >= 100) & (b <= 3000)
    fit_nom = loglin(bn[fsel], S[fsel]); fit_eff = loglin(be[fsel], S[fsel])
    two_nom = float(np.log(S[0]/S[3])/1000); two_eff = float(np.log(S[0]/S[3])/(be[3]-be[0]))
    app_nom = {int(bb): float(np.log(S[1]/S[i])/(bb-100)) if S[i] > 0 else None for i, bb in enumerate(b) if bb in (500, 1000, 2000, 3000)}
    app_eff = {int(bb): float(np.log(S[1]/S[i])/(be[i]-be[1])) if S[i] > 0 else None for i, bb in enumerate(b) if bb in (500, 1000, 2000, 3000)}
    seven[n] = dict(version=VERS[n], b_nominal=b.tolist(), b_effective=be.tolist(), S_corrected=S.tolist(), raw_roi_mean=[s['raw_mean'] for s in sig],
                    sigma_bg=[s['sigma'] for s in sig], snr=[s['snr'] for s in sig],
                    fit_nominal_b100_3000=fit_nom, fit_effective_b100_3000=fit_eff,
                    two_point_b0_b1000_nominal=two_nom, two_point_b0_b1000_effective=two_eff,
                    apparent_adc_from_b100_nominal=app_nom, apparent_adc_from_b100_effective=app_eff,
                    navigator_echoes_2_8_b0_b1000=nav_adc(n, 1, 4, 0, 1000),
                    navigator_echo1_noise_sub_amp=[nav_amp(n, v, 1) for v in range(1, 8)])
R['seven_b_scans'] = {n: seven[n] for n in 'ACBD'}

# ---------------------------------------------------------------- fig 1
for n in 'AC':
    s = seven[n]; b = np.array(s['b_nominal']); S = np.array(s['S_corrected']); m = b <= 3000
    f = s['fit_nominal_b100_3000']
    fig = plt.figure(figsize=(6.4, 4.8))
    plt.semilogy(b[m], S[m], 'o', label='measured')
    bb = np.linspace(0, 3000, 200)
    plt.plot(bb, np.exp(f['intercept']-f['adc']*bb), label=f'fit: ADC={f["adc"]:.5f} mm^2/s, R^2={f["r2"]:.3f}')
    plt.title(f'FSE-DWI_10-10-2026_{FOLDER[n]} slice 1'); plt.xlabel('b (s/mm^2)'); plt.ylabel('signal'); plt.legend(loc='upper right')
    fig.savefig(OUT/FIT_NAME[n], dpi=180); plt.close(fig)

# ---------------------------------------------------------------- fig 2/3
order = [('C', 'v1.8'), ('A', 'v1.81'), ('D', 'v1.91'), ('B', 'v1.911')]
curves = {n: dict(nominal_x=[500, 1000, 2000, 3000], nominal_y=[seven[n]['apparent_adc_from_b100_nominal'][x]*1e3 for x in (500, 1000, 2000, 3000)],
                  effective_x=[seven[n]['b_effective'][i] for i in (2, 3, 4, 5)], effective_y=[seven[n]['apparent_adc_from_b100_effective'][x]*1e3 for x in (500, 1000, 2000, 3000)]) for n, _ in order}
allv = [v for c in curves.values() for v in c['nominal_y']+c['effective_y'] if v is not None and np.isfinite(v)]
pad = 0.05*(max(allv)-min(allv)); YL = (min(allv)-pad, max(allv)+pad)
R['apparent_adc_curves_x1e-3_mm2_s'] = {VERS[n]+f' ({n})': c for n, c in curves.items()}
R['apparent_adc_ylim'] = YL


def draw(ax, kind):
    for n, lab in order:
        c = curves[n]
        ax.plot(c[kind+'_x'], c[kind+'_y'], 'o-', label=lab)
    ax.grid(alpha=0.3); ax.set_ylim(*YL)


YLAB = 'Apparent ADC from b=100 reference (×10⁻³ mm²/s)'
for kind, xl, fn in (('nominal', 'Nominal b-value (s/mm²)', 'apparent_adc_nominal.png'), ('effective', 'Effective b-value (s/mm²)', 'apparent_adc_effective.png')):
    fig, ax = plt.subplots(figsize=(8.4, 5.4)); draw(ax, kind)
    ax.set_title('Apparent ADC vs. b-value by sequence'); ax.set_xlabel(xl); ax.set_ylabel(YLAB); ax.legend(title='Sequence')
    fig.tight_layout(); fig.savefig(OUT/fn, dpi=200); plt.close(fig)
fig, axs = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
for ax, kind, t, xl in zip(axs, ('nominal', 'effective'), ('Nominal b', 'Effective b'), ('Nominal b-value (s/mm²)', 'Effective b-value (s/mm²)')):
    draw(ax, kind); ax.set_title(t); ax.set_xlabel(xl)
axs[0].set_ylabel(YLAB); axs[1].legend(title='Sequence')
fig.tight_layout(); fig.savefig(OUT/'adc_nominal_vs_effective.png', dpi=200); plt.close(fig)

# ---------------------------------------------------------------- directions
dirs = {}
for n in 'EG':
    ims, b, bvec = load(n); data[n] = (ims, b, bvec)
    labs = [label(bvec, v, b) for v in range(len(b))]
    assert labs == ['b0', '+x', '-x', '+y', '+z', '+x', '+y', '+z'] and list(b) == [0, 1000, 1000, 1000, 1000, 3000, 3000, 3000], (labs, b)
    sig = [signal(im) for im in ims]; S = [s['S'] for s in sig]
    beff_x = beff(n, 1000)-beff(n, 0)
    rows = {}
    for v in (1, 2, 3, 4):
        d = labs[v]
        a_nom = float(np.log(S[0]/S[v])/1000)
        a_eff = float(np.log(S[0]/S[v])/beff_x) if d != '+z' else None    # z cross term unknown -> nominal only
        ratio = [nav_amp(n, v+1, e)/nav_amp(n, 1, e) for e in range(2, 9)]
        med = float(np.median(ratio))
        rows[d] = dict(S_b0=S[0], S_b1000=S[v], raw_roi_mean_b1000=sig[v]['raw_mean'], adc_nominal=a_nom, adc_effective=a_eff,
                       nav_median_ratio_echo2_8=med, nav_adc_nominal=float(-np.log(med)/1000),
                       nav_adc_effective=float(-np.log(med)/beff_x) if d != '+z' else None)
    out = dict(version=VERS[n], b_eff_diff_b1000_minus_b0_used=beff_x, labels=labs, b0_S=S[0], snr_b0=sig[0]['snr'], rows=rows)
    for key in ('adc_nominal', 'adc_effective', 'nav_adc_nominal', 'nav_adc_effective'):
        vals = {d: rows[d][key] for d in rows if rows[d][key] is not None}
        mean = float(np.mean(list(vals.values()))); out[f'mean_{key}'] = mean
        out[f'mean_{key}_note'] = 'mean over ' + ','.join(vals)
        for d in vals:
            rows[d][f'{key}_pct_diff_from_mean'] = float((vals[d]-mean)/mean*100)
    out['note'] = 'effective b = b_eff(1000)-b_eff(0) (x value) used for +x,-x,+y; +z shown nominal only (z cross term unknown); effective means over x,-x,y'
    dirs[n] = out
R['directions'] = dirs

# ---------------------------------------------------------------- image panels
panels = {}
for col_b, vi in ((0, {'A': 0, 'B': 0}), (1000, {'A': 3, 'B': 3})):
    p995 = {n: float(np.percentile(data[n][0][vi[n]], 99.5)) for n in 'AB'}
    vmax = 1.05*max(p995.values())
    for n in 'AB':
        im = data[n][0][vi[n]]
        assert data[n][1][vi[n]] == col_b
        fig = plt.figure(figsize=(3.44, 2.86), facecolor='black')
        ax = fig.add_axes([0.01, 0.01, 0.80, 0.98]); h = ax.imshow(im, cmap='gray', vmin=0, vmax=vmax, interpolation='nearest'); ax.axis('off')
        cb = fig.colorbar(h, cax=fig.add_axes([0.83, 0.04, 0.04, 0.92]))
        cb.ax.yaxis.set_tick_params(color='white', labelcolor='white'); cb.outline.set_edgecolor('white')
        fig.savefig(OUT/f'img_{n}_b{col_b}.png', dpi=200, facecolor='black'); plt.close(fig)
        s = signal(im)
        panels[f'img_{n}_b{col_b}'] = dict(version=VERS[n], b=col_b, snr=s['snr'], roi_mean=s['raw_mean'], S_corrected=s['S'], vmax=vmax, p99_5=p995[n], p99_5_both=p995)
R['image_panels'] = panels

# ---------------------------------------------------------------- echo train
fig, ax = plt.subplots(figsize=(8.4, 5.4))
et = {}
for n, t0, dt, c, lab in (('A', 54, 14, 'tab:blue', 'v1.81'), ('B', 72.7, 13, 'tab:orange', 'v1.911')):
    te = [t0+dt*(k-1) for k in range(1, 9)]
    for vol, b, ls, st in ((1, 0, 'o-', 'b=0'), (4, 1000, 'o--', 'b=1000')):
        amp = [nav_amp(n, vol, e) for e in range(1, 9)]
        ax.plot(te, amp, ls, color=c, label=f'{lab} {st}')
        et[f'{n}_b{b}'] = dict(echo_time_ms=te, amplitude=amp)
ax.grid(alpha=0.3); ax.set_title('Echo-train signal (navigator)'); ax.set_xlabel('Echo time (ms)'); ax.set_ylabel('Signal (a.u.)'); ax.legend()
fig.tight_layout(); fig.savefig(OUT/'echo_train.png', dpi=200); plt.close(fig)
R['echo_train_navigator'] = et
R['navigator_echo1'] = {k: v['amplitude'][0] for k, v in et.items()}

(HERE/'oct10_slide_numbers.json').write_text(json.dumps(R, indent=2))
print('done', sorted(p.name for p in OUT.glob('*.png')))

"""Report figures and the supporting numbers for 2026-10-12 (run after oct12_rois.py and oct12_roi_analysis.py).

Figures -> docs/figures/physical_scanner_2026-10-12/; numbers -> docs/data/oct12_extra_results.json
  overview_exvivo.png, overview_invivo.png   image montages (centre slice), brain SNR annotated
  md_maps.png                                mean-diffusivity maps, low-b and high-b
  snr_summary.png                            b10/b0 SNR and SNR efficiency, ex vivo and in vivo
  adc_summary.png                            PBS ADC by direction/slice, brain low-b vs high-b ADC, in-vivo ADC
  ssmgot_lr.png                              why the in-vivo ss-MGOT b10 image is bright top-left
  etl16_vs_etl8.png                          ETL 16 vs 8: images, depth SNR, echo train, PE point-spread
"""
import csv, json
import numpy as np
from scipy import ndimage as ndi
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from oct12_load import load, load_epi, ROOT
from oct12_rois import NOISE_COLS_IV, NOISE_COLS_EX
from shot_navigator import readout_projection

FIG = ROOT/'docs/figures/physical_scanner_2026-10-12'
DATA = ROOT/'docs/data'
C = {'v1.83': '#2a78d6', 'v1.912': '#eb6834', 'EPI': '#1baf7a'}
INK, INK2, GRID = '#0b0b0b', '#52514e', '#e4e3df'
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': INK2, 'axes.labelcolor': INK, 'xtick.color': INK2,
                     'ytick.color': INK2, 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.6, 'figure.facecolor': '#fcfcfb',
                     'axes.facecolor': '#fcfcfb', 'savefig.facecolor': '#fcfcfb'})
MASK = dict(np.load(DATA/'oct12_roi_masks.npz'))
ROWS = list(csv.DictReader(open(DATA/'oct12_roi_signals.csv')))
BEFF = {(r['scan'], int(r['volume'])-1): float(r['trace_s_mm2'])
        for r in csv.DictReader(open(DATA/'oct12_effective_b.csv')) if r['echo'] == '1'}
EXTRA = {}


def sig_bg(I, cols):
    return float(np.sqrt(np.mean(I[4:124, cols]**2)/2))


def snr_of(scan, roi, b, d, recon='off'):
    for r in ROWS:
        if r['scan'] == scan and r['roi'] == roi and float(r['b']) == b and r['dir'] == d and (r['recon'] == recon or scan.startswith('epi')):
            return float(r['snr'])
    return None


def bare(ax):
    ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)


def panel(ax, im, title='', vmax=None, note=None):
    ax.imshow(im, cmap='gray', vmin=0, vmax=vmax if vmax is not None else np.percentile(im, 99.5), interpolation='nearest')
    ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    if title:
        ax.set_title(title, fontsize=8, color=INK)
    if note:
        ax.text(0.03, 0.04, note, transform=ax.transAxes, color='w', fontsize=7, va='bottom')


# ---------------------------------------------------------------- overview montages
def overview_exvivo():
    spec = [('Q', 'v1.83 Q (3 slices, nav 1)', [(0, 'b10'), (1, 'b1000 x'), (6, 'b3000 z'), (None, '')]),
            ('R', 'v1.912 R (3 slices, nav 2)', [(0, 'b10'), (1, 'b1000 x'), (6, 'b3000 z'), (None, '')]),
            ('M', 'v1.83 M (1 slice)', [(0, 'b10'), (1, 'b1000 x'), (2, 'b3000 z'), (3, 'b6000 z')]),
            ('O', 'v1.912 O (1 slice)', [(0, 'b10'), (1, 'b1000 x'), (2, 'b3000 z'), (3, 'b6000 z')]),
            ('epi0', 'EPI (2-mm slice, 16 shots)', [(0, 'b0'), (1, 'b1000 y'), (None, ''), (2, 'b6000 z')])]
    fig, ax = plt.subplots(len(spec), 4, figsize=(9.2, 11.6))
    brain = MASK['ex_brain']
    for i, (k, lab, cols) in enumerate(spec):
        if k.startswith('epi'):
            e = load_epi(k); img = e['img'][:, 1]; b = e['b']; dirs = None
        else:
            s = load(k); c = int(np.argmin(np.abs(s['offsets_mm']))) if s['offsets_mm'] else 0; img = s['img'][:, c]; b = s['b']
        for j, (v, t) in enumerate(cols):
            a = ax[i, j]
            if v is None:
                a.axis('off'); continue
            im = img[v][10:126, 8:120]
            vmax = np.percentile(img[v][brain], 99.5) if v else np.percentile(img[v], 99.5)
            roi = 'ex_brain'
            d = '0' if b[v] <= 10 else ('+x' if 'x' in t else '+y' if 'y' in t else '+z')
            snr = snr_of(k, roi, float(b[v]), d)
            panel(a, im, t if i == 0 or k in ('M', 'epi0') else t, vmax, f'brain SNR {snr:.0f}' if snr is not None else None)
        ax[i, 0].text(-0.06, 0.5, lab, transform=ax[i, 0].transAxes, rotation=90, ha='right', va='center', fontsize=8, color=INK)
    fig.suptitle('Ex vivo, centre slice (b>10 panels windowed to the brain)', fontsize=10, color=INK)
    plt.tight_layout(); plt.savefig(FIG/'overview_exvivo.png', dpi=150); plt.close()


def overview_invivo():
    names = [('b10', 0, '0')] + [(f'b{b} {d}', i, f'+{d}') for i, (b, d) in enumerate(
        [(1000, 'x'), (1000, 'y'), (1000, 'z'), (3000, 'x'), (3000, 'y'), (3000, 'z'), (6000, 'x'), (6000, 'y'), (6000, 'z')], start=1)]
    a = load('iA'); bb = load('iB'); e = load_epi('epiA')
    rows = [('iA', 'v1.83 iA', a['img'][:, 3], a['b']), ('iB', 'v1.912 iB', bb['img'][:, 1], bb['b']), ('epiA', 'EPI', e['img'][:, 1], e['b'])]
    fig, ax = plt.subplots(3, 10, figsize=(16, 5.4))
    m = MASK['iv_brain']
    for i, (k, lab, img, b) in enumerate(rows):
        for j, (t, v, d) in enumerate(names):
            im = img[v][38:100, 22:106]
            vmax = np.percentile(img[v][m], 99.5)
            snr = snr_of(k, 'iv_brain', float(b[v]), d)
            panel(ax[i, j], im, t if i == 0 else '', vmax, f'{snr:.0f}' if snr is not None else None)
        ax[i, 0].text(-0.08, 0.5, lab, transform=ax[i, 0].transAxes, rotation=90, ha='right', va='center', fontsize=9, color=INK)
    fig.suptitle('In vivo, centre slice (0 mm); each panel windowed to its own brain; number = whole-brain SNR', fontsize=10, color=INK)
    plt.tight_layout(); plt.savefig(FIG/'overview_invivo.png', dpi=150); plt.close()


# ---------------------------------------------------------------- MD maps
def md_map(img, b, idx0, triples, sm=0.7):
    I = ndi.gaussian_filter(img, (0, sm, sm))
    g = np.exp(np.mean([np.log(np.maximum(I[i], 1e-9)) for i in triples], 0))
    return g, I[idx0]


def md_maps():
    fig, ax = plt.subplots(2, 4, figsize=(13, 6.6))
    a = load('iA'); bb = load('iB'); e = load_epi('epiA'); q = load('Q'); r = load('R')
    def beff(k, v, nominal):
        return BEFF.get((k, v), nominal)
    entries = [
        (ax[0, 0], 'Ex vivo v1.83 Q', q['img'][:, 1], 'Q', q['b'], MASK['ex_brain'] | MASK['ex_pbs'], (0, [1, 2, 3], [4, 5, 6])),
        (ax[0, 1], 'Ex vivo v1.912 R', r['img'][:, 1], 'R', r['b'], np.roll(MASK['ex_brain'] | MASK['ex_pbs'], 2, 0), (0, [1, 2, 3], [4, 5, 6])),
        (ax[1, 0], 'In vivo v1.83 iA', a['img'][:, 3], 'iA', a['b'], MASK['iv_brain'], (0, [1, 2, 3], [4, 5, 6])),
        (ax[1, 1], 'In vivo v1.912 iB', bb['img'][:, 1], 'iB', bb['b'], MASK['iv_brain'], (0, [1, 2, 3], [4, 5, 6])),
        (ax[1, 2], 'In vivo EPI', e['img'][:, 1], 'epiA', e['b'], MASK['iv_brain'], (0, [1, 2, 3], [4, 5, 6])),
    ]
    out = {}
    for axx, title, img, key, b, mask, (i0, s1, s3) in entries:
        g1, s0 = md_map(img, b, i0, s1); g3, _ = md_map(img, b, i0, s3)
        b0 = beff(key, i0, b[i0]); b1 = np.mean([beff(key, v, b[v]) for v in s1]); b3 = np.mean([beff(key, v, b[v]) for v in s3])
        md_low = np.log(np.maximum(s0, 1e-9)/np.maximum(g1, 1e-9))/(b1-b0)*1e3
        md_high = np.log(np.maximum(g1, 1e-9)/np.maximum(g3, 1e-9))/(b3-b1)*1e3
        vmax = 2.2 if 'Ex' in title else 1.2
        im = axx.imshow(np.where(mask, md_low, np.nan), cmap='viridis', vmin=0, vmax=vmax, interpolation='nearest')
        axx.set_title(f'{title}\nGM-ADC, b_ref→b1000', fontsize=8); axx.set_xticks([]); axx.set_yticks([]); axx.grid(False)
        if 'Ex' in title:
            axx.set_ylim(126, 20); axx.set_xlim(10, 118)
        else:
            axx.set_ylim(96, 44); axx.set_xlim(30, 100)
        plt.colorbar(im, ax=axx, fraction=0.04, label='×10⁻³ mm²/s')
        if key in ('Q', 'R'):
            brain_mask, pbs_mask = MASK['ex_brain'], MASK['ex_pbs']
            mask_label = 'pooled ex_brain + ex_pbs (legacy plotted mask)'
        else:
            brain_mask, pbs_mask = mask, np.zeros_like(mask, dtype=bool)
            mask_label = 'iv_brain'
        out[key] = dict(
            mask=mask_label,
            md_low_median_pooled=float(np.nanmedian(md_low[mask])),
            md_high_median_pooled=float(np.nanmedian(md_high[mask])),
            md_low_median_brain=float(np.nanmedian(md_low[brain_mask])),
            md_high_median_brain=float(np.nanmedian(md_high[brain_mask])),
            md_low_median_pbs=float(np.nanmedian(md_low[pbs_mask])) if pbs_mask.any() else None,
            md_high_median_pbs=float(np.nanmedian(md_high[pbs_mask])) if pbs_mask.any() else None,
            descriptive_only=True,
            smoothing_sigma_px=0.7,
            noise_floor_clipping='none; denominator/signal floors use 1e-9 only',
        )
    # high-b MD maps in vivo, FSE vs EPI
    for axx, key, img, b in [(ax[0, 2], 'iA', a['img'][:, 3], a['b']), (ax[0, 3], 'epiA', e['img'][:, 1], e['b'])]:
        g1, _ = md_map(img, b, 0, [1, 2, 3]); g3, _ = md_map(img, b, 0, [4, 5, 6])
        b1 = np.mean([beff(key, v, b[v]) for v in [1, 2, 3]]); b3 = np.mean([beff(key, v, b[v]) for v in [4, 5, 6]])
        md_high = np.log(np.maximum(g1, 1e-9)/np.maximum(g3, 1e-9))/(b3-b1)*1e3
        im = axx.imshow(np.where(MASK['iv_brain'], md_high, np.nan), cmap='viridis', vmin=0, vmax=1.2, interpolation='nearest')
        axx.set_title(f"In vivo {'v1.83 iA' if key == 'iA' else 'EPI'}\nGM-ADC, b1000→b3000", fontsize=8)
        axx.set_ylim(96, 44); axx.set_xlim(30, 100); bare(axx)
        plt.colorbar(im, ax=axx, fraction=0.04, label='×10⁻³ mm²/s')
    ax[1, 3].axis('off')
    ax[1, 3].text(0, 0.9, 'Descriptive two-point GM-ADC maps, not tensor MD.\nSignals smoothed σ=0.7 px; no noise-floor correction.\nTop ex-vivo mask: brain + PBS; pooled median is PBS-dominated.\nLow-b ref: FSE b10 (+x), EPI b0; FSE model b, EPI nominal b.', fontsize=7.3, color=INK2, va='top')
    plt.tight_layout(); plt.savefig(FIG/'md_maps.png', dpi=150); plt.close()
    EXTRA['md_map_medians'] = out


# ---------------------------------------------------------------- SNR summary
def snr_summary():
    fig, ax = plt.subplots(2, 2, figsize=(11, 7.2))
    ex = [('A', 'A 20 kHz'), ('B', 'B'), ('M', 'M 1 sl'), ('Q', 'Q 3 sl'), ('Q1', 'Q1 7 sl'), ('C', 'C 1 sl'), ('O', 'O 1 sl'), ('R', 'R 3 sl'), ('epi0', 'EPI')]
    iv = [('iA', 'iA TR2 1mm'), ('iD', 'iD TR3 1mm'), ('iE', 'iE TR3 2mm TE54'), ('iF', 'iF ETL16'), ('iB', 'iB 3 sl'), ('iC', 'iC 1 sl'), ('epiA', 'EPI 2mm')]
    def seq(k):
        return 'EPI' if k.startswith('epi') else ('v1.912' if k in ('C', 'O', 'R', 'iB', 'iC') else 'v1.83')
    def get(k, roi, field):
        b = 0.0 if k.startswith('epi') else 10.0
        for r in ROWS:
            if r['scan'] == k and r['roi'] == roi and float(r['b']) == b and r['dir'] == '0' and r['recon'] in ('off', 'vendor-kspace FFT'):
                return float(r[field])
    for col, (field, ylab) in enumerate([('snr', 'b10 / b0 SNR'), ('snr_eff', 'SNR / √(s per volume) / µL')]):
        a = ax[0, col]; x = np.arange(len(ex)); w = 0.38
        for off, roi, hatch in [(-w/2, 'ex_pbs', None), (w/2, 'ex_brain', '//')]:
            vals = [get(k, roi, field) for k, _ in ex]
            a.bar(x+off, vals, w-0.04, color=[C[seq(k)] for k, _ in ex], hatch=hatch, edgecolor='#fcfcfb', linewidth=0.5)
        a.set_xticks(x); a.set_xticklabels([l for _, l in ex], rotation=35, ha='right', fontsize=8); a.set_ylabel(ylab)
        a.set_title(f'Ex vivo — PBS (solid) and brain (hatched)', fontsize=9)
        a = ax[1, col]; x = np.arange(len(iv))
        vals = [get(k, 'iv_brain', field) for k, _ in iv]
        a.bar(x, vals, 0.6, color=[C[seq(k)] for k, _ in iv])
        for xi, v in zip(x, vals):
            a.text(xi, v, f'{v:.0f}', ha='center', va='bottom', fontsize=7, color=INK)
        a.set_xticks(x); a.set_xticklabels([l for _, l in iv], rotation=35, ha='right', fontsize=8); a.set_ylabel(ylab)
        a.set_title('In vivo — whole brain', fontsize=9)
    handles = [plt.Rectangle((0, 0), 1, 1, color=C[s]) for s in C]
    fig.legend(handles, list(C), loc='upper center', ncol=3, frameon=False)
    plt.tight_layout(rect=(0, 0, 1, 0.96)); plt.savefig(FIG/'snr_summary.png', dpi=150); plt.close()


def snr_summary_audited():
    """Audited SNR/time summary; uses geometry-scaled R ROI and exposes EPI voxel conventions."""
    audit = json.load(open(DATA/'oct12_quant_audit.json'))
    rmeta = audit['r_geometry']['metrics']
    fig, ax = plt.subplots(2, 3, figsize=(13.5, 7.4))
    ex_scans = ['Q', 'R', 'epi0']
    iv_scans = ['iA', 'iB', 'epiA']
    colors = {'Q': C['v1.83'], 'R': C['v1.912'], 'epi0': C['EPI'],
              'iA': C['v1.83'], 'iB': C['v1.912'], 'epiA': C['EPI']}

    def sample(k, roi):
        recon = 'vendor-kspace FFT' if k.startswith('epi') else 'off'
        b_ref = 0.0 if k.startswith('epi') else 10.0
        r = next(x for x in ROWS if x['scan'] == k and x['roi'] == roi and
                 x['recon'] == recon and float(x['b']) == b_ref and x['dir'] == '0')
        snr = float(r['snr']); t = float(r['t_vol_s'])
        vol_old = float(r['voxel_ul'])
        if k == 'R':
            rr = rmeta[roi]
            snr = float(rr['R_b10_snr_geometry_roi'])
            vol = float(rr['R_b10_voxel_ul_geometry'])
        elif k.startswith('epi'):
            vol = float(audit['epi_geometry']['roi_grid_voxel_ul'])
        else:
            vol = vol_old
        voxel_eff = snr / np.sqrt(t) / vol
        if k.startswith('epi'):
            # Keep the historical native-168 divisor as an explicitly labelled sensitivity convention.
            voxel_eff_native = float(r['snr']) / np.sqrt(t) / vol_old
        else:
            voxel_eff_native = voxel_eff
        return snr, snr / np.sqrt(t), voxel_eff_native, voxel_eff

    def row_plot(row, scans, rois, labels, title):
        for col, metric in enumerate(range(4)):
            if col == 3:
                continue
            a = ax[row, col]
            x = np.arange(len(scans)); width = 0.34 if len(rois) == 2 else 0.58
            for oi, roi in enumerate(rois):
                vals = [sample(k, roi)[metric] for k in scans]
                off = (oi - (len(rois)-1)/2) * width
                a.bar(x + off, vals, width * 0.88,
                      color=[colors[k] for k in scans], hatch='//' if roi in ('ex_brain', 'iv_brain') and row == 0 else None,
                      edgecolor='#fcfcfb', linewidth=0.5)
                if row == 0 and len(rois) == 2:
                    # The panels are deliberately small; legend explains hatch semantics.
                    pass
            a.set_xticks(x); a.set_xticklabels(labels, rotation=20, ha='right', fontsize=8)
            a.set_title(['Measured b10 / b0 SNR', 'SNR / √(volume time)', ''][col], fontsize=9)
            if col == 0: a.set_ylabel(title)
            a.grid(axis='x', visible=False)

    # Two main metrics in the first two columns.
    for row, scans, rois, labels, title in [
        (0, ex_scans, ['ex_pbs', 'ex_brain'], ['Q 1.83', 'R 1.912*', 'EPI'], 'Ex vivo'),
        (1, iv_scans, ['iv_brain'], ['iA 1.83', 'iB 1.912', 'EPI'], 'In vivo whole brain'),
    ]:
        for col, metric in enumerate((0, 1)):
            a = ax[row, col]; x = np.arange(len(scans))
            if len(rois) == 2:
                width = 0.34
                for oi, roi in enumerate(rois):
                    vals = [sample(k, roi)[metric] for k in scans]
                    off = (oi - 0.5) * width
                    a.bar(x + off, vals, width * .88, color=[colors[k] for k in scans],
                          hatch='//' if roi == 'ex_brain' else None,
                          edgecolor='#fcfcfb', linewidth=.5)
                if row == 0 and col == 0:
                    a.legend(handles=[plt.Rectangle((0,0),1,1,facecolor='#777',edgecolor='#777',label='PBS'),
                                      plt.Rectangle((0,0),1,1,facecolor='#fff',edgecolor='#333',hatch='///',label='brain')],
                             frameon=False, fontsize=8, loc='upper right')
            else:
                vals = [sample(k, rois[0])[metric] for k in scans]
                a.bar(x, vals, .58, color=[colors[k] for k in scans], edgecolor='#fcfcfb', linewidth=.5)
            a.set_xticks(x); a.set_xticklabels(labels, rotation=20, ha='right', fontsize=8)
            a.set_title('Measured b10 / b0 SNR' if metric == 0 else 'SNR / √(volume time)', fontsize=9)
            a.set_ylabel(title); a.grid(axis='x', visible=False)

    # Voxel-normalized comparison: explicitly plot both EPI voxel assumptions.
    for row, scans, rois, labels in [
        (0, ex_scans, ['ex_pbs', 'ex_brain'], ['Q 1.83', 'R 1.912*', 'EPI']),
        (1, iv_scans, ['iv_brain'], ['iA 1.83', 'iB 1.912', 'EPI']),
    ]:
        a = ax[row, 2]; x = np.arange(len(scans))
        if len(rois) == 2:
            width = .34
            for oi, roi in enumerate(rois):
                vals = []
                for k in scans:
                    sample_values = sample(k, roi)
                    vals.append(sample_values[2] if k.startswith('epi') else sample_values[3])
                off = (oi - .5) * width
                a.bar(x + off, vals, width * .88, color=[colors[k] for k in scans],
                      hatch='//' if roi == 'ex_brain' else None,
                      edgecolor='#fcfcfb', linewidth=.5)
            if row == 0:
                # Native-168 divisor shown as a hollow outline over the EPI bars.
                for oi, roi in enumerate(rois):
                    a.bar(x[-1] + (oi-.5)*width, sample('epi0', roi)[2], width*.88,
                          fill=False, edgecolor=colors['epi0'], linewidth=1.4, hatch='..')
        else:
            vals = [sample(k, rois[0])[3] for k in scans]
            a.bar(x, vals, .58, color=[colors[k] for k in scans], edgecolor='#fcfcfb', linewidth=.5)
            a.bar(x[-1], sample(scans[-1], rois[0])[2], .58, fill=False,
                  edgecolor=colors[scans[-1]], linewidth=1.4, hatch='..')
        a.set_xticks(x); a.set_xticklabels(labels, rotation=20, ha='right', fontsize=8)
        a.set_title('SNR / √(volume time) / voxel volume', fontsize=9)
        a.set_ylabel('µL⁻¹·s⁻½'); a.grid(axis='x', visible=False)

    fig.suptitle('October 12 SNR comparison — descriptive, reconstruction-dependent', fontsize=11)
    fig.text(.5, .012,
             '* R uses Q-defined ROIs transformed with the measured PE scale. Filled EPI bars: 128-pixel ROI grid, assuming 35-mm FOV.\n'
             'Dotted EPI outlines: stored 168-native-pixel divisor. EPI σ uses vendor-processed k-space; FSE σ uses plain FFT.\n'
             'Reconstruction and noise correlation differ. Reference is FSE b10 and EPI b0.',
             ha='center', va='bottom', fontsize=7.2, color=INK2)
    plt.tight_layout(rect=(0, .105, 1, .94)); plt.savefig(FIG/'snr_summary_audited.png', dpi=160); plt.close()


# ---------------------------------------------------------------- ADC summary
def adc_summary():
    res = json.load(open(DATA/'oct12_roi_results.json'))['adc']
    fig, ax = plt.subplots(2, 2, figsize=(11.5, 8))
    # (a) PBS ADC by direction (effective b), centre slice
    a = ax[0, 0]
    scans = [('C', 'v1.912'), ('M', 'v1.83'), ('O', 'v1.912'), ('Q', 'v1.83'), ('R', 'v1.912'), ('Q1', 'v1.83'), ('epi0', 'EPI')]
    mk = {'+x': 'o', '+y': 's', '+z': '^'}
    for i, (k, sq) in enumerate(scans):
        recon = 'vendor-kspace FFT' if k.startswith('epi') else 'off'
        d = res.get(f'{k}|{recon}|ex_pbs', {})
        for dd, m in mk.items():
            e = d.get(f'b1000{dd}')
            if e:
                a.scatter(i + {'+x': -0.15, '+y': 0, '+z': 0.15}[dd], e.get('adc_eff', e['adc_nom']), marker=m, s=42, color=C[sq], edgecolor='#fcfcfb', linewidth=1, zorder=3)
    a.set_xticks(range(len(scans))); a.set_xticklabels([k for k, _ in scans]); a.set_ylabel('PBS ADC b_ref→b1000 (×10⁻³ mm²/s)')
    a.set_title('PBS ADC by direction (○ x  □ y  △ z), effective b', fontsize=9); a.set_ylim(1.6, 2.1)
    # (b) PBS ADC vs slice offset
    a = ax[0, 1]
    ps = EXTRA.get('pbs_adc_by_slice', {})
    for k, sq, ls in [('Q', 'v1.83', '-'), ('Q1', 'v1.83', ':'), ('R', 'v1.912', '-')]:
        for dd, m in mk.items():
            pts = sorted((float(off), v[dd]) for off, v in ps.get(k, {}).items())
            if pts:
                a.plot(*zip(*pts), ls=ls, marker=m, color=C[sq], ms=5, lw=1.4, label=f'{k} {dd}' if dd == '+x' else None)
    a.set_xlabel('slice offset (mm)'); a.set_ylabel('PBS ADC (×10⁻³ mm²/s)'); a.set_ylim(1.6, 2.1)
    a.set_title('PBS ADC across slices (Q solid, Q1 dotted; ○x □y △z)', fontsize=9)
    # (c) brain: low-b vs high-b ADC
    a = ax[1, 0]
    lab = [('C', 1, 'v1.912'), ('M', 1, 'v1.83'), ('O', 1, 'v1.912'), ('Q', 3, 'v1.83'), ('R', 3, 'v1.912'), ('Q1', 7, 'v1.83')]
    for i, (k, nsl, sq) in enumerate(lab):
        d = res[f'{k}|off|ex_brain']['b1000+x']
        a.scatter(i, d.get('adc_eff', d['adc_nom']), s=48, color=C[sq], marker='o', zorder=3)
        hb = EXTRA.get('brain_highb_adc', {}).get(k)
        if hb is not None:
            a.scatter(i, hb, s=48, color=C[sq], marker='D', zorder=3, edgecolor=INK, linewidth=0.6)
    a.set_xticks(range(len(lab))); a.set_xticklabels([f'{k}\n{n} slice{"s" if n > 1 else ""}' for k, n, _ in lab], fontsize=8)
    a.set_ylabel('brain ADC (×10⁻³ mm²/s)')
    a.set_title('Ex-vivo brain: ● b10→b1000 (x)   ◆ b1000→b3000 (mean x,y,z)', fontsize=9)
    # (d) in vivo per direction and shell
    a = ax[1, 1]
    for i, (k, sq) in enumerate([('iA', 'v1.83'), ('iB', 'v1.912'), ('epiA', 'EPI')]):
        recon = 'vendor-kspace FFT' if k.startswith('epi') else 'off'
        d = res[f'{k}|{recon}|iv_brain']
        for j, shell in enumerate([1000, 3000, 6000]):
            for dd, m in mk.items():
                e = d.get(f'b{shell}{dd}')
                if e:
                    a.scatter(j*4 + i + {'+x': -0.2, '+y': 0, '+z': 0.2}[dd], e.get('adc_eff', e['adc_nom']), marker=m, s=34, color=C[sq], zorder=3, edgecolor='#fcfcfb', linewidth=0.8)
    a.set_xticks([1, 5, 9]); a.set_xticklabels(['b_ref→b1000', 'b_ref→b3000', 'b_ref→b6000'])
    a.set_ylabel('whole-brain ADC (×10⁻³ mm²/s)'); a.set_title('In vivo: v1.83 iA, v1.912 iB, EPI (○x □y △z)', fontsize=9)
    handles = [plt.Line2D([], [], marker='o', ls='', color=C[s], label=s) for s in C]
    fig.legend(handles=handles, loc='upper center', ncol=3, frameon=False)
    plt.tight_layout(rect=(0, 0, 1, 0.96)); plt.savefig(FIG/'adc_summary.png', dpi=150); plt.close()


def adc_summary_audited():
    """ADC view with corrected centre-slice R PBS and brain values, intervals explicit."""
    pbs_adc_by_slice()
    brain_highb_adc()
    audit = json.load(open(DATA/'oct12_quant_audit.json'))['r_geometry']['metrics']
    res = json.load(open(DATA/'oct12_roi_results.json'))['adc']
    fig, ax = plt.subplots(2, 2, figsize=(11.8, 8.2))
    mk = {'+x': 'o', '+y': 's', '+z': '^'}
    # Ex-vivo PBS b10->b1000, model effective b for FSE; EPI uses nominal b.
    a = ax[0, 0]
    scans = [('C', 'v1.912'), ('M', 'v1.83'), ('O', 'v1.912'), ('Q', 'v1.83'),
             ('R', 'v1.912'), ('Q1', 'v1.83'), ('epi0', 'EPI')]
    for i, (k, sq) in enumerate(scans):
        recon = 'vendor-kspace FFT' if k.startswith('epi') else 'off'
        d = res.get(f'{k}|{recon}|ex_pbs', {})
        for dd, m in mk.items():
            ent = d.get(f'b1000{dd}')
            val = ent.get('adc_eff', ent['adc_nom']) if ent else None
            if k == 'R': val = audit['ex_pbs']['R_adc_effective_geometry_roi'][f'b1000{dd}']
            if val is not None:
                a.scatter(i + {'+x': -.15, '+y': 0, '+z': .15}[dd], val,
                          marker=m, s=42, color=C[sq], edgecolor='#fcfcfb', linewidth=1, zorder=3)
    a.set_xticks(range(len(scans))); a.set_xticklabels([k for k, _ in scans])
    a.set_ylabel('PBS ADC, b10→b1000 (×10⁻³ mm²/s)')
    a.set_title('Centre slice, geometry-aware R mask; ○x □y △z', fontsize=9)
    a.set_ylim(1.6, 2.1)
    # Off-centre stays exploratory: legacy translation-only R masks, explicitly labelled.
    a = ax[0, 1]
    ps = EXTRA.get('pbs_adc_by_slice', {})
    for k, sq, ls in [('Q', 'v1.83', '-'), ('Q1', 'v1.83', ':'), ('R', 'v1.912', '-')]:
        for dd, m in mk.items():
            pts = sorted((float(off), vv[dd]) for off, vv in ps.get(k, {}).items())
            if pts:
                a.plot(*zip(*pts), ls=ls, marker=m, color=C[sq], ms=5, lw=1.4,
                       label=f'{k} {dd}' if dd == '+x' else None)
    a.set_xlabel('slice offset (mm)'); a.set_ylabel('PBS ADC (×10⁻³ mm²/s)')
    a.set_ylim(1.6, 2.1); a.set_title('Exploratory off-centre ADC; R uses legacy mask placement', fontsize=9)
    # Brain low-b b10->b1000 and high-b b1000->b3000, both effective b.
    a = ax[1, 0]
    lab = [('C', 1, 'v1.912'), ('M', 1, 'v1.83'), ('O', 1, 'v1.912'),
           ('Q', 3, 'v1.83'), ('R', 3, 'v1.912'), ('Q1', 7, 'v1.83')]
    for i, (k, nsl, sq) in enumerate(lab):
        d = res[f'{k}|off|ex_brain']['b1000+x']
        lo = d.get('adc_eff', d['adc_nom'])
        hb = EXTRA.get('brain_highb_adc', {}).get(k)
        if k == 'R':
            lo = audit['ex_brain']['R_adc_effective_geometry_roi']['b1000+x']
            hb = audit['ex_brain']['R_highb_adc_effective_geometry_roi']['mean']
        if lo is not None: a.scatter(i, lo, s=48, color=C[sq], marker='o', zorder=3)
        if hb is not None: a.scatter(i, hb, s=48, color=C[sq], marker='D', zorder=3, edgecolor=INK, linewidth=.6)
    a.set_xticks(range(len(lab))); a.set_xticklabels([f'{k}\n{nsl} slice{"s" if nsl > 1 else ""}' for k, nsl, _ in lab], fontsize=8)
    a.set_ylabel('brain ADC (×10⁻³ mm²/s)')
    a.set_title('Ex-vivo brain: ● b10→b1000 (+x), ◆ b1000→b3000 (mean x/y/z)', fontsize=9)
    # In vivo comparative panel retains the shell/direction display; references differ.
    a = ax[1, 1]
    for i, (k, sq) in enumerate([('iA', 'v1.83'), ('iB', 'v1.912'), ('epiA', 'EPI')]):
        recon = 'vendor-kspace FFT' if k.startswith('epi') else 'off'
        d = res[f'{k}|{recon}|iv_brain']
        for j, shell in enumerate([1000, 3000, 6000]):
            for dd, m in mk.items():
                ent = d.get(f'b{shell}{dd}')
                if ent:
                    a.scatter(j*4+i+{' +x':-.2, ' +y':0, ' +z':.2}[' '+dd],
                              ent.get('adc_eff', ent['adc_nom']), marker=m, s=34,
                              color=C[sq], zorder=3, edgecolor='#fcfcfb', linewidth=.8)
    a.set_xticks([1, 5, 9]); a.set_xticklabels(['reference→b1000', 'reference→b3000', 'reference→b6000'])
    a.set_ylabel('whole-brain ADC (×10⁻³ mm²/s)')
    a.set_title('In vivo: FSE reference b10; EPI reference b0', fontsize=9)
    direction_handles = [plt.Line2D([], [], marker=m, ls='', color=INK, label=lab)
                         for m, lab in [('o', 'x'), ('s', 'y'), ('^', 'z')]]
    sequence_handles = [plt.Line2D([], [], color=C[sq], lw=3, label=sq)
                        for sq in ('v1.83', 'v1.912', 'EPI')]
    fig.legend(handles=sequence_handles, loc='upper center', ncol=3, frameon=False,
               bbox_to_anchor=(.34, .995))
    fig.legend(handles=direction_handles, loc='upper center', ncol=3, frameon=False,
               bbox_to_anchor=(.76, .995))
    fig.text(.5, .012, 'FSE low-b uses the acquired b10 (+x) reference and modeled effective trace b; EPI low-b uses b0 and nominal b. '
             'High-b brain diamonds use b1000→b3000. Off-centre R points remain exploratory and translation-only.',
             ha='center', va='bottom', fontsize=7.2, color=INK2)
    plt.tight_layout(rect=(0, .05, 1, .95)); plt.savefig(FIG/'adc_summary_audited.png', dpi=160); plt.close()


def pbs_adc_by_slice():
    out = {}
    for k in ['Q', 'Q1', 'R']:
        s = load(k); out[k] = {}
        for sl, off in enumerate(s['offsets_mm']):
            I = s['img'][:, sl]
            r = I[1:4].mean(0)/np.maximum(I[0], 1e-9); rows = np.arange(128)[:, None]*np.ones((1, 128))
            lvl = np.percentile(I[0][(r < 0.3) & (rows < 84)], 75)
            m = ndi.binary_erosion(ndi.binary_opening((r < 0.3) & (I[0] > 0.5*lvl) & (rows < 84)), iterations=3)
            sg = sig_bg(I[0], NOISE_COLS_EX)
            S = [np.sqrt(max(np.mean(I[e][m]**2)-2*sg**2, 0)) for e in range(4)]
            out[k][f'{off:+.1f}'] = {dd: float(np.log(S[0]/S[e])/(BEFF[(k, e)]-BEFF[(k, 0)])*1e3) for e, dd in zip((1, 2, 3), ('+x', '+y', '+z'))}
    EXTRA['pbs_adc_by_slice'] = out


def brain_highb_adc():
    out = {}
    for k in ['Q', 'Q1', 'R']:
        vals = []
        for d1, d3 in [(1, 4), (2, 5), (3, 6)]:
            s1 = s3 = None
            for r in ROWS:
                if r['scan'] == k and r['roi'] == 'ex_brain' and r['recon'] == 'off':
                    if int(r['volume']) == d1: s1 = float(r['signal'])
                    if int(r['volume']) == d3: s3 = float(r['signal'])
            vals.append(np.log(s1/s3)/(BEFF[(k, d3)]-BEFF[(k, d1)])*1e3)
        out[k] = float(np.mean(vals))
    for k in ['iA', 'iB', 'epiA']:
        vals = []
        for d1, d3 in [(1, 4), (2, 5), (3, 6)]:
            s1 = s3 = None
            for r in ROWS:
                if r['scan'] == k and r['roi'] == 'iv_brain' and r['recon'] in ('off', 'vendor-kspace FFT'):
                    if int(r['volume']) == d1: s1 = float(r['signal']); b1 = BEFF.get((k, d1), float(r['b']))
                    if int(r['volume']) == d3: s3 = float(r['signal']); b3 = BEFF.get((k, d3), float(r['b']))
            vals.append(np.log(s1/s3)/(b3-b1)*1e3)
        out[k] = dict(x=float(vals[0]), y=float(vals[1]), z=float(vals[2]), mean=float(np.mean(vals)))
    EXTRA['brain_highb_adc'] = out


# ---------------------------------------------------------------- ss-MGOT left-right
def depth_profiles(keys):
    m = MASK['iv_brain']; out = {}
    for k in keys:
        if k.startswith('epi'):
            e = load_epi(k); im = e['img'][0, 1]; sg = sig_bg(e['mag'][0, 1], np.r_[2:16, 152:166])
        else:
            s = load(k); c = int(np.argmin(np.abs(s['offsets_mm']))); im = s['img'][0, c]; sg = sig_bg(im, NOISE_COLS_IV)
        prof = []
        for r0 in range(53, 89, 2):
            mm = m[r0:r0+2]
            prof.append(float(im[r0:r0+2][mm].mean()/sg) if mm.sum() else np.nan)
        out[k] = prof
    return np.array([(r0+1-53)*0.2734 for r0 in range(53, 89, 2)]), out


def ssmgot_lr():
    a = load('iA'); b = load('iB'); c = load('iC')
    cimg = lambda s, e, sl: np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(s['kspace'][e, sl])))
    A = cimg(a, 0, 3); B = cimg(b, 0, 1)
    sm = lambda X: ndi.gaussian_filter(np.abs(X), 1)
    m = MASK['iv_brain']
    ratio = sm(B)/np.maximum(sm(A), 1e-9)
    dph = np.angle(np.exp(1j*(np.angle(ndi.gaussian_filter(B.real, 1)+1j*ndi.gaussian_filter(B.imag, 1))
                              - np.angle(ndi.gaussian_filter(A.real, 1)+1j*ndi.gaussian_filter(A.imag, 1)))))
    fig, ax = plt.subplots(2, 3, figsize=(13, 7.6))
    for axx, im, t in [(ax[0, 0], np.abs(A), 'v1.83 iA b10 (0 mm)'), (ax[0, 1], np.abs(B), 'v1.912 iB b10 (0 mm)')]:
        panel(axx, im[38:100, 22:106], t)
    im = ax[0, 2].imshow(np.where(m, ratio, np.nan)[38:100, 22:106], cmap='viridis', vmin=0, vmax=0.55, interpolation='nearest')
    ax[0, 2].set_title('iB / iA (receive sensitivity partly cancels\nif geometry is stable)', fontsize=8); bare(ax[0, 2])
    plt.colorbar(im, ax=ax[0, 2], fraction=0.04)
    # scatter: ratio vs v1.83 intensity, left vs right
    Ai = sm(A)/sm(A)[m].max(); col = np.arange(128)[None, :]*np.ones((128, 1))
    L = m & (col < 62); R = m & (col > 66)
    axx = ax[1, 0]
    axx.scatter(Ai[L], ratio[L], s=6, color='#4a3aa7', alpha=0.5, label='left hemisphere (image)')
    axx.scatter(Ai[R], ratio[R], s=6, color='#eda100', alpha=0.5, label='right hemisphere (image)')
    axx.set_xlabel('v1.83 b10 intensity (receive-profile proxy)'); axx.set_ylabel('iB / iA'); axx.legend(frameon=False, fontsize=8)
    axx.set_title('Residual asymmetry at matched v1.83 intensity', fontsize=9)
    im = ax[1, 1].imshow(np.where(m, dph, np.nan)[38:100, 22:106], cmap='twilight', vmin=-np.pi, vmax=np.pi, interpolation='nearest')
    ax[1, 1].set_title('Reconstructed phase difference (high-SNR region)', fontsize=8); bare(ax[1, 1])
    plt.colorbar(im, ax=ax[1, 1], fraction=0.04, label='rad')
    depth, prof = depth_profiles(['iA', 'iB', 'iC', 'epiA'])
    axx = ax[1, 2]
    for k, lab, sq, ls in [('iA', 'v1.83 iA', 'v1.83', '-'), ('iB', 'v1.912 iB', 'v1.912', '-'), ('iC', 'v1.912 iC (1 slice)', 'v1.912', ':'), ('epiA', 'EPI (2 mm)', 'EPI', '-')]:
        axx.plot(depth, prof[k], ls=ls, color=C[sq], lw=2, label=lab)
    axx.set_yscale('log'); axx.set_xlabel('depth below dorsal brain surface (mm)'); axx.set_ylabel('b10/b0 SNR (row mean)')
    axx.legend(frameon=False, fontsize=8); axx.set_title('Depth profile under the surface coil', fontsize=9)
    plt.tight_layout(); plt.savefig(FIG/'ssmgot_lr.png', dpi=150); plt.close()
    # numbers
    lr = {}
    for name, X in [('iA', np.abs(A)), ('iB', np.abs(B)), ('iC', np.abs(cimg(c, 0, 0)))]:
        lr[name] = {f'rows{r0}-{r1}': float(X[r0:r1, 46:60].mean()/X[r0:r1, 68:82].mean()) for r0, r1 in [(52, 62), (62, 72), (72, 85)]}
    EXTRA['ssmgot'] = dict(left_right_ratio=lr, depth_mm=depth.tolist(), depth_snr=prof,
                           ratio_iB_iA_top_left=float(np.nanpercentile(np.where(m, ratio, np.nan), 98)),
                           phase_diff_std_rad_high_snr=float(np.std(dph[m & (Ai > 0.5)])))


# ---------------------------------------------------------------- ETL 16 vs 8
def nav_train(s, sl):
    p = np.abs(readout_projection(s['navs'][0, sl])); obj = p[0] > 0.3*p[0].max()
    return p[:, obj].sum(1)/p[0, obj].sum()


def pe_psf(tr, s):
    N, L, rows = s['N'], s['L'], s['rows']
    mtf = np.zeros(N); mtf[rows] = tr[np.arange(N) % L]
    up = 8; k = np.zeros(N*up, complex); k[(N*up-N)//2:(N*up-N)//2+N] = mtf
    p = np.abs(np.fft.fftshift(np.fft.ifft(np.fft.ifftshift(k)))); p /= p.max()
    x = (np.arange(N*up)-N*up//2)/up
    above = np.nonzero(p >= 0.5)[0]
    return x, p, (above[-1]-above[0]+1)/up, float(np.sum(p[np.abs(x) > 2]**2)/np.sum(p**2)), mtf


def etl():
    e8 = load('iE'); e16 = load('iF')
    fig = plt.figure(figsize=(13, 7.4)); gs = fig.add_gridspec(2, 4)
    for j, (s, t) in enumerate([(e8, 'ETL 8 (iE) b10'), (e16, 'ETL 16 (iF) b10')]):
        panel(fig.add_subplot(gs[0, j]), s['img'][0, 3][38:100, 22:106], t, np.percentile(e8['img'][0, 3][MASK['iv_brain']], 99.5))
    for j, (s, t) in enumerate([(e8, 'ETL 8 b6000 y'), (e16, 'ETL 16 b6000 y')]):
        panel(fig.add_subplot(gs[0, 2+j]), s['img'][1, 3][38:100, 22:106], t, np.percentile(e8['img'][1, 3][MASK['iv_brain']], 99.5))
    depth, prof = depth_profiles(['iE', 'iF'])
    a = fig.add_subplot(gs[1, 0])
    a.plot(depth, prof['iE'], color=C['v1.83'], lw=2, label='ETL 8')
    a.plot(depth, prof['iF'], color='#4a3aa7', lw=2, label='ETL 16')
    a.set_xlabel('depth (mm)'); a.set_ylabel('b10 SNR'); a.legend(frameon=False); a.set_title('SNR vs depth', fontsize=9)
    a = fig.add_subplot(gs[1, 1])
    a.plot(depth, np.array(prof['iF'])/np.array(prof['iE']), color=INK2, lw=2)
    a.set_xlabel('depth (mm)'); a.set_ylabel('ETL16 / ETL8'); a.set_ylim(0.5, 1.05); a.set_title('Loss is largest near the coil (MT?)', fontsize=9)
    t8 = nav_train(e8, 3); t16 = nav_train(e16, 3)
    a = fig.add_subplot(gs[1, 2])
    a.plot(np.arange(1, 9), t8, 'o-', color=C['v1.83'], lw=2, ms=5, label='ETL 8')
    a.plot(np.arange(1, 17), t16, 's-', color='#4a3aa7', lw=1.5, ms=4, label='ETL 16')
    a.set_xlabel('echo'); a.set_ylabel('navigator echo / echo 1'); a.legend(frameon=False); a.set_title('Measured echo train (b10)', fontsize=9)
    a = fig.add_subplot(gs[1, 3])
    x8, p8, f8, s8, _ = pe_psf(t8, e8); x16, p16, f16, s16, _ = pe_psf(t16, e16)
    a.plot(x8, p8, color=C['v1.83'], lw=2, label=f'ETL 8: FWHM {f8*0.273:.2f} mm')
    a.plot(x16, p16, color='#4a3aa7', lw=2, label=f'ETL 16: FWHM {f16*0.273:.2f} mm')
    a.set_xlim(-6, 6); a.set_xlabel('phase-encode pixels'); a.set_ylabel('PSF'); a.legend(frameon=False, fontsize=8)
    a.set_title('Phase-encode PSF from the measured train', fontsize=9)
    plt.tight_layout(); plt.savefig(FIG/'etl16_vs_etl8.png', dpi=150); plt.close()
    EXTRA['etl'] = dict(train_etl8=t8.tolist(), train_etl16=t16.tolist(), psf_fwhm_mm=dict(etl8=f8*0.2734, etl16=f16*0.2734),
                        psf_energy_beyond_2px=dict(etl8=s8, etl16=s16), depth_mm=depth.tolist(),
                        depth_ratio_16_over_8=(np.array(prof['iF'])/np.array(prof['iE'])).tolist(),
                        t_vol_s=dict(etl8=17*3.0, etl16=9*3.0))


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    pbs_adc_by_slice(); brain_highb_adc()
    overview_exvivo(); overview_invivo(); md_maps(); snr_summary(); adc_summary(); ssmgot_lr(); etl()
    (DATA/'oct12_extra_results.json').write_text(json.dumps(EXTRA, indent=1, default=float))
    print(json.dumps({k: v for k, v in EXTRA.items() if k in ('brain_highb_adc', 'md_map_medians', 'etl')}, indent=1, default=float)[:3000])


if __name__ == '__main__':
    main()

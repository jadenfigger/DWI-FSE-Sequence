"""Figures for oct12_navigators.py -> docs/figures/physical_scanner_2026-10-12/{nav_*,ghost_*}.png

Colour: v1.83 = blue, v1.912 = orange (reference categorical slots 1-2); direction = marker/linestyle; grey = not measurable.
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from scipy import ndimage
from oct12_nav_common import FIG, direction_label, object_mask, sigma_img_from_k, recon_shot_variant, centre_slice, slice_offset
from oct12_nav_layout import warp_rows

BLUE, ORANGE, GREY, INK, MUTE = '#2a78d6', '#eb6834', '#9a9a95', '#222222', '#666666'
VCOL = {'v1.83': BLUE, 'v1.912': ORANGE}
plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.edgecolor': '#888888',
                     'axes.titlesize': 10, 'figure.facecolor': 'white', 'axes.facecolor': 'white', 'axes.grid': True,
                     'grid.color': '#e6e6e3', 'grid.linewidth': 0.6, 'legend.frameon': False})


def save(fig, name):
    p = FIG/name
    fig.savefig(p, dpi=110, bbox_inches='tight')
    plt.close(fig)
    return str(p)


# ------------------------------------------------------------------------------------------ N layout
def fig_n_layout(lay):
    O = lay['_objects']; Nraw, R, M, Nf, Nscr = O['Nraw'], O['R'], O['M'], O['Nf'], O['N_scr']
    fig = plt.figure(figsize=(17, 10.5))
    gs = fig.add_gridspec(2, 3, hspace=0.38, wspace=0.28)
    flat = Nraw['raw'][:, 0].reshape(-1, 128)
    pk = np.abs(flat).max(1)
    ax = fig.add_subplot(gs[0, 0])
    ax.semilogy(np.arange(len(pk)), np.maximum(pk, 0.3), color=INK, lw=0.7)
    for j in range(5):
        ax.axvline(119*j, color='#1b9e77', lw=1.4, label='recovered volume start (119 x j)' if j == 0 else None)
    for j in range(1, 4):
        ax.axvline(153*j, color='#d62728', lw=1.2, ls='--', label='start assumed by split_mode2 (153 x j)' if j == 1 else None)
    ax.axvspan(476, 612, color='#dddddd', alpha=0.7, lw=0)
    ax.text(480, 3e3, 'file is all zero\nfrom view 476', fontsize=8, color=MUTE)
    ax.set_xlabel('view slot in the MRD (4 volumes x 153 slots; b = 10, 1000, 3000, 6000)'); ax.set_ylabel('peak |k| per view (log)')
    ax.set_title('N (v1.83, nav_on=2): only 476 of 612 slots were written', loc='left'); ax.legend(loc='lower left', fontsize=7.5)
    # folded heatmaps
    ax = fig.add_subplot(gs[0, 1])
    nrm = np.log10(np.sqrt((np.abs(flat[:119])**2).sum(1))).reshape(17, 7)
    im = ax.imshow(nrm, aspect='auto', cmap='viridis'); ax.set_xticks(range(7)); ax.set_xticklabels(range(1, 8))
    ax.set_yticks(range(17)); ax.set_yticklabels(['nav'] + list(range(1, 17)), fontsize=7)
    ax.set_xlabel('echo in shot'); ax.set_ylabel('shot'); ax.grid(False)
    ax.set_title('N b10 folded 17 shots x 7 echoes: no per-shot navigator column', loc='left')
    fig.colorbar(im, ax=ax, fraction=0.04, label='log10 |k| line norm')
    ax = fig.add_subplot(gs[0, 2])
    nr = np.log10(np.sqrt((np.abs(R['raw'][0, 1])**2).sum(1))).reshape(17, 9)
    im = ax.imshow(nr, aspect='auto', cmap='viridis'); ax.set_xticks(range(9)); ax.set_xticklabels(range(1, 10))
    ax.set_yticks(range(17)); ax.set_yticklabels(['nav'] + list(range(1, 17)), fontsize=7)
    ax.set_xlabel('echo in shot'); ax.set_ylabel('shot'); ax.grid(False)
    ax.set_title('R b10 (centre slice) folded 17 x 9: echo 9 = unencoded navigator', loc='left')
    fig.colorbar(im, ax=ax, fraction=0.04, label='log10 |k| line norm')
    # ACF
    ax = fig.add_subplot(gs[1, 0])
    for key, name, c, ls in (('N_b10_stream_views_7_to_118', 'N (period 7)', BLUE, '-'), ('R_b10_centre_slice_views_9_to_152', 'R (period 9)', ORANGE, '-'),
                             ('M_b10_imaging_views_8_to_135', 'M, nav_on=1 (period 8)', GREY, '--')):
        a = lay['acf_log_norm'][key]; lags = sorted(a)
        ax.plot(lags, [a[l] for l in lags], marker='o', color=c, ls=ls, label=name, ms=4)
    ax.set_xlabel('lag (views)'); ax.set_ylabel('autocorrelation of log10 |k| line norm'); ax.legend(fontsize=8)
    ax.set_title('Shot length from the data: N repeats every 7 views', loc='left')
    # naive recon
    ax = fig.add_subplot(gs[1, 1])
    ax.imshow(Nscr['img'][0, 0], cmap='gray', vmax=np.percentile(Nscr['img'][0, 0], 99.5)); ax.axis('off')
    c = lay['N_split_mode2_vs_M'][0]
    ax.set_title(f"N b10 reconstructed as split_mode2 assumes (153 views): corr with M {c['corr']:.2f}", loc='left')
    ax = fig.add_subplot(gs[1, 2]); ax.axis('off'); ax.grid(False)
    f = lay['N_vs_M_final']['per_volume'][0]
    txt = ("Recovered layout of N (per volume, 119 views):\n"
           "  views 0-6      unencoded navigator train, 7 echoes\n"
           "  views 7-118    16 imaging shots x 7 echoes, PE rows\n"
           "                 = pe_rows(112, 7, 1): central 112 of 128 lines\n"
           "  missing        8th imaging echo + per-shot navigator echo\n\n"
           "PPL (1.83) line 1412: crusher_etl = views_per_seg + (nav_on==2)\n"
           "PPL true = -1  ->  8 + (-1) = 7 echoes per shot.\n"
           "v1.912 uses an explicit v1912_echoes += 1  ->  9 echoes (R ok).\n\n"
           "Phase-encode step (both nav_on=2 scans N and R):\n"
           "  console gp_init_var -1125 (for NO_VIEWS 153), PPL divides\n"
           "  by the reduced no_views 136  ->  step x 1.125\n"
           f"  PE FOV 31.1 mm (not 35); R/Q row scale {np.mean([x['alpha_R_to_Q'] for x in lay['R_vs_Q_scale_fit']]):.3f}\n"
           f"  (theory 0.889), N/M {np.mean([x['alpha_free'] for x in lay['N_vs_M_scale_fit']]):.3f} (theory 1.016).\n\n"
           f"N-fixed vs M, b10: corr {f['corr_all']:.3f}, object NRMSE {f['nrmse_object']:.3f}")
    ax.text(-0.15, 1.0, txt, va='top', ha='left', fontsize=8, family='monospace', color=INK)
    return save(fig, 'nav_N_layout_diagnosis.png')


def fig_n_vs_m(lay):
    O = lay['_objects']; Nf, M = O['Nf'], O['M']; alpha = O['alpha_th']
    fig, axs = plt.subplots(3, 4, figsize=(15, 11.5))
    per = lay['N_vs_M_final']['per_volume']
    for j in range(4):
        n, m = Nf['img'][j, 0], M['img'][j, 0]
        vmax = np.percentile(m, 99.7)
        axs[0, j].imshow(n, cmap='gray', vmax=vmax); axs[0, j].set_title(f"N fixed, b{Nf['b'][j]:g} {direction_label(Nf['vec'][j])}  (112 x 128)")
        axs[1, j].imshow(m, cmap='gray', vmax=vmax); axs[1, j].set_title(f"M (nav_on=1), same b  (128 x 128)")
        z, v = warp_rows(n, alpha, 0.0, 112)
        c = per[j]['scale_c']
        d = np.where(v[:, None], z-c*m, 0)
        lim = 0.25*vmax
        axs[2, j].imshow(d, cmap='coolwarm', vmin=-lim, vmax=lim)
        axs[2, j].set_title(f"N resampled to M grid - {c:.2f} M\ncorr {per[j]['corr_all']:.3f}  NRMSE(object) {per[j]['nrmse_object']:.3f}  (noise-only {per[j]['nrmse_object_noise_only_expected']:.3f})", fontsize=8.5)
        for r in range(3):
            axs[r, j].axis('off')
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.suptitle('Scan N after re-ordering (7 echoes/shot, 112 lines) vs scan M: the same four volumes', x=0.02, y=0.99, ha='left', fontsize=11)
    return save(fig, 'nav_N_fixed_vs_M.png')


# ------------------------------------------------------------------------------------------ ghosts
def primary_ghost(r):
    """ex vivo: 'own' zone at b>=3000 (PBS gone), outside-tube zone at b<=1000; in vivo: outside the b10 head."""
    if r['sample'].startswith('ex') and r['b'] >= 3000:
        return r['ghost_excess_own'], r['ghost_excess_own_se']
    return r['ghost_excess'], r['ghost_excess_se']


def fig_ghost_bars(df):
    """Two figures (ex vivo, in vivo): one small panel per (b, direction), one bar per scan (blue v1.83, orange v1.912)."""
    names = {}
    for sample, scans, fname, title in (('ex', ['M', 'N', 'Q', 'Q1', 'O', 'R', 'C'], 'ghost_metric_bars_exvivo.png',
                                          'Ex vivo (fixed brain in PBS), centre slice, plain recon: phase-encode ghost excess (% of object mean)'),
                                         ('in', ['iA', 'iD', 'iE', 'iF', 'iB', 'iC'], 'ghost_metric_bars_invivo.png',
                                          'In vivo (surface coil), centre slice, plain recon: phase-encode ghost excess (% of object mean)')):
        d = df[(df.centre_slice == 1) & (df.recon == 'plain') & (df.scan.isin(scans)) & (df.b > 10) & (df['sample'].str.startswith(sample))]
        bs = sorted(d.b.unique()); dirs = ['+x', '+y', '+z']
        fig, axs = plt.subplots(len(bs), 3, figsize=(15, 3.1*len(bs)), squeeze=False)
        for i, b in enumerate(bs):
            for j, dr in enumerate(dirs):
                ax = axs[i, j]; ax.grid(axis='x', visible=False)
                for k, sc in enumerate(scans):
                    rr = d[(d.scan == sc) & (d.b == b) & (d.direction == dr)]
                    if rr.empty:
                        continue
                    r = rr.iloc[0]; col = VCOL[r['version']]
                    val, se = primary_ghost(r)
                    if not r['reliable']:
                        ax.bar(k, 0.4, 0.7, color='none', edgecolor=GREY, hatch='///', lw=0.8)
                        ax.text(k, 0.5, 'n.d.', ha='center', va='bottom', fontsize=7, color=MUTE)
                        continue
                    nav2 = sc in ('N', 'R')
                    ax.bar(k, 100*val, 0.7, color=col, alpha=0.55 if nav2 else 1.0, hatch='\\' if nav2 else None, edgecolor=col if nav2 else 'white', lw=0.6)
                    ax.errorbar(k, 100*val, yerr=100*max(se, 0), color='#333333', lw=0.8, capsize=0)
                    ax.text(k, 100*val+100*max(se, 0)+0.1, f'{100*val:.1f}', ha='center', va='bottom', fontsize=7.5, color=INK)
                ax.axhline(0, color='#888888', lw=0.8)
                ax.set_xticks(range(len(scans))); ax.set_xticklabels(scans, fontsize=8.5)
                ax.set_title(f'b{b:g} {dr}', loc='left', fontsize=9.5)
                if j == 0:
                    ax.set_ylabel('%')
                ymax = ax.get_ylim()[1]; ax.set_ylim(min(ax.get_ylim()[0], -0.3), max(ymax, 1.5))
        handles = [Patch(facecolor=BLUE, label='v1.83 (nav_on=1; N = nav_on=2 requested, no per-shot echo acquired)'),
                   Patch(facecolor=ORANGE, label='v1.912 (O, C, iB, iC nav_on=1; R nav_on=2, hatched = plain recon)'),
                   Patch(facecolor='none', edgecolor=GREY, hatch='///', label='n.d. = object not detectable (SNR < 4 or < 150 pixels)')]
        fig.legend(handles=handles, loc='upper right', fontsize=8.5, ncol=1, bbox_to_anchor=(0.99, 1.0))
        fig.suptitle(title, x=0.01, y=1.0, ha='left', fontsize=11)
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        names[sample] = save(fig, fname)
    return names


def fig_ghost_examples(scans):
    def pick(s, b, d):
        for i in range(s['E']):
            if abs(s['b'][i]-b) < 1 and direction_label(s['vec'][i]) == d:
                return i
    spec = [('M', 3000, '+z'), ('N', 3000, '+z'), ('Q', 3000, '+z'), ('O', 3000, '+z'), ('R', 3000, '+z'),
            ('Q', 3000, '+y'), ('R', 3000, '+y'), ('M', 6000, '+z'), ('O', 6000, '+z'),
            ('iA', 3000, '+y'), ('iB', 3000, '+y'), ('iA', 6000, '+y')]
    fig, axs = plt.subplots(2, 6, figsize=(19, 7.2))
    for ax, (k, b, d) in zip(axs.ravel(), spec):
        s = scans[k]; i = pick(s, b, d); sl = centre_slice(s); im = s['img'][i, sl]
        ax.imshow(im, cmap='gray', vmax=(0.2 if not k.startswith('i') else 0.5)*np.percentile(im, 99.7)); ax.axis('off')
        ax.set_title(f"{k} {s['version']} b{b} {d}", fontsize=9, color=VCOL['v1.83' if s['version'] == 'v1.83' else 'v1.912'])
    fig.suptitle('High-b centre slices, window set to the lowest 20% (ex vivo) / 50% (in vivo) of the signal: vertical bands above/below the object are phase-encode ghosts', x=0.01, ha='left', fontsize=10)
    fig.tight_layout()
    return save(fig, 'ghost_examples_highb.png')


# ------------------------------------------------------------------------------------------ per-shot
def fig_per_shot(R, shot_rows, shot_stats):
    fig = plt.figure(figsize=(17, 11.5))
    gs = fig.add_gridspec(3, 4, hspace=0.42, wspace=0.28)
    # (a,b) per-shot constant / linear terms, centre slice and +2.8 slice
    for col, (sl, title) in enumerate(((1, 'centre slice'), (2, '+2.8 mm slice'))):
        axc = fig.add_subplot(gs[0, col*2]); axl = fig.add_subplot(gs[0, col*2+1])
        for e, lab, c in ((0, 'b10', '#444444'), (1, 'b1000 x', BLUE), (2, 'b1000 y', '#1baf7a'), (4, 'b3000 x', ORANGE)):
            qa = R['shot_qa'][e*R['S']+sl]
            est = qa['Estimates']
            cc = (np.degrees([x['constant_rad'] for x in est])+180) % 360-180
            ll = np.degrees([x['linear_rad_per_voxel'] for x in est])*128
            ap = np.array([x['applied'] for x in est])
            if ap.sum() == 0:
                continue
            axc.plot(np.arange(16)[ap], cc[ap], 'o-', color=c, ms=3.5, lw=1, label=lab)
            axl.plot(np.arange(16)[ap], ll[ap], 'o-', color=c, ms=3.5, lw=1, label=lab)
        axc.set_title(f'constant phase vs ref. shot, {title}', loc='left', fontsize=9); axc.set_xlabel('shot'); axc.set_ylabel('deg')
        axl.set_title(f'linear phase over readout FOV, {title}', loc='left', fontsize=9); axl.set_xlabel('shot'); axl.set_ylabel('deg per 128 samples')
        if col == 0:
            axc.legend(fontsize=8, ncol=2)
        if sl == 2:
            axl.text(0.02, 0.04, 'b3000: navigator SNR 1-2 < 3, no shot corrected', transform=axl.transAxes, fontsize=8, color=MUTE)
    # (c) ghost by variant
    names = ['plain', 'const+lin (shipped)', 'const', 'const+lin, SNR>=8']
    cols = ['#888888', ORANGE, BLUE, '#1baf7a']
    for k, (sl, title) in enumerate(((2, 'centre slice'), (3, '+2.8 mm slice'), (1, '-2.8 mm slice'))):
        ax = fig.add_subplot(gs[1, k])
        rr = [r for r in shot_rows if r['slice'] == sl]
        x = np.arange(len(rr)); w = 0.2
        for i, (nm, c) in enumerate(zip(names, cols)):
            ax.bar(x+(i-1.5)*w, [r[nm] for r in rr], w*0.95, color=c, label=nm)
        ax.set_xticks(x); ax.set_xticklabels([f"b{r['b']:g}\n{r['direction']}" for r in rr], fontsize=7.5)
        ax.set_title(f'R ghost excess by variant, {title}', loc='left', fontsize=9); ax.set_ylabel('ghost excess (primary metric)')
        if k == 0:
            ax.legend(fontsize=7.5, loc='upper right')
    # (d) navigator SNR per slice/volume
    ax = fig.add_subplot(gs[1, 3])
    for sl, c, lab in ((0, '#9085e9', '-2.8 mm'), (1, '#444444', 'centre'), (2, ORANGE, '+2.8 mm')):
        v = [R['shot_qa'][e*R['S']+sl]['Estimates'] for e in range(R['E'])]
        ax.plot(range(1, R['E']+1), [np.median([x['navigator_snr'] for x in est]) for est in v], 'o-', color=c, label=lab)
    ax.axhline(3, color='#d62728', ls='--', lw=1); ax.text(7.1, 3.3, 'gate SNR 3', color='#d62728', fontsize=8, ha='right')
    ax.set_yscale('log'); ax.set_xticks(range(1, 8)); ax.set_xticklabels(['b10', 'b1000x', 'b1000y', 'b1000z', 'b3000x', 'b3000y', 'b3000z'], fontsize=7.5)
    ax.set_title('median per-shot navigator SNR', loc='left'); ax.legend(fontsize=8)
    # (e) images of the +2.8 mm b1000 +y case: plain / shipped / const
    sl, e = 2, 2
    ref_ims = [R['img'][e, sl], recon_shot_variant(R, e, sl, 'constant+linear')[0], recon_shot_variant(R, e, sl, 'constant')[0]]
    ttl = ['plain', 'shipped: const+lin', 'const only']
    vmax = 0.35*np.percentile(ref_ims[0], 99.5)
    for k in range(3):
        ax = fig.add_subplot(gs[2, k]); ax.imshow(ref_ims[k], cmap='gray', vmax=vmax); ax.axis('off')
        ax.set_title(f'R +2.8 mm, b1000 +y: {ttl[k]}', loc='left', fontsize=9)
    ax = fig.add_subplot(gs[2, 3])
    d = ref_ims[1]-ref_ims[0]
    ax.imshow(d, cmap='coolwarm', vmin=-vmax, vmax=vmax); ax.axis('off'); ax.set_title('shipped - plain', loc='left')
    return save(fig, 'nav_per_shot_R.png')


# ------------------------------------------------------------------------------------------ per-echo ADC
def fig_adc(J):
    A = J['adc']
    fig, axs = plt.subplots(2, 3, figsize=(17, 9.5))
    e8 = np.arange(1, 9)
    def line(ax, v, key, errkey, label, c, ls='-', marker='o'):
        y = np.array(v[key], float)*1e3; n = len(y)
        e = np.array(v[errkey], float)*1e3 if errkey else None
        ax.errorbar(np.arange(1, n+1), y, yerr=e, color=c, ls=ls, marker=marker, ms=3.5, lw=1.2, capsize=0, label=label)
    # a, b: ex vivo total ADC at b1000 x and b3000 x/z
    for ax, (vk_map, title) in zip(axs[0, :2], (({'Q': 'v2_b1000+x', 'M': 'v2_b1000+x', 'O': 'v2_b1000+x', 'R': 'v2_b1000+x', 'C': 'v2_b1000+x'}, 'ex vivo, whole navigator: b10 -> b1000 +x'),
                                                ({'Q': 'v5_b3000+x', 'M': 'v3_b3000+z', 'O': 'v3_b3000+z', 'R': 'v5_b3000+x', 'C': 'v3_b3000+x'}, 'ex vivo, whole navigator: b10 -> b3000 (x; z for M, O)'))):
        for sc, c, ls in (('Q', BLUE, '-'), ('M', BLUE, '--'), ('O', ORANGE, '--'), ('R', ORANGE, '-'), ('C', ORANGE, ':')):
            line(ax, A[sc]['volumes'][vk_map[sc]], 'adc_total', 'adc_total_err', f"{sc} {'v1.83' if sc in 'QM' else 'v1.912'}", c, ls)
        ax.set_title(title, loc='left'); ax.set_xlabel('echo number'); ax.set_ylabel('apparent ADC, 1e-3 mm$^2$/s'); ax.legend(fontsize=8)
    # c: pure-brain pair b3000 -> b6000 and component fits at b1000x
    ax = axs[0, 2]
    pair = J['highb_pair']
    for sc, c, ls in (('M', BLUE, '--'), ('O', ORANGE, '--')):
        p = pair[sc]
        ax.errorbar(np.arange(1, len(p['adc'])+1), np.array(p['adc'])*1e3, yerr=np.array(p['err'])*1e3, color=c, ls=ls, marker='o', ms=3.5, label=f"{sc} brain only, b3000 -> b6000 +z")
    ax.set_title('pure brain (PBS gone): b3000 -> b6000, +z', loc='left'); ax.set_xlabel('echo number'); ax.set_ylabel('apparent ADC, 1e-3 mm$^2$/s'); ax.legend(fontsize=8)
    ax.set_ylim(0, 0.35)
    # d: components b1000 x : PBS-only columns, brain 2-comp
    ax = axs[1, 0]
    for sc, c, ls in (('Q', BLUE, '-'), ('M', BLUE, '--'), ('O', ORANGE, '--'), ('R', ORANGE, '-')):
        v = A[sc]['volumes']['v2_b1000+x']
        line(ax, v, 'adc_pbs_cols', 'adc_pbs_cols_err', f'{sc} PBS-only columns', c, ls, 's')
    ax.set_title('PBS only (columns outside the brain), b10 -> b1000 +x', loc='left'); ax.set_xlabel('echo number'); ax.set_ylabel('1e-3 mm$^2$/s'); ax.legend(fontsize=8)
    ax = axs[1, 1]
    for sc, c, ls in (('Q', BLUE, '-'), ('M', BLUE, '--'), ('O', ORANGE, '--'), ('R', ORANGE, '-')):
        v = A[sc]['volumes']['v2_b1000+x']
        line(ax, v, 'adc_brain_2comp', 'adc_brain_2comp_err', f'{sc} brain (2-compartment fit)', c, ls, '^')
    ax.set_title('brain, from the PBS+brain template fit, b10 -> b1000 +x', loc='left'); ax.set_xlabel('echo number'); ax.set_ylabel('1e-3 mm$^2$/s'); ax.legend(fontsize=8)
    # e: in vivo
    ax = axs[1, 2]
    for sc, c, lab in (('iA', BLUE, 'iA v1.83'), ('iB', ORANGE, 'iB v1.912')):
        for (vk, ls, mk) in (('v2_b1000+x', '-', 'o'), ('v5_b3000+x', '--', 's'), ('v8_b6000+x', ':', '^')):
            if vk in A[sc]['volumes']:
                line(ax, A[sc]['volumes'][vk], 'adc_total', 'adc_total_err', f"{lab} b{vk.split('_b')[1].split('+')[0]} x", c, ls, mk)
    ax.set_title('in vivo, whole navigator: b10 -> b1000 / 3000 / 6000, +x', loc='left'); ax.set_xlabel('echo number'); ax.set_ylabel('1e-3 mm$^2$/s'); ax.legend(fontsize=7.5, ncol=2)
    for ax in axs.ravel():
        ax.set_xticks(range(1, 9))
    fig.tight_layout()
    return save(fig, 'nav_per_echo_adc.png')


# ------------------------------------------------------------------------------------------ trains
def fig_trains(J, scan_a, scan_b, name, vol_sel_a, vol_sel_b, title):
    fig, axs = plt.subplots(2, 4, figsize=(18, 8))
    cmap = {10: '#444444', 1000: '#2a78d6', 3000: '#eb6834', 6000: '#a4262c'}
    for ci, (sc, vsel) in enumerate(((scan_a, vol_sel_a), (scan_b, vol_sel_b))):
        T = J['trains'][sc]; info = J['per_scan'][sc]; vols = info['volumes']
        csl = info['centre_slice']-1; slices = info['slices']
        for part, (ax_m, ax_p) in enumerate(((axs[0, ci*2], axs[1, ci*2]), (axs[0, ci*2+1], axs[1, ci*2+1]))):
            if part == 0:                          # centre slice, all volumes
                sel = [(e, csl) for e in range(len(vols)) if e in vsel]
                ttl = f"{sc} {info['version']}: centre slice"
            else:                                   # b10 for each slice
                sel = [(0, sl) for sl in range(len(slices))]
                ttl = f"{sc} {info['version']}: b10, every slice"
            cm = plt.cm.viridis(np.linspace(0, 0.9, max(len(sel), 2)))
            for k, (e, sl) in enumerate(sel):
                amp = np.array(T['amp'][e][sl]); ph = np.array(T['ip_phase'][e][sl]); n = np.arange(1, len(amp)+1)
                if part == 0:
                    b = vols[e]['b']; c = cmap.get(int(b), '#777777'); lab = f"b{b:g} {vols[e]['direction']}"
                    ls = {'+x': '-', '+y': '--', '+z': ':'}.get(vols[e]['direction'], '-')
                else:
                    c = cm[k]; lab = f"{slices[sl]:+.1f} mm"; ls = '-'
                snr = np.array(T['snr'][e][sl])
                ax_m.semilogy(n, np.where(snr > 2, amp, np.nan), color=c, ls=ls, marker='o', ms=3, lw=1.2, label=lab)
                ok = snr > 5
                ax_p.plot(n[ok], ph[ok], color=c, ls=ls, marker='o', ms=3, lw=1.2)
            ax_m.set_title(ttl, loc='left'); ax_m.set_ylabel('navigator amplitude (noise-subtracted)'); ax_m.legend(fontsize=6.5, ncol=2)
            ax_p.set_xlabel('echo'); ax_p.set_ylabel('phase vs echo 1 (deg), echoes with SNR > 5')
            ax_p.set_ylim(-190, 190)
    fig.suptitle(title, x=0.01, ha='left', fontsize=11)
    fig.tight_layout()
    return save(fig, name)

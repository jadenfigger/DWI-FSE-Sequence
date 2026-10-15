"""Rebuild Oct 12 image and k-space comparison tiles in the prior-report style.

The preview mode writes ex-vivo three-sequence image and k-space figures first.
FSE k-space comes from the actual complex, PE-reordered grid; EPI k-space is read
directly from the vendor-processed complex _o.MRD grid (not from image magnitude).
"""
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'docs' / 'data'
FIG = ROOT / 'docs' / 'figures' / 'physical_scanner_2026-10-12'
sys.path.insert(0, str(DATA))

from oct12_load import load, folder, direction_label, get_mrd_3d4  # noqa: E402
from oct12_rois import NOISE_COLS_EX, NOISE_COLS_IV  # noqa: E402

FOV_MM = 35.0
EX_CROP = (-10.0, 10.0, -2.5, 17.5)
IV_CROP = (-10.0, 10.0, -10.0, 10.0)
KSPACE_DB_FLOOR = -50.0


def central_slice(scan):
    offsets = np.asarray(scan.get('offsets_mm', []), float)
    nsl = int(scan.get('S', len(offsets)))
    return int(np.argmin(np.abs(offsets))) if len(offsets) == nsl else nsl // 2


def vol_index(scan, b, direction):
    choices = [i for i, value in enumerate(scan['b'])
               if abs(float(value) - b) < 2.0 and direction_label(scan['vec'][i]) == direction]
    if not choices:
        raise ValueError(f"{scan['key']}: missing b={b}, direction={direction}")
    return choices[0]


def scan_image(scan, b, direction):
    e = vol_index(scan, b, direction)
    s = central_slice(scan)
    if 'mag' in scan:
        im = np.asarray(scan['mag'][e, s], float)
    else:
        im = np.asarray(scan['img'][e, s], float)
    return im, float(scan['b'][e]), direction_label(scan['vec'][e]), s + 1


def background_sigma(im, key, sample):
    """Use the Oct 12 ROI/SNR analysis' established background RMS estimator."""
    if key in ('epi0', 'epiA'):
        cols = np.r_[152:166] if sample == 'Ex vivo' else np.r_[2:16, 152:166]
    else:
        cols = NOISE_COLS_EX if sample == 'Ex vivo' else NOISE_COLS_IV
    return float(np.sqrt(np.mean(im[4:124, cols] ** 2) / 2.0))


def crop_values(im, crop):
    ny, nx = im.shape
    y = (np.arange(ny) + .5) * (FOV_MM / ny) - FOV_MM / 2
    x = (np.arange(nx) + .5) * (FOV_MM / nx) - FOV_MM / 2
    xmask = (x >= crop[0]) & (x <= crop[1])
    ymask = (y >= crop[2]) & (y <= crop[3])
    return im[np.ix_(ymask, xmask)]


def load_scans(keys):
    scans = {}
    for key in keys:
        if key.startswith('epi'):
            p = next(folder(key).glob('*_o.MRD'))
            raw, dims, _ = get_mrd_3d4(p)
            complex_k = raw[:, 0, :, 0]
            # Plain inverse FFT, used only for the image panels and noise ROI.
            cimg = np.fft.fftshift(
                np.fft.ifft2(np.fft.ifftshift(complex_k, axes=(-2, -1))), axes=(-2, -1)
            )[..., ::-1]
            from oct12_load import load_epi
            e = load_epi(key)
            scans[key] = dict(key=key, b=e['b'], vec=e['vec'], offsets_mm=e['offsets_mm'],
                              S=len(e['offsets_mm']), mag=np.abs(cimg), kspace=complex_k, read_px=dims[5])
        else:
            scans[key] = load(key, shot_mode='off')
    return scans


def make_image_preview(scans, path, sample, crop, grid):
    # grid: source rows and b/direction columns. Each b column has a shared I/sigma window.
    entries = [[(src, b, d) for b, d in col] for src, col in zip(grid['sources'], grid['by_source'])]
    panels = []
    for row, src in enumerate(grid['sources']):
        panels.append([])
        for col, (b, d) in enumerate(grid['by_source'][row]):
            im, actual_b, actual_d, sl = scan_image(scans[src], b, d)
            sigma = background_sigma(im, src, sample)
            panels[-1].append(dict(im=im / sigma, sigma=sigma, b=actual_b, d=actual_d, sl=sl, src=src))
    vmax_by_col = []
    for c in range(len(grid['headers'])):
        vmax_by_col.append(max(float(np.percentile(crop_values(p[c]['im'], crop), 99.5)) for p in panels))
    vmax_by_col = [max(v, 1.0) for v in vmax_by_col]

    fig = plt.figure(figsize=(10.0, 8.2), facecolor='white')
    gs = fig.add_gridspec(len(panels), len(grid['headers']), left=.105, right=.985,
                          bottom=.08, top=.91, wspace=.035, hspace=.18)
    for c, header in enumerate(grid['headers']):
        fig.text(.105 + (c + .5) * (.88 / len(grid['headers'])), .944, header,
                 ha='center', va='center', fontsize=13, color='black')
    for r, src in enumerate(grid['sources']):
        fig.text(.087, .08 + (len(panels) - r - .5) * (.83 / len(panels)),
                 grid['row_labels'][r], ha='right', va='center', fontsize=10.5, color='black')
        for c, p in enumerate(panels[r]):
            ax = fig.add_subplot(gs[r, c], facecolor='black')
            ax.set_anchor('W')
            ax.imshow(p['im'], cmap='gray', origin='lower', extent=(-17.5, 17.5, -17.5, 17.5),
                      vmin=0, vmax=vmax_by_col[c], interpolation='nearest', aspect='equal')
            ax.add_patch(Rectangle((crop[1], crop[2]), 4.0, crop[3]-crop[2], color='black', zorder=3))
            ax.set_xlim(crop[0], crop[1]+4.0); ax.set_ylim(crop[2], crop[3]); ax.set_axis_off()
            ax.set_title(panel_name(p['src'], 0, p['b'], p['d']), color='white', fontsize=8.5, pad=3)
            cax = ax.inset_axes([.91, .10, .025, .78])
            cb = fig.colorbar(plt.cm.ScalarMappable(norm=Normalize(0, vmax_by_col[c]), cmap='gray'), cax=cax)
            cb.ax.tick_params(colors='white', labelsize=5.5, length=2, pad=1)
            cb.outline.set_edgecolor('white')
            cb.set_label('I/σ', color='white', fontsize=7, labelpad=2)
    fig.text(.5, .025, 'Linear I/σ · shared window per b', ha='center', va='center', fontsize=7.1, color='#333333')
    fig.savefig(path, dpi=220, facecolor='white', bbox_inches='tight', pad_inches=.08)
    plt.close(fig)


def make_kspace_preview(scans, path, sample, grid):
    panels = []
    for r, src in enumerate(grid['sources']):
        panels.append([])
        for b, d in grid['by_source'][r]:
            e = vol_index(scans[src], b, d)
            sl = central_slice(scans[src])
            k = np.asarray(scans[src]['kspace'][e, sl])
            peak = float(np.max(np.abs(k)))
            db = 20 * np.log10(np.maximum(np.abs(k) / max(peak, 1e-30), 10 ** (KSPACE_DB_FLOOR / 20)))
            panels[-1].append(dict(db=db, b=float(scans[src]['b'][e]),
                                   d=direction_label(scans[src]['vec'][e]), sl=sl + 1, src=src))

    fig = plt.figure(figsize=(10.0, 8.2), facecolor='white')
    gs = fig.add_gridspec(len(panels), len(grid['headers']), left=.105, right=.985,
                          bottom=.08, top=.91, wspace=.035, hspace=.18)
    for c, header in enumerate(grid['headers']):
        fig.text(.105 + (c + .5) * (.88 / len(grid['headers'])), .944, header,
                 ha='center', va='center', fontsize=13, color='black')
    for r, src in enumerate(grid['sources']):
        fig.text(.087, .08 + (len(panels) - r - .5) * (.83 / len(panels)),
                 grid['row_labels'][r], ha='right', va='center', fontsize=10.5, color='black')
        for c, p in enumerate(panels[r]):
            ax = fig.add_subplot(gs[r, c], facecolor='black')
            ax.set_anchor('W')
            ny, nx = p['db'].shape
            ax.imshow(p['db'], cmap='gray', origin='lower', extent=(-.5, nx-.5, -.5, ny-.5),
                      vmin=KSPACE_DB_FLOOR, vmax=0, interpolation='nearest', aspect='equal')
            ax.set_axis_off()
            ax.set_title(panel_name(p['src'], 0, p['b'], p['d']), color='white', fontsize=8.5, pad=3)
            ax.add_patch(Rectangle((nx-.5, -.5), 20.0, ny, color='black', zorder=3))
            ax.set_xlim(-.5, nx+19.5); ax.set_ylim(-.5, ny-.5)
            cax = ax.inset_axes([.84, .10, .035, .78])
            cb = fig.colorbar(plt.cm.ScalarMappable(norm=Normalize(KSPACE_DB_FLOOR, 0), cmap='gray'), cax=cax)
            cb.ax.tick_params(colors='white', labelsize=5.5, length=2, pad=1)
            cb.outline.set_edgecolor('white')
        cb.set_label('dB', color='white', fontsize=6.4, labelpad=2)
    fig.savefig(path, dpi=220, facecolor='white', bbox_inches='tight', pad_inches=.08)
    plt.close(fig)


def panel_name(scan, index, b, direction):
    tag = {'M': 'M · v1.83', 'O': 'O · v1.912 ss-MGOT', 'iA': 'iA · v1.83',
           'iB': 'iB · v1.912 ss-MGOT', 'epi0': 'EPI · test0', 'epiA': 'EPI · invivoA'}[scan]
    return tag


def one_row_three_sequence(scans, sample, keys, acquisition, crop, suffix, is_kspace=False):
    values = []
    for key, (b, direction) in zip(keys, acquisition):
        scan = scans[key]
        e = vol_index(scan, b, direction)
        sl = central_slice(scan)
        if is_kspace:
            k = np.asarray(scan['kspace'][e, sl])
            peak = float(np.max(np.abs(k)))
            data = 20 * np.log10(np.maximum(np.abs(k) / max(peak, 1e-30), 10 ** (KSPACE_DB_FLOOR / 20)))
            values.append(dict(data=data, label=panel_name(key, e, float(scan['b'][e]), direction_label(scan['vec'][e])),
                               sl=sl + 1))
        else:
            image, actual_b, actual_d, sl_label = scan_image(scan, b, direction)
            sigma = background_sigma(image, key, sample)
            values.append(dict(data=image / sigma, label=panel_name(key, e, actual_b, actual_d),
                               sl=sl_label, sigma=sigma))
    if is_kspace:
        vmin, vmax = KSPACE_DB_FLOOR, 0.0
    else:
        vmin = 0.0
        vmax = max(float(np.percentile(crop_values(p['data'], crop), 99.5)) for p in values)
        vmax = max(vmax, 1.0)

    fig, axes = plt.subplots(1, 3, figsize=(10.0, 4.65), facecolor='white')
    if is_kspace:
        fig.subplots_adjust(left=.035, right=.99, top=.95, bottom=.05, wspace=.10)
    else:
        fig.subplots_adjust(left=.035, right=.99, top=.91, bottom=.06, wspace=.10)
    cmap = 'gray'
    for ax, key, item in zip(axes, keys, values):
        ax.set_facecolor('black')
        ax.set_anchor('C')
        if is_kspace:
            ny, nx = item['data'].shape
            ax.imshow(item['data'], cmap=cmap, origin='lower', extent=(-.5, nx-.5, -.5, ny-.5),
                      vmin=vmin, vmax=vmax, interpolation='nearest', aspect='equal')
            ax.add_patch(Rectangle((nx-.5, -.5), 20.0, ny, color='black', zorder=3))
            ax.set_xlim(-.5, nx+19.5); ax.set_ylim(-.5, ny-.5)
        else:
            ax.imshow(item['data'], cmap=cmap, origin='lower', extent=(-17.5, 17.5, -17.5, 17.5),
                      vmin=vmin, vmax=vmax, interpolation='nearest', aspect='equal')
            ax.add_patch(Rectangle((crop[1], crop[2]), 4.0, crop[3]-crop[2], color='black', zorder=3))
            ax.set_xlim(crop[0], crop[1]+4.0); ax.set_ylim(crop[2], crop[3])
        ax.set_axis_off()
        ax.set_title(item['label'], color='black', fontsize=9.3, pad=7)
        sm = plt.cm.ScalarMappable(norm=Normalize(vmin, vmax), cmap=cmap)
        cax = ax.inset_axes([.91, .10, .025, .78]) if is_kspace else ax.inset_axes([.84, .10, .035, .78])
        cb = fig.colorbar(sm, cax=cax)
        cb.ax.tick_params(colors='white', labelsize=5.5, length=2, pad=1)
        cb.outline.set_edgecolor('#333333')
        cb.set_label('dB' if is_kspace else 'I/σ', color='white', fontsize=6.4, labelpad=2)
    if is_kspace:
        title = f'{sample} · b={acquisition[0][0]:g} · complex k-space magnitude'
        note = ''
    else:
        btext = 'baseline: FSE b=10, EPI b=0' if acquisition[0][0] in (0, 10) else f'b={acquisition[0][0]:g}'
        title = f'{sample} · {btext} · linear magnitude'
        note = 'Linear I/σ · shared window per b'
    if note:
        fig.text(.5, .045, note, ha='center', va='center', fontsize=6.8, color='#333333')
    target = FIG / f'revised_{sample.lower().replace(" ", "")}_{suffix}.png'
    fig.savefig(target, dpi=220, facecolor='white', bbox_inches='tight', pad_inches=.08)
    plt.close(fig)
    return target


def epi_fse_image_2x3(scans, sample, epi_key, fse_key, crop, exvivo):
    if exvivo:
        specs = [((0, '+x'), (10, '+x')), ((1000, '+y'), (1000, '+x')), ((6000, '+z'), (6000, '+z'))]
        headers = ('Baseline · EPI b=0 / FSE b=10', 'b=1000 · EPI +y / FSE +x', 'b=6000 · +z')
    else:
        specs = [((0, '+x'), (10, '+x')), ((1000, '+z'), (1000, '+z')), ((6000, '+z'), (6000, '+z'))]
        headers = ('Baseline · EPI b=0 / FSE b=10', 'b=1000 · +z', 'b=6000 · +z')
    rows = []
    for src, row_label in ((epi_key, 'Lab EPI'), (fse_key, 'v1.83 FSE')):
        rows.append([])
        for epi_spec, fse_spec in specs:
            b, d = epi_spec if src == epi_key else fse_spec
            im, actual_b, actual_d, sl = scan_image(scans[src], b, d)
            sigma = background_sigma(im, src, 'Ex vivo' if exvivo else 'In vivo')
            rows[-1].append(dict(data=im / sigma, label=('Lab EPI' if src == epi_key else 'v1.83 FSE')))
    vmax = [max(float(np.percentile(crop_values(rows[r][c]['data'], crop), 99.5)) for r in range(2)) for c in range(3)]
    vmax = [max(v, 1.0) for v in vmax]
    fig, axes = plt.subplots(2, 3, figsize=(10.0, 6.1), facecolor='white')
    fig.subplots_adjust(left=.095, right=.99, top=.84, bottom=.14, wspace=.05, hspace=.23)
    for c, (header, lim) in enumerate(zip(headers, vmax)):
        for r in range(2):
            ax = axes[r, c]
            ax.set_facecolor('black')
            ax.imshow(rows[r][c]['data'], cmap='gray', origin='lower', extent=(-17.5,17.5,-17.5,17.5),
                      vmin=0, vmax=lim, interpolation='nearest', aspect='equal')
            ax.add_patch(Rectangle((crop[1],crop[2]),4.0,crop[3]-crop[2],color='black',zorder=3))
            ax.set_xlim(crop[0],crop[1]+4.0); ax.set_ylim(crop[2],crop[3]); ax.set_axis_off()
            ax.set_title(rows[r][c]['label'], color='black', fontsize=7.7, pad=4)
            sm=plt.cm.ScalarMappable(norm=Normalize(0,lim),cmap='gray')
            cax=ax.inset_axes([.84,.10,.035,.78])
            cb=fig.colorbar(sm,cax=cax)
            cb.ax.tick_params(colors='white',labelsize=5.3,length=2,pad=1)
            cb.outline.set_edgecolor('white')
            cb.set_label('I/σ',color='white',fontsize=5.8,labelpad=1)
        fig.text(.19 + c*.30, .882, header, ha='center', va='center', fontsize=9.5, color='black')
    fig.text(.045,.61,'EPI',rotation=90,ha='center',va='center',fontsize=10,color='black')
    fig.text(.045,.31,'FSE',rotation=90,ha='center',va='center',fontsize=10,color='black')
    caveat = 'b1000 direction differs ex vivo (EPI +y; FSE +x). Independent acquisition protocols; no quantitative intensity claim.' if exvivo else 'Independent acquisition protocols; EPI directions provisional. Shared linear I/σ window within each b column.'
    fig.text(.5,.045,caveat,ha='center',va='center',fontsize=7,color='#333333')
    path=FIG/f'revised_{sample.lower().replace(" ","")}_epi_vs_fse.png'
    fig.savefig(path,dpi=220,facecolor='white',bbox_inches='tight',pad_inches=.08)
    plt.close(fig)
    return path


def epi_fse_individual_tiles(scans, sample, epi_key, fse_key, crop, exvivo):
    """Export six black-backed image/colorbar tiles for native slide re-layout."""
    specs = ([((0, '+x'), (10, '+x')), ((1000, '+y'), (1000, '+x')), ((6000, '+z'), (6000, '+z'))]
             if exvivo else [((0, '+x'), (10, '+x')), ((1000, '+z'), (1000, '+z')), ((6000, '+z'), (6000, '+z'))])
    data = []
    for epi_spec, fse_spec in specs:
        col = []
        for key, (b, direction) in ((epi_key, epi_spec), (fse_key, fse_spec)):
            im, _, _, _ = scan_image(scans[key], b, direction)
            sigma = background_sigma(im, key, sample)
            col.append((key, im / sigma))
        lim = max(float(np.percentile(crop_values(im, crop), 99.5)) for _, im in col)
        data.append((col, max(lim, 1.0)))
    out = []
    for ci, ((col, lim), (epi_spec, fse_spec)) in enumerate(zip(data, specs)):
        for ri, (key, im) in enumerate(col):
            fig = plt.figure(figsize=(3.6, 3.0), facecolor='black')
            ax = fig.add_axes([0, 0, 1, 1], facecolor='black')
            ax.imshow(im, cmap='gray', origin='lower', extent=(-17.5,17.5,-17.5,17.5),
                      vmin=0, vmax=lim, interpolation='nearest', aspect='equal')
            ax.add_patch(Rectangle((crop[1],crop[2]),4.0,crop[3]-crop[2],color='black',zorder=3))
            ax.set_xlim(crop[0],crop[1]+4.0); ax.set_ylim(crop[2],crop[3]); ax.set_axis_off()
            cax=ax.inset_axes([.86,.10,.035,.78])
            cb=fig.colorbar(plt.cm.ScalarMappable(norm=Normalize(0,lim),cmap='gray'),cax=cax)
            cb.ax.tick_params(colors='white',labelsize=7,length=2,pad=1)
            cb.outline.set_edgecolor('white')
            cb.set_label('I/σ',color='white',fontsize=8,labelpad=2)
            role = 'epi' if key == epi_key else 'fse'
            shell = ('baseline' if ci == 0 else f'b{int(specs[ci][0][0])}')
            path = FIG / f'revised_{sample.lower().replace(" ","")}_epi_fse_{role}_{shell}.png'
            fig.savefig(path,dpi=220,facecolor='black',pad_inches=0)
            plt.close(fig)
            out.append(path)
    return out


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    scans = load_scans(('M', 'O', 'iA', 'iB', 'epi0', 'epiA'))
    ex = dict(sources=('M', 'O', 'epi0'),
              row_labels=('M · v1.83', 'O · v1.912 ss-MGOT', 'EPI · test0'),
              headers=('Baseline · b=10 FSE / b=0 EPI', 'b=6000 · +z'),
              by_source=(((10, '+x'), (6000, '+z')),
                         ((10, '+x'), (6000, '+z')),
                         ((0, '+x'), (6000, '+z'))))
    images_only = '--images-only' in sys.argv
    # Keep the six-tile ex-vivo preview as a crop/window diagnostic.
    make_image_preview(scans, FIG / 'revised_exvivo_image.png', 'Ex vivo', EX_CROP, ex)
    if not images_only:
        make_kspace_preview(scans, FIG / 'revised_exvivo_kspace.png', 'Ex vivo', ex)
    outputs = []
    for sample, keys, acqs, crop in (
        ('Ex vivo', ('M','O','epi0'), (((10,'+x'),)*2+((0,'+x'),),), EX_CROP),
        ('In vivo', ('iA','iB','epiA'), (((10,'+x'),)*2+((0,'+x'),),), IV_CROP),
    ):
        baseline = acqs[0]
        high = ((6000,'+z'),(6000,'+z'),(6000,'+z'))
        outputs.append(one_row_three_sequence(scans,sample,keys,baseline,crop,'baseline'))
        outputs.append(one_row_three_sequence(scans,sample,keys,high,crop,'b6000'))
        if not images_only:
            outputs.append(one_row_three_sequence(scans,sample,keys,baseline,crop,'kspace_baseline',True))
            outputs.append(one_row_three_sequence(scans,sample,keys,high,crop,'kspace_b6000',True))
    outputs.append(epi_fse_image_2x3(scans,'Ex vivo','epi0','M',EX_CROP,True))
    outputs.append(epi_fse_image_2x3(scans,'In vivo','epiA','iA',IV_CROP,False))
    outputs.extend(epi_fse_individual_tiles(scans,'Ex vivo','epi0','M',EX_CROP,True))
    outputs.extend(epi_fse_individual_tiles(scans,'In vivo','epiA','iA',IV_CROP,False))
    print('\n'.join(str(p) for p in outputs))


if __name__ == '__main__':
    main()

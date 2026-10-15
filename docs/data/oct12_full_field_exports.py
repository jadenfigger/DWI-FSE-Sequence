"""Export full-field Oct 12 reconstruction and log-k-space PNGs.

Matches scanner/recon/bare_bones_recon_fse.py's standalone image display:
black figure/axes, default upper-origin imshow, equal pixel aspect, and a right
colorbar. No crop, resampling, normalization, or overlays are applied.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.axes_grid1 import make_axes_locatable

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'docs' / 'data'
OUT = ROOT / 'docs' / 'figures' / 'physical_scanner_2026-10-12' / 'full_field_exports'
SLIDE = OUT / 'slide_ready'
PREVIEW = OUT / 'preview'
sys.path.insert(0, str(DATA))
from oct12_load import load, folder, get_mrd_3d4, direction_label  # noqa: E402

SCANS = {
    'M': ('exvivo', 'v1.83'), 'O': ('exvivo', 'v1.912_ss-MGOT'),
    'epi0': ('exvivo', 'EPI_test0'), 'iA': ('invivo', 'v1.83'),
    'iB': ('invivo', 'v1.912_ss-MGOT'), 'epiA': ('invivo', 'EPI_invivoA'),
}


def load_all():
    result = {}
    for key in SCANS:
        if key.startswith('epi'):
            path = next(folder(key).glob('*_o.MRD'))
            raw, dims, _ = get_mrd_3d4(path)
            kspace = np.asarray(raw[:, 0, :, 0])
            cimg = np.fft.fftshift(
                np.fft.ifft2(np.fft.ifftshift(kspace, axes=(-2, -1))), axes=(-2, -1)
            )[..., ::-1]
            from oct12_load import load_epi
            meta = load_epi(key)
            result[key] = dict(key=key, image=np.abs(cimg), kspace=kspace,
                               b=np.asarray(meta['b']), vec=np.asarray(meta['vec']),
                               offsets=np.asarray(meta['offsets_mm'], float),
                               version=SCANS[key][1], dims=tuple(cimg.shape[-2:]),
                               fov=meta.get('fov_mm', None))
        else:
            s = load(key, shot_mode='off')
            result[key] = dict(key=key, image=np.asarray(s['img']), kspace=np.asarray(s['kspace']),
                               b=np.asarray(s['b']), vec=np.asarray(s['vec']),
                               offsets=np.asarray(s['offsets_mm'], float),
                               version=SCANS[key][1], dims=tuple(s['img'].shape[-2:]),
                               fov=s.get('fov_mm', None))
    return result


def limits_for(scans):
    limits = {}
    for sample, keys in [('exvivo', ('M', 'O', 'epi0')),
                         ('invivo', ('iA', 'iB', 'epiA'))]:
        vmax_img = max(float(np.max(np.abs(scans[k]['image']))) for k in keys)
        vmax_k = max(float(np.max(np.log1p(np.abs(scans[k]['kspace'])))) for k in keys)
        limits[(sample, 'image')] = vmax_img
        limits[(sample, 'log_kspace')] = vmax_k
    return limits


def write_png(data, path, vmax):
    """Render one uncropped image using bare_bones_recon_fse.py formatting."""
    data = np.asarray(data)
    fig, ax = plt.subplots()
    fig.patch.set_facecolor('black')
    ax.set_facecolor('black')
    im = ax.imshow(data, cmap='gray', aspect='equal', origin='upper', vmin=0, vmax=vmax)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    divider = make_axes_locatable(ax)
    cax = divider.append_axes('right', size='5%', pad=0.1)
    cb = fig.colorbar(im, cax=cax)
    cb.ax.yaxis.set_tick_params(color='white', labelcolor='white')
    cb.formatter.set_powerlimits((-2, 3))
    cb.formatter.set_useOffset(False)
    # Keep every character readable, unlike the old three-character truncation.
    cb.ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda val, pos: f'{val:.3g}'))
    cb.update_ticks()
    cb.outline.set_edgecolor('none')
    cb.ax.set_facecolor('black')
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300, facecolor='black', edgecolor='none',
                bbox_inches='tight', pad_inches=0.1)
    plt.close(fig)


def center_slice(scan):
    offsets = scan['offsets']
    return int(np.argmin(np.abs(offsets))) if len(offsets) == scan['image'].shape[1] else scan['image'].shape[1] // 2


def select_volume(scan, b_target, direction):
    candidates = [i for i, b in enumerate(scan['b'])
                  if abs(float(b) - b_target) < 2 and direction_label(scan['vec'][i]) == direction]
    if not candidates:
        raise ValueError(f"{scan['key']}: missing b={b_target}, direction={direction}")
    return candidates[0]


def export_all(scans, limits):
    rows = []
    for key, scan in scans.items():
        sample = SCANS[key][0]
        image_limit = limits[(sample, 'image')]
        k_limit = limits[(sample, 'log_kspace')]
        for vol in range(scan['image'].shape[0]):
            b = float(scan['b'][vol])
            direction = direction_label(scan['vec'][vol])
            for sl in range(scan['image'].shape[1]):
                base = f'{key}_vol{vol+1:02d}_b{b:g}_{direction}_slice{sl+1:02d}'
                image_rel = f'{sample}_{key}/image_{base}.png'
                k_rel = f'{sample}_{key}/log_kspace_{base}.png'
                write_png(np.abs(scan['image'][vol, sl]), OUT / image_rel, image_limit)
                write_png(np.log1p(np.abs(scan['kspace'][vol, sl])), OUT / k_rel, k_limit)
                rows.append(dict(sample=sample, scan=key, version=scan['version'], volume=vol+1,
                                 b_s_mm2=b, direction=direction, slice=sl+1,
                                 slice_offset_mm=float(scan['offsets'][sl]) if sl < len(scan['offsets']) else '',
                                 image_shape='x'.join(map(str, scan['image'].shape[-2:])),
                                 kspace_shape='x'.join(map(str, scan['kspace'].shape[-2:])),
                                 image_clim=f'0,{image_limit:.8g}', log_kspace_clim=f'0,{k_limit:.8g}',
                                 image_file=image_rel, log_kspace_file=k_rel))
    with (OUT / 'index.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    return rows


def export_slide_ready(scans, limits):
    choices = {
        'M': [(10, '+x'), (1000, '+x'), (6000, '+z')],
        'O': [(10, '+x'), (1000, '+x'), (6000, '+z')],
        'epi0': [(0, '+x'), (1000, '+y'), (6000, '+z')],
        'iA': [(10, '+x'), (1000, '+z'), (6000, '+z')],
        'iB': [(10, '+x'), (1000, '+z'), (6000, '+z')],
        'epiA': [(0, '+x'), (1000, '+z'), (6000, '+z')],
    }
    rows = []
    for key, specs in choices.items():
        scan = scans[key]
        sample = SCANS[key][0]
        sl = center_slice(scan)
        for b_target, direction in specs:
            vol = select_volume(scan, b_target, direction)
            b = float(scan['b'][vol])
            d = direction_label(scan['vec'][vol])
            tag = f'{key}_vol{vol+1:02d}_b{b:g}_{d}_slice{sl+1:02d}'
            image_file = SLIDE / f'{sample}_{tag}_image.png'
            k_file = SLIDE / f'{sample}_{tag}_log_kspace.png'
            write_png(np.abs(scan['image'][vol, sl]), image_file, limits[(sample, 'image')])
            write_png(np.log1p(np.abs(scan['kspace'][vol, sl])), k_file, limits[(sample, 'log_kspace')])
            rows.append(dict(sample=sample, scan=key, version=scan['version'], volume=vol+1,
                             b_s_mm2=b, direction=d, slice=sl+1,
                             slice_offset_mm=float(scan['offsets'][sl]) if sl < len(scan['offsets']) else '',
                             image_file=image_file.name, log_kspace_file=k_file.name))
    with (SLIDE / 'index.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    scans = load_all()
    limits = limits_for(scans)
    limits_out = {f'{sample}_{kind}': value for (sample, kind), value in limits.items()}
    (OUT / 'limits.json').write_text(json.dumps(limits_out, indent=2), encoding='utf-8')
    print(json.dumps(limits_out, indent=2))
    # Always make a pair of previews first, before the user reviews the export.
    for key, vol, sl, kind in [('M', 0, center_slice(scans['M']), 'image'),
                                ('epi0', 0, center_slice(scans['epi0']), 'image')]:
        sample = SCANS[key][0]
        out = PREVIEW / f'preview_{key}_{kind}.png'
        write_png(np.abs(scans[key]['image'][vol, sl]), out, limits[(sample, 'image')])
    if '--preview-only' in sys.argv:
        return
    rows = export_all(scans, limits)
    export_slide_ready(scans, limits)
    (OUT / 'README.md').write_text(make_readme(scans, limits, len(rows)), encoding='utf-8')
    print(f'Wrote {len(rows)} image/k-space pairs; slides selected for central-slice review.')


def make_readme(scans, limits, nrows):
    lines = [
        '# Oct 12 full-field reconstruction exports', '',
        'All images are uncropped, unresampled full grids rendered on black using the scanner reconstruction script display convention. The image files show raw reconstructed magnitude in reconstruction units, with no σ normalization. The k-space files show `ln(1 + |K|)` from raw complex magnitude, with no per-panel normalization. Each sample/type group uses one fixed 0-to-maximum color scale across every selected sequence, b-value, volume, and slice. Colorbar ticks are readable and untruncated.', '',
        'FSE k-space is the actual complex PE-reordered acquisition grid. EPI k-space is the native vendor-processed complex `_o.MRD` grid; EPI image is its inverse FFT with only the verified read-axis reversal used for display. EPI remains 128×168 and is shown without resampling; FSE retains its native grid. EPI direction labels are decoded from the acquisition b-table and remain provisional. Receiver gains and reconstruction/vendor processing differ across acquisitions, so displayed magnitude is not calibrated SNR and should not be treated as a cross-sequence intensity measurement.', '',
        'The four shared limits are:', '',
        '| Group | vmin | vmax |', '|---|---:|---:|',
    ]
    for (sample, kind), value in limits.items():
        lines.append(f'| {sample} {kind} | 0 | {value:.9g} |')
    lines += ['', 'Full exports are indexed in [`index.csv`](index.csv). Selected central slices for slide assembly are in [`slide_ready/`](slide_ready/) with a separate [`slide_ready/index.csv`](slide_ready/index.csv). The PNG bundle is [`oct12_full_field_exports.zip`](../oct12_full_field_exports.zip).', '',
              f'Full export index contains {nrows} acquisition-volume/slice rows across M, O, iA, iB, test0 EPI, and invivoA EPI.']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    main()

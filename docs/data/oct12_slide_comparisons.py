"""Create slide-ready image comparisons from plain FFT reconstructions of Oct 12 MRDs.

Run from the repository root: python docs/data/oct12_slide_comparisons.py
Outputs are written to docs/figures/physical_scanner_2026-10-12/slide_*.png.
FSE is reconstructed from its raw MRD without navigator correction. Lab EPI uses
the vendor-processed _o.MRD k-space followed by a plain inverse FFT, preserving
the native 168-sample read axis. Each panel is windowed independently; displayed
magnitudes are for anatomy/contrast inspection, not quantitative intensity comparison.
"""
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'docs' / 'data'
FIG = ROOT / 'docs' / 'figures' / 'physical_scanner_2026-10-12'
sys.path.insert(0, str(DATA))

from oct12_load import load, load_epi, direction_label  # noqa: E402

FOV_MM = 35.0
PE_R_FOV_MM = 35.0 / 1.125
CROP_X_MM = 14.0
CROP_Y_INVIVO_MM = (-14.0, 14.0)
CROP_Y_EXVIVO_MM = (2.0, 17.5)
SCALEBAR_MM = 5.0


def centre_slice(s):
    offsets = np.asarray(s.get('offsets_mm', []), float)
    return int(np.argmin(np.abs(offsets))) if len(offsets) == s['S'] else int(s['S'] // 2)


def volume_index(s, b, direction=None, tolerance=2.0):
    candidates = [i for i, value in enumerate(s['b']) if abs(float(value) - b) <= tolerance]
    if direction is not None:
        candidates = [i for i in candidates if direction_label(s['vec'][i]) == direction]
    if not candidates:
        present = [(round(float(v)), direction_label(s['vec'][i])) for i, v in enumerate(s['b'])]
        raise ValueError(f"{s['key']}: no b={b} {direction or ''}; available={present}")
    return candidates[0]


def get_image(s, b, direction=None):
    ei = volume_index(s, b, direction)
    sl = centre_slice(s)
    if 'cimg' in s:
        # Native 128 × 168 EPI k-space is inverse transformed without read-axis resampling.
        image = np.abs(s['cimg'][ei, sl])
        extent = (-FOV_MM / 2, FOV_MM / 2, -FOV_MM / 2, FOV_MM / 2)
    else:
        image = np.asarray(s['img'][ei, sl])
        fov_pe = PE_R_FOV_MM if s['key'] == 'R' else FOV_MM
        extent = (-FOV_MM / 2, FOV_MM / 2, -fov_pe / 2, fov_pe / 2)
    return image, extent, float(s['b'][ei]), direction_label(s['vec'][ei]), sl + 1


def draw_panel(ax, s, b, direction, panel_label, column_header, crop_y):
    image, extent, actual_b, actual_dir, sl = get_image(s, b, direction)
    vmin = 0.0
    vmax = float(np.percentile(image, 99.5))
    if not np.isfinite(vmax) or vmax <= 0:
        vmax = 1.0
    ax.imshow(image, cmap='gray', origin='lower', extent=extent, vmin=vmin, vmax=vmax,
              interpolation='nearest', aspect='equal')
    ax.set_xlim(-CROP_X_MM, CROP_X_MM)
    ax.set_ylim(*crop_y)
    ax.set_axis_off()
    ax.set_title(f'{column_header} · {panel_label} · b={actual_b:g} {actual_dir} · slice {sl}',
                 color='white', fontsize=7.4, pad=3.2)
    # White 5 mm scale bar with a dark outline so it remains visible over anatomy.
    x0, y0 = -CROP_X_MM + 1.0, crop_y[0] + 1.2
    ax.add_patch(Rectangle((x0 - .08, y0 - .08), SCALEBAR_MM + .16, .44,
                           facecolor='black', edgecolor='none', alpha=.55, zorder=4))
    ax.plot([x0, x0 + SCALEBAR_MM], [y0, y0], color='white', lw=2.2,
            solid_capstyle='butt', zorder=5)
    ax.text(x0 + SCALEBAR_MM / 2, y0 + .28, '5 mm', color='white', fontsize=7,
            ha='center', va='bottom', zorder=5,
            bbox=dict(facecolor='black', edgecolor='none', alpha=.55, pad=1.2))


def figure_grid(path, panels, column_headers, row_headers, note, crop_y):
    fig, axes = plt.subplots(2, 3, figsize=(12.8, 7.2), dpi=220, constrained_layout=False)
    fig.patch.set_facecolor('#111111')
    for ax in axes.flat:
        ax.set_facecolor('#111111')
    for r, row in enumerate(panels):
        for c, panel in enumerate(row):
            scan, b, direction, label = panel
            draw_panel(axes[r, c], scan, b, direction, label, column_headers[c], crop_y)
    for r, label in enumerate(row_headers):
        axes[r, 0].text(-.09, .5, label, transform=axes[r, 0].transAxes,
                        rotation=90, ha='center', va='center', color='white', fontsize=9)
    fig.text(.5, .025, note, color='#dddddd', ha='center', va='bottom', fontsize=7.1)
    fig.subplots_adjust(left=.075, right=.99, top=.91, bottom=.08, wspace=.035, hspace=.19)
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches='tight', pad_inches=.12)
    plt.close(fig)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    scans = {key: load(key, shot_mode='off') for key in ('M', 'O', 'iA', 'iB')}
    epi = {'epi0': load_epi('epi0'), 'epiA': load_epi('epiA')}

    # The common ex-vivo high-b comparison is +z at b6000 for both FSE versions and EPI.
    figure_grid(
        FIG / 'slide_exvivo_three_sequence.png',
        [
            [(scans['M'], 10, '+x', 'M · v1.83'), (scans['O'], 10, '+x', 'O · v1.912'), (epi['epi0'], 0, None, 'EPI test0')],
            [(scans['M'], 6000, '+z', 'M · v1.83'), (scans['O'], 6000, '+z', 'O · v1.912'), (epi['epi0'], 6000, '+z', 'EPI test0')],
        ],
        ['FSE', 'FSE', 'EPI'],
        ['Baseline', 'b=6000 +z'],
        'Central slice · each image windowed independently; magnitude is not quantitative · EPI played directions are provisional.',
        CROP_Y_EXVIVO_MM,
    )
    figure_grid(
        FIG / 'slide_invivo_three_sequence.png',
        [
            [(scans['iA'], 10, '+x', 'iA · v1.83'), (scans['iB'], 10, '+x', 'iB · v1.912'), (epi['epiA'], 0, None, 'EPI invivoA')],
            [(scans['iA'], 6000, '+z', 'iA · v1.83'), (scans['iB'], 6000, '+z', 'iB · v1.912'), (epi['epiA'], 6000, '+z', 'EPI invivoA')],
        ],
        ['FSE', 'FSE', 'EPI'],
        ['Baseline', 'b=6000 +z'],
        'Central slice · each image windowed independently; magnitude is not quantitative · EPI played directions are provisional.',
        CROP_Y_INVIVO_MM,
    )
    figure_grid(
        FIG / 'slide_exvivo_epi_vs_v183.png',
        [
            [(epi['epi0'], 0, None, 'EPI test0'), (epi['epi0'], 1000, '+y', 'EPI test0'), (epi['epi0'], 6000, '+z', 'EPI test0')],
            [(scans['M'], 10, '+x', 'M · v1.83'), (scans['M'], 1000, '+x', 'M · v1.83'), (scans['M'], 6000, '+z', 'M · v1.83')],
        ],
        ['Baseline', 'b=1000', 'b=6000'],
        ['lab EPI', 'v1.83 FSE'],
        'Ex vivo central slice · labels show actual b and direction (b1000 EPI +y; FSE +x) · independent windowing · EPI directions provisional.',
        CROP_Y_EXVIVO_MM,
    )
    figure_grid(
        FIG / 'slide_invivo_epi_vs_v183.png',
        [
            [(epi['epiA'], 0, None, 'EPI invivoA'), (epi['epiA'], 1000, '+z', 'EPI invivoA'), (epi['epiA'], 6000, '+z', 'EPI invivoA')],
            [(scans['iA'], 10, '+x', 'iA · v1.83'), (scans['iA'], 1000, '+z', 'iA · v1.83'), (scans['iA'], 6000, '+z', 'iA · v1.83')],
        ],
        ['Baseline', 'b=1000 +z', 'b=6000 +z'],
        ['lab EPI', 'v1.83 FSE'],
        'In vivo central slice · each image windowed independently; magnitude is not quantitative · EPI played directions are provisional.',
        CROP_Y_INVIVO_MM,
    )
    print('\n'.join(str(p) for p in sorted(FIG.glob('slide_*.png'))))


if __name__ == '__main__':
    main()

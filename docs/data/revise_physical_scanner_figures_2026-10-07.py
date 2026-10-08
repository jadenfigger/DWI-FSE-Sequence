"""Make six simpler presentation figures with the FSE navigator correction.

Run: python docs/data/revise_physical_scanner_figures_2026-10-07.py
The original figures, acquisitions, and numerical reports are left in place.
"""
from pathlib import Path
import importlib.util
import io

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator


SOURCE = Path(__file__).with_name("physical_scanner_analysis_2026-10-07.py")
spec = importlib.util.spec_from_file_location("oct07_analysis", SOURCE)
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
OUT = analysis.OUT / "revised"
B_VALUES = (0, 1000, 6000)
# Shared reconstruction helpers use deramp, phase correction, and nav_eps=0.01,
# matching scanner/recon/bare_bones_recon_fse.py's active navigator settings.
CORRECTION_MODE = "deramp"
GROUPS = (
    (
        ("test0", "test1"),
        "crusher_amplitude.png",
        "Imaging Train Crusher Amplitude Comparison",
        ("−5482 DAC\n(test0)", "−8223 DAC\n(test1)"),
    ),
    (
        ("test1", "test2", "test3"),
        "new_methods_etl8.png",
        "New Method Comparison (ETL8)",
        ("original\n(test1)", "ss-MGOT\n(test2)", "Alsop\n(test3)"),
    ),
    (
        ("test1b", "test2c", "test3c"),
        "new_methods_etl16.png",
        "New Method Comparison (ETL16)",
        ("original\n(test1b)", "ss-MGOT\n(test2c)", "Alsop\n(test3c)"),
    ),
)


def montage(scans, names, filename, title, row_labels, kspace=False):
    # Correct complex imaging lines before the inverse FFT or k-space display.
    values = [
        [
            np.log10(1 + abs(analysis.sorted_kspace(scans[name], e, mode=CORRECTION_MODE)))
            if kspace else abs(scans[name]["images"][e][CORRECTION_MODE])
            for b in B_VALUES
            for e in [analysis.bindex(scans[name], b)]
        ]
        for name in names
    ]
    maxima = [max(row[c].max() for row in values) for c in range(3)]
    fig, axes = plt.subplots(
        len(names), 3, figsize=(10.8, 2.7 * len(names) + .5),
        squeeze=False, layout="constrained",
    )
    for r, row in enumerate(values):
        for c, data in enumerate(row):
            ax = axes[r, c]
            ax.imshow(
                data, cmap="magma" if kspace else "gray", vmin=0,
                vmax=maxima[c], origin="upper", interpolation="nearest",
            )
            ax.set_axis_off()
            if r == 0:
                ax.set_title(f"b = {B_VALUES[c]}", fontsize=11, pad=7)
            if c == 0:
                ax.text(
                    -.07, .5, row_labels[r], transform=ax.transAxes,
                    ha="right", va="center", fontsize=10,
                )
    for c in range(3):
        bar = fig.colorbar(
            axes[0, c].images[0], ax=axes[:, c].tolist(),
            shrink=.45, fraction=.035, pad=.025,
        )
        bar.locator = MaxNLocator(nbins=4)
        bar.update_ticks()
        bar.ax.tick_params(labelsize=9)
    fig.suptitle(title + (" (k-space)" if kspace else ""), fontsize=14)
    destination = OUT / (("kspace_" if kspace else "") + filename)
    output = io.BytesIO()
    fig.savefig(output, format="png", dpi=200, facecolor="white", bbox_inches="tight", pad_inches=.08)
    # Write a complete replacement so an open image preview never sees a partial PNG.
    temporary = destination.with_suffix(".png.tmp")
    temporary.write_bytes(output.getvalue())
    temporary.replace(destination)
    plt.close(fig)
    print(destination.relative_to(analysis.ROOT))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    scans = analysis.load_scans()
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10}):
        for names, filename, title, labels in GROUPS:
            for kspace in (False, True):
                montage(scans, names, filename, title, labels, kspace=kspace)


if __name__ == "__main__":
    main()

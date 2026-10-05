import os
import re
import json
from mpl_toolkits.axes_grid1 import make_axes_locatable
import matplotlib.pyplot as plt
import numpy as np

from get_mrd_3d4 import get_mrd_3d4
import snr_utils as su

# --- MODE TOGGLE ---
save_images_mode = True  # Set to True for saving mode, False for display mode,  None for don't make figures or display; only write NIfTI (if save_nifti=True)
save_nifti = True  # also write the reconstructed images to a NIfTI volume
plot_t2_toggle = False  # Save a diagnostic plot of T2(x) per slice if navigator is on

# --- PHASE-ENCODE ORDER ---
# None = read PE_order from the MRD's embedded PPR. Set 1, 6, or 7 to override.
# 1 = centric interleaved; 6 = reverse-centric; 7 = linear interleaved.
pe_order_override = None

month = "09"
date = "15"
test_num = "1_posx"
version = "v14"
base_dir = r"C:\Users\jaden\Downloads\J_Figger"
stem_name = f"FSE-DWI_{month}-{date}-2026_{version}_test{test_num}"
filename = rf"{base_dir}\{stem_name}\{stem_name}.MRD"

# --- NAVIGATOR CORRECTION ---
nav_mode        = "deramp"   # "deramp" = Zhou Eq.5 analogue (remove steps, keep trend)
                             # "flatten" = Zhou Eq.6 analogue (remove envelope entirely)
                             # "off"     = measure and report only, no correction
nav_apply_phase = True       # Zhou uses magnitude only; keep True but watch the printout
nav_eps         = 0.01       # Wiener regularizer, fraction of echo-1 amplitude
nav_report      = True       # print the envelope table + plot it
nav_report_slice = 0         # only print/plot the nav diagnostics for this slice

# --- SLICE ORDER ---
# Leave this at None.  The console writes each acquisition into the slice slot
# given by pos_index (the BATCHSLICE macro), not into the slot given by the
# multislice loop counter, so the MRD slice axis is ALREADY in table/position
# order and is independent of :SLICE_INTERLEAVE.  Verified two ways:
slice_order = None


def write_nifti(vol, path, fov_mm, dz_mm, z0_mm, descrip=""):
    import nibabel as nib

    nx, ny, nz = vol.shape[:3]
    dx, dy = fov_mm / nx, fov_mm / ny
    affine = np.diag([dx, dy, dz_mm, 1.0])
    affine[:3, 3] = [-dx * nx / 2.0, -dy * ny / 2.0, z0_mm]

    img = nib.Nifti1Image(vol.astype(np.float32), affine)
    img.header.set_xyzt_units("mm")
    img.header["descrip"] = descrip[:80].encode()
    nib.save(img, path)


def read_header_text(path):
    """Return only the PPR section appended to the MRD.

    Decoding the whole file and regexing it risks matching ':FOV', ':VAR ...' and
    friends inside the binary k-space block, which silently yields a plausible but
    wrong number.  The PPR is appended after the data and always starts at ':PPL'.
    """
    with open(path, "rb") as fh:
        text = fh.read().decode("latin-1", errors="ignore")
    start = text.find(":PPL")
    if start < 0:
        raise ValueError(f"no PPR section found in {path}")
    return text[start:]


def check_sidecar_ppr(mrd_path, header):
    """The .ppr sitting next to the MRD is a saved protocol, not an acquisition log.

    It can be re-saved or copied between test folders after the fact, so it may not
    describe the scan that produced the MRD.  The PPR embedded in the MRD is written
    at acquisition time and is the authoritative record.  test4a is a live example:
    its folder .ppr claims slice offsets of +/-1.4 mm and a 1.2 mm slice separation,
    while the MRD says +/-0.4 mm and 0.2 mm.
    """
    folder = os.path.dirname(mrd_path)
    ppr_files = [f for f in os.listdir(folder) if f.lower().endswith(".ppr")]
    if not ppr_files:
        return
    sidecar = os.path.join(folder, ppr_files[0])
    with open(sidecar, "rb") as fh:
        side = fh.read().decode("latin-1", errors="ignore")

    keys = ("NO_SLICES", "SLICE_INTERLEAVE", "SLICE_THICKNESS", "SLICE_SEPARATION",
            "NO_VIEWS", "VIEWS_PER_SEGMENT", "FOV", "FOV_SLICE_OFF",
            "EXPERIMENT_ARRAY", "NO_AVERAGES")
    bad = []
    for key in keys:
        pat = rf"^:{key}\s+([^\r\n]*(?:\r?\n,[^\r\n]*)*)"
        a = re.search(pat, side, re.M)
        b = re.search(pat, header, re.M)
        av = " ".join(a.group(1).split()) if a else None
        bv = " ".join(b.group(1).split()) if b else None
        if av != bv:
            bad.append((key, av, bv))

    if bad:
        print(f"\nWARNING: {ppr_files[0]} does not match the PPR embedded in the MRD. "
              "The embedded one is used; the folder .ppr is stale.")
        for key, av, bv in bad:
            print(f"  :{key:<18} folder.ppr = {av}")
            print(f"  {'':<19} MRD        = {bv}")


def read_geometry(text):
    """FOV and slice pitch in mm.

    :SLICE_SEPARATION is centre-to-centre pitch, not an edge-to-edge gap, so it is
    the pitch on its own and must not have the thickness added to it.  Confirmed on
    Stock-FSE_08-25-2026_s2_test0: separation 1.09907 with 1 mm slices gives an
    acquired :FOV_SLICE_OFF pitch of 1.1 mm, not 2.1 mm.  The gap is
    separation - thickness, and is negative when the slices overlap.
    """
    fov = re.search(r":FOV\s+([\d.]+)", text, re.M)
    sep = re.search(r":SLICE_SEPARATION\s+\w+,\s*-?\d+,\s*([\d.]+)", text, re.M)
    return (
        float(fov.group(1)) if fov else 1.0,
        float(sep.group(1)) if sep else read_thickness(text),
    )


def read_thickness(text):
    m = re.search(r":SLICE_THICKNESS\s+\w+,\s*-?\d+,\s*([\d.]+)", text, re.M)
    return float(m.group(1)) if m else 1.0


def ppr_var(text, name, default=0.0):
    m = re.search(rf"^:VAR\s+{re.escape(name)},\s*(-?[\d.]+)", text, re.M | re.I)
    return float(m.group(1)) if m else default


def read_pe_order(text, override=None):
    value = override if override is not None else ppr_var(text, "PE_order", None)
    if value not in (1, 6, 7):
        raise ValueError(f"Missing or unsupported PE_order: {value}. "
                         "Set pe_order_override to the acquired order (1, 6, or 7).")
    return int(value)


def pe_rows(N, etl, pe_order):
    """Image-row indices in acquisition order; navigator is handled separately."""
    if pe_order not in (1, 6, 7):
        raise ValueError("Supported PE_order values are 1, 6, and 7.")
    if etl < 2 or N <= 0 or N % 2 or N % etl:
        raise ValueError("Need ETL > 1 and positive, even imaging views divisible by ETL.")
    shots = N // etl
    s = np.arange(shots)[:, None]
    e = np.arange(etl)[None, :]
    if pe_order == 7:
        rows = s + e * shots
    else:
        if shots % 2:
            raise ValueError("PE_order 1 and 6 require imaging views divisible by 2*ETL.")
        v = shots // 2
        if pe_order == 6:
            e = etl - 1 - e
        rows = N // 2 + s - v + np.where(s < v, -v * e, v * e)
    return rows.ravel()


def ppr_array(text, name):
    """PPR arrays run over several lines and end at the next line starting with ':'."""
    m = re.search(rf":VAR_ARRAY {name},\s*\d+,(.*?)(?=\r?\n:)", text, re.S)
    if not m:
        return np.array([])
    return np.array([float(v) for v in re.findall(r"-?[\d.]+", m.group(1))])


def read_slice_offsets(text):
    m = re.search(r":FOV_OFFSETS\s+\d+(.*?)(?=\r?\n:)", text, re.S)
    if not m:
        return np.array([])
    vals = [float(v) for v in re.findall(r"-?[\d.]+", m.group(1))]
    return np.array(vals[2::3])          # each row is x, y, z; keep z


def slice_axis(offsets, slice_mm, n):
    """Prefer the acquired slice positions; fall back to thickness + separation.

    When the offsets are unevenly spaced a NIfTI affine cannot represent them at
    all, so use the mean spacing rather than thickness + separation: the latter
    describes a contiguous stack the scan did not acquire and can be several times
    too large (test4b: 2.2 mm assumed vs 0.7 mm mean actual).  The true positions
    go in the JSON sidecar either way.
    """
    if offsets.size == n and n > 1:
        d = np.diff(offsets)
        if np.allclose(d, d[0], atol=1e-3):
            return float(d[0]), float(offsets[0])
        print("WARNING: slice offsets are not evenly spaced, so the NIfTI z axis is "
              "only approximate. True offsets (mm): " + ", ".join(f"{o:g}" for o in offsets))
        return float(d.mean()), float(offsets[0])
    return slice_mm, -slice_mm * (n - 1) / 2.0


def report_slice_overlap(offsets, thickness_mm, signal):
    """Slice cross-talk report.

    Two 2D slices whose excited profiles overlap saturate each other within one TR,
    so the later of the pair loses signal.  Nothing in the recon can undo this, but
    it is easy to mistake for a slice-ordering bug, so state it explicitly.
    """
    n = signal.size
    if offsets.size != n:
        return
    print(f"\n=== slice overlap / cross-talk (thickness {thickness_mm:g} mm) ===")
    print("slice   pos(mm)   overlaps        rel. signal")
    rel = signal / signal.max() if signal.max() > 0 else signal
    for i in range(n):
        nbr = [str(j + 1) for j in range(n)
               if j != i and abs(offsets[j] - offsets[i]) < thickness_mm]
        print(f"{i + 1:4d}  {offsets[i]:8.2f}   {','.join(nbr) if nbr else '-':<14}  {rel[i]:.3f}")
    if any(abs(offsets[j] - offsets[i]) < thickness_mm
           for i in range(n) for j in range(i + 1, n)):
        print("  WARNING: excited slice profiles overlap. The signal differences between "
              "slices are saturation, not a recon or slice-ordering error.")

def dac_from_b(b, delta_ms, big_delta_ms):
    d, D = delta_ms * 1e-3, big_delta_ms * 1e-3
    g = np.sqrt(np.maximum(b, 0.0) * 1e6 / (D - d / 3.0)) / (gamma * d)
    return g / (grad_fs_mT_m * 1e-3) * dac_fs

def read_diffusion(text):
    """Per-diffusion-step b values, gradient DACs and unit directions.

    Mode 0: acq_grad holds the DAC actually played, b follows from Stejskal-Tanner.
    Mode 1: acq_b holds the requested b, the DAC is what the sequence had to play.
    acq_grad is not written back in mode 1, so it is derived rather than read.
    """
    n = int(ppr_var(text, "no_diff_acq", 1))
    delta = ppr_var(text, "sm_delta") / 1000.0        # us -> ms
    big_delta = ppr_var(text, "big_delta") / 1000.0
    scale = ppr_var(text, "diff_grad_scale", 100.0) / 100.0
    mode = int(ppr_var(text, "b_input_mode", 0))

    vec = np.stack([ppr_array(text, f"acq_{a}")[:n] for a in ("x", "y", "z")], axis=1) / 1000.0
    norm = np.linalg.norm(vec, axis=1)
    unit = np.zeros_like(vec)
    unit[norm > 0] = vec[norm > 0] / norm[norm > 0, None]

    if mode == 0:
        # DAC values were entered; do not derive b-values.
        dac = ppr_array(text, "acq_grad")[:n] * scale
        b = None
        unit[dac <= 0] = 0.0
    else:
        # b-values were entered; do not derive DAC values.
        b = ppr_array(text, "acq_b")[:n]
        dac = None
        unit[b <= 0] = 0.0

    return dict(n=n, mode=mode, delta=delta, big_delta=big_delta,
                b=b, dac=dac, unit=unit)


def nav_envelope(k_acq, etl):
    """Per-echo amplitude and phase from the navigator shot.

    Amplitude uses the L2 norm of the line (Parseval), which is insensitive to a
    readout-direction phase ramp. Summing along the readout instead gives the DC
    sample, which partially cancels if such a ramp exists and biases amplitude low.
    Phase still comes from the DC sample, where it is meaningful.
    """
    nav_lines = k_acq[:etl, :]
    amp = np.linalg.norm(nav_lines, axis=1)
    amp = amp / amp[0]
    dc = nav_lines.sum(axis=1)
    phase = np.angle(dc * np.conj(dc[0]))          # wrapped to [-pi, pi]
    return amp, phase, nav_lines


def nav_profile_spread(nav_lines, frac=0.15):
    """Zhou fits T2(x) per readout position rather than one scalar per echo.

    This checks whether that matters here: it projects each navigator along the
    readout and reports how much the normalised envelope varies across the object.
    Small spread means a single scalar per echo is an adequate approximation.
    """
    proj = np.abs(np.fft.fftshift(
        np.fft.ifft(np.fft.ifftshift(nav_lines, axes=1), axis=1), axes=1))
    mask = proj[0] > frac * proj[0].max()
    if mask.sum() < 8:
        return None
    ratio = proj[:, mask] / proj[0, mask]          # etl x npix
    return ratio.std(axis=1) / np.abs(ratio.mean(axis=1))


def nav_correction(amp, phase, echo_idx, rows, N, mode, apply_phase, eps, pe_order=1):
    """Build the per-acquisition correction factor.

    'flatten' divides the measured envelope out completely. Zhou notes this is the
    noise-amplifying form: the filter acts on noise as well as signal, whereas the
    original weighting acted only on signal.

    'deramp' instead interpolates a smooth envelope through the per-echo values as a
    function of |k_y| (signed k_y for linear order) and corrects only the difference.
    That removes the staircase
    discontinuity, which is what causes ringing, while leaving the smooth trend in
    place, so noise is barely amplified.
    """
    w_step = amp[echo_idx]

    if mode == "flatten":
        w_target = np.ones_like(w_step)
    elif mode == "deramp":
        ky = rows - N // 2
        coordinate = ky if pe_order == 7 else np.abs(ky)
        centre = np.array([coordinate[echo_idx == n].mean() for n in range(amp.size)])
        order = np.argsort(centre)
        w_target = np.interp(coordinate, centre[order], amp[order])
    else:
        w_target = w_step.copy()

    corr = w_target * w_step / (w_step ** 2 + eps ** 2)     # Wiener-regularised
    if apply_phase:
        corr = corr * np.exp(-1j * phase[echo_idx])
    return corr.astype(np.complex64)

def nav_fit_t2_per_x(nav_lines, esp_ms, frac=0.15):
    """Fits T2(x) for each readout position (x) using the navigator echo train.

    1. Transforms navigator k-space lines to 1D spatial projections P(x, TE).
    2. Filters out low-signal background regions.
    3. Fits a single exponential decay curve P(x, TE) = P0(x) * exp(-TE / T2(x))
       per pixel along the readout direction (x).

    Returns:
        t2_map: 1D array of T2 values in ms per readout pixel (NaN for background).
        mean_t2: Mean T2 in ms over the high-signal object region.
        std_t2: Standard deviation of T2 across the object region.
    """
    # 1D Inverse FT along readout (axis 1) to get spatial projections P(x, TE)
    proj = np.abs(np.fft.fftshift(
        np.fft.ifft(np.fft.ifftshift(nav_lines, axes=1), axis=1), axes=1))

    etl, n_samples = proj.shape
    te_array = np.arange(1, etl + 1) * esp_ms  # Array of echo times in ms

    # Mask out noise/background based on peak threshold of the first echo
    mask = proj[0] > (frac * proj[0].max())

    t2_map = np.full(n_samples, np.nan)

    # Linearized exponential fit: ln(P) = ln(P0) - TE / T2
    # Fits for all valid readout positions simultaneously
    if mask.sum() > 0:
        log_proj = np.log(np.maximum(proj[:, mask], 1e-10))
        # Fit slope using linear regression: TE vs log(Signal)
        A = np.vstack([-te_array, np.ones(etl)]).T
        slopes, _ = np.linalg.lstsq(A, log_proj, rcond=None)[0]

        # T2 = 1 / slope (ignore negative slopes from noise/instability)
        valid_slopes = slopes > 0
        t2_values = np.full(mask.sum(), np.nan)
        t2_values[valid_slopes] = 1.0 / slopes[valid_slopes]

        t2_map[mask] = t2_values

    valid_t2s = t2_map[~np.isnan(t2_map)]
    if len(valid_t2s) > 0:
        return t2_map, np.nanmean(valid_t2s), np.nanstd(valid_t2s)
    else:
        return t2_map, np.nan, np.nan


def plot_t2_profile(t2_map, exp_idx, slice_idx, save_dir):
    """Plots and saves the T2(x) profile across the readout axis."""
    fig, ax = plt.subplots()
    ax.plot(t2_map, color='tab:blue', lw=1.5, label='Fitted $T_2(x)$')
    ax.set_xlabel("Readout Position ($x$ voxel)")
    ax.set_ylabel("$T_2$ decay time (ms)")
    ax.set_title(f"Projected $T_2(x)$ Map - Exp {exp_idx + 1}, Slice {slice_idx + 1}")
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend()

    fig.savefig(
        os.path.join(save_dir, f"t2_profile_exp_{exp_idx + 1}_slice_{slice_idx + 1}.png"),
        dpi=300,
        bbox_inches='tight'
    )
    plt.close(fig)


kspace, dim, params = get_mrd_3d4(filename, "seq", "seq")
print(dim)
no_expts = dim[0]
no_slices = dim[2]
no_views = dim[4]
no_samples = dim[5]

header_text = read_header_text(filename)
check_sidecar_ppr(filename, header_text)
diff = read_diffusion(header_text)

etl = int(params['views_per_seg'])
pe_order = read_pe_order(header_text, pe_order_override)
tr = params['tr']
te = params['te']
esp = params['esp']
b_mode = diff['mode']
tcrush = params['tcrush']
diff_tcrush = params['diff_tcrush']
diff_on = int(params['diff_on'])
if pe_order in (6, 7):
    if not diff_on or ppr_var(header_text, "PF_echoes", 0) not in (0, etl):
        raise ValueError("PE_order 6/7 require diffusion mode and full Fourier.")
    if ppr_var(header_text, "echoes_to_discard", 0) != 0:
        raise ValueError("PE_order 6/7 do not support discarded initial echoes.")

print("=== MRD Header Parameters ===")
print(f"Number of Experiments: {no_expts}")
print(f"Number of Slices: {no_slices}")
print(f"Number of Views: {no_views}")
print(f"Number of Samples: {no_samples}")
print(f"Views per Segment (ETL): {etl}")
print(f"PE_order: {pe_order} "
      f"({'manual override' if pe_order_override is not None else 'embedded MRD header'})")
print(f"TR: {tr} ms")
print(f"TE: {te} ms")
print(f"ESP: {esp} ms")
print(f"tcrush: {tcrush} us")
print(f"diff tcrush: {diff_tcrush} us")
print(f"diff on: {diff_on}")
print(f"b-mode: {b_mode}  (0 = DAC entered, 1 = b entered)")
print(f"delta / Delta: {diff['delta']} / {diff['big_delta']} ms")
if diff['b'] is not None:
    print(f"b values (s/mm^2): {np.round(diff['b'], 1)}")
if diff['dac'] is not None:
    print(f"gradient DAC: {np.round(diff['dac'], 1)}")
print(f"directions:\n{np.round(diff['unit'], 3)}")
print(f"slice interleave: {int(params.get('slice_interleave', 1))}  "
      "(storage order in the MRD is unaffected by this; see slice_order above)")
rx_gain = re.findall(r":_ObserveReceiverGain\s+(-?\d+)", header_text)
tx_gain = re.findall(r":_ObserveTransmitGain\s+(-?\d+)", header_text)
print(f"RX gain: {rx_gain}  TX gain: {tx_gain}  "
      "-- absolute intensities are only comparable between scans at equal RX gain")

nav_on = int(ppr_var(header_text, "nav_on", params.get('nav_on', 0)))
acq_offset = etl if nav_on else 0
N = no_views - acq_offset          # true number of image lines (128, not 160)

rows = pe_rows(N, etl, pe_order)
echo_idx = np.arange(N) % etl  # echo number (0-based) for each image acquisition

k_acq_all = np.zeros((no_views, no_samples, no_slices, no_expts), dtype=np.complex64)  # raw, incl. nav
k_sort_all = np.zeros((N, no_samples, no_slices, no_expts), dtype=np.complex64)
img_all = np.zeros((N, no_samples, no_slices, no_expts), dtype=np.float64)

for exp_idx in range(no_expts):
    for slice_idx in range(no_slices):
        k_acq = kspace[exp_idx, 0, slice_idx, 0, :, :]
        k_acq_all[:, :, slice_idx, exp_idx] = k_acq

        k_img = k_acq[acq_offset:, :]  # drop the nav shot, leaving true image rows
        k_sorted = np.zeros((N, no_samples), dtype=np.complex64)
        k_sorted[rows, :] = k_img

        if nav_on:
            nav_amp, nav_phase, nav_lines = nav_envelope(k_acq, etl)

            # Calculate T2(x) per readout position (Zhou et al. style)
            t2_map, mean_t2, std_t2 = nav_fit_t2_per_x(nav_lines, esp_ms=esp)

            if nav_report and slice_idx == nav_report_slice:
                spread = nav_profile_spread(nav_lines)
                print(f"\n--- navigator envelope, exp {exp_idx + 1}, slice {slice_idx + 1} "
                      f"(mode={nav_mode}, phase={'on' if nav_apply_phase else 'off'}) ---")
                print("echo    amp   phase(deg)   spread(%)")
                for n in range(etl):
                    sp = f"{100 * spread[n]:8.1f}" if spread is not None else "     n/a"
                    print(f"{n + 1:4d}  {nav_amp[n]:6.3f}  {np.degrees(nav_phase[n]):9.1f}  {sp}")

                # Diagnostic for spatial variation of T2
                print(f"\n[Zhou Diagnostic] Fitted Spatial T2(x): Mean = {mean_t2:.2f} ms | Std = {std_t2:.2f} ms")
                if not np.isnan(mean_t2) and (std_t2 / mean_t2) > 0.10:
                    print("  WARNING: T2 varies >10% across the object readout. A 1D scalar correction "
                          "may leave residual phase-encode artifacts.")
                else:
                    print("  INFO: T2(x) is relatively uniform across the object readout. Scalar correction is sufficient.")

                if plot_t2_toggle is True:
                    # Save diagnostic plot of T2(x)
                    plot_t2_profile(t2_map, exp_idx, slice_idx, os.path.dirname(filename))

            if nav_mode != "off":
                corr = nav_correction(nav_amp, nav_phase, echo_idx, rows, N,
                                      nav_mode, nav_apply_phase, nav_eps, pe_order)
                k_sorted[rows, :] *= corr[:, None]

        k_sort_all[:, :, slice_idx, exp_idx] = k_sorted

        img_all[:, :, slice_idx, exp_idx] = np.abs(
            np.fft.fftshift(
                np.fft.ifft2(np.fft.ifftshift(k_sorted, axes=(0, 1)), axes=(0, 1)),
                axes=(0, 1),
            )
        )

if slice_order is not None:
    k_acq_all = k_acq_all[:, :, slice_order, :]
    k_sort_all = k_sort_all[:, :, slice_order, :]
    img_all = img_all[:, :, slice_order, :]

if no_slices > 1:
    report_slice_overlap(
        read_slice_offsets(header_text),
        read_thickness(header_text),
        np.percentile(img_all[:, :, :, 0], 99.5, axis=(0, 1)),
    )


su.print_snr(
    img_all.reshape(N, no_samples, -1),
    labels=[f"exp {e + 1} slice {z + 1}" for z in range(no_slices) for e in range(no_expts)],
    noise_width=16,
    mask_method="max_fraction",
)


# Helper function to plot and apply formatting rules depending on the mode
def render_plot(data, title, save_filename, is_line_plot=False):
    fig, ax = plt.subplots(num=title if not save_images_mode else None)

    if save_images_mode:
        fig.patch.set_facecolor('black')
        ax.set_facecolor('black')

        if is_line_plot:
            ax.axis('off')
            ax.plot(data, label="Energy", color='white')
        else:
            im = ax.imshow(data, cmap="gray", aspect="equal")

            # Hide tick marks/frames on main image, but keep axis space structured
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)

            # Fix colorbar dimensions relative to the image axis
            divider = make_axes_locatable(ax)
            cax = divider.append_axes("right", size="5%", pad=0.1)
            cbar = fig.colorbar(im, cax=cax)

            # Style colorbar ticks (white text, max 3 chars formatted, no extra lines)
            cbar.ax.yaxis.set_tick_params(color='white', labelcolor='white')
            cbar.formatter.set_powerlimits((-2, 3))
            cbar.formatter.set_useOffset(False)
            cbar.ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda val, pos: f"{val:.2g}"[:3]))
            cbar.update_ticks()
            cbar.outline.set_edgecolor('none')

        fig.savefig(
            os.path.join(os.path.dirname(filename), save_filename),
            dpi=300,
            facecolor=fig.get_facecolor(),
            edgecolor='none',
            bbox_inches='tight',
            pad_inches=0.1
        )
        plt.close(fig)
    else:
        if is_line_plot:
            ax.plot(data)
            ax.set_yscale("log")
        else:
            im = ax.imshow(data, cmap="gray", aspect="equal")
            divider = make_axes_locatable(ax)
            cax = divider.append_axes("right", size="5%", pad=0.1)
            cbar = fig.colorbar(im, cax=cax)
            cbar.ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda val, pos: f"{val:.2g}"[:3]))

        ax.set_title(title)
        if not is_line_plot and "Image" not in title:
            ax.set_xlabel("Readout (samples)")
            ax.set_ylabel("k_y line")
        elif is_line_plot:
            ax.set_xlabel("k-space row")
            ax.set_ylabel("energy")

# Loop over each experiment and slice to generate separate individual figures
if save_images_mode is not None:
    for exp_idx in range(no_expts):
        for slice_idx in range(no_slices):
            tag = f"exp_{exp_idx + 1}_slice_{slice_idx + 1}"
            label = f"Exp {exp_idx + 1}, Slice {slice_idx + 1}"

            # 1. Reconstructed Image
            render_plot(
                img_all[:, :, slice_idx, exp_idx],
                f"Reconstructed Image - {label}",
                f"reconstructed_image_{tag}.png"
            )

            # # 2. Reordered K-Space
            # render_plot(
            #     np.abs(k_sort_all[:, :, slice_idx, exp_idx]),
            #     f"Reordered Normal K-Space - {label}",
            #     f"reordered_kspace_{tag}.png"
            # )

            # 3. Reordered Log K-Space
            render_plot(
                np.log(1 + np.abs(k_sort_all[:, :, slice_idx, exp_idx])),
                f"Reordered Log K-Space - {label}",
                f"reordered_log_kspace_{tag}.png"
            )

            # # 3. Phase of Reordered K-Space
            # render_plot(
            #     np.angle(k_sort_all[:, :, slice_idx, exp_idx]),
            #     f"Phase of Reordered K-Space - {label}",
            #     f"phase_reordered_kspace_{tag}.png"
            # )

            # # 3. Acquired K-Space
            # render_plot(
            #     np.log(np.abs(k_acq_all[:, :, slice_idx, exp_idx]) + 1),
            #     f"Acquired K-Space - {label}",
            #     f"acquired_kspace_{tag}.png"
            # )

            # # 4. Sorted Row Energy
            # row_energy_sorted = np.sum(np.abs(k_sort_all[:, :, slice_idx, exp_idx]) ** 2, axis=1)
            # render_plot(
            #     row_energy_sorted,
            #     f"Sorted Row Energy - {label}",
            #     f"sorted_kspace_{tag}.png",
            #     is_line_plot=True
            # )

            # # 5. Acquired Row Energy
            # row_energy = np.sum(np.abs(k_acq_all[:, :, slice_idx, exp_idx]) ** 2, axis=1)
            # render_plot(
            #     row_energy,
            #     f"Acquired Row Energy - {label}",
            #     f"acquired_row_energy_{tag}.png",
            #     is_line_plot=True
            # )

if save_nifti:
    fov_mm, slice_mm = read_geometry(header_text)
    offsets = read_slice_offsets(header_text)
    dz_mm, z0_mm = slice_axis(offsets, slice_mm, no_slices)

    stem = os.path.splitext(filename)[0]
    step = np.arange(no_expts) % max(diff['n'], 1)     # diffusion step for each volume
    bval = diff['b'][step] if diff['b'] is not None else None
    dac = diff['dac'][step] if diff['dac'] is not None else None
    bvec = diff['unit'][step]

    if b_mode == 0:
        descrip = "bmode=0 dac=" + ",".join(f"{d:g}" for d in dac)
    else:
        descrip = "bmode=1 b=" + ",".join(f"{b:g}" for b in bval)

    write_nifti(
        np.transpose(img_all, (1, 0, 2, 3)),           # x, y, slice, experiment
        stem + ".nii.gz",
        fov_mm,
        dz_mm,
        z0_mm,
        descrip,
    )

    # The NIfTI descrip field holds 80 characters, so the full table goes in a sidecar.
    sidecar = {
        "PEOrder": pe_order,
        "BValueInputMode": b_mode,
        "DiffusionOn": diff_on,
        "SmallDelta_ms": diff['delta'],
        "BigDelta_ms": diff['big_delta'],
        "SliceOffsets_mm": offsets.tolist(),
        "SliceSpacing_mm": dz_mm,
    }

    if b_mode == 0:
        sidecar["GradientDAC"] = dac.tolist()
    else:
        sidecar["bval_s_per_mm2"] = bval.tolist()

    with open(stem + ".json", "w") as fh:
        json.dump(sidecar, fh, indent=2)

    if diff_on and bval is not None:
        with open(stem + ".bval", "w") as fh:
            fh.write(" ".join(f"{b:g}" for b in bval) + "\n")
        with open(stem + ".bvec", "w") as fh:
            for axis in range(3):
                fh.write(" ".join(f"{c:.6f}" for c in bvec[:, axis]) + "\n")

if save_images_mode is False:
    plt.show()


# Plot the navigator echo-train envelope if applicable
if nav_on and nav_report and save_images_mode is False:
    fig, ax = plt.subplots(num="Navigator echo-train envelope")
    for exp_idx in range(no_expts):
        a, _, _ = nav_envelope(k_acq_all[:, :, nav_report_slice, exp_idx], etl)
        ax.plot(np.arange(1, etl + 1), a, marker="o", label=f"exp {exp_idx + 1}")
    ax.set_xlabel("echo index")
    ax.set_ylabel("relative amplitude")
    ax.axhline(1.0, color="0.7", lw=0.8)
    ax.legend()
    ax.set_title(f"Navigator envelope (slice {nav_report_slice + 1})")


# output the RX and TX gain values from the MRD header
rx_gain = re.findall(r":_ObserveReceiverGain\s+(-?\d+)", header_text)
tx_gain = re.findall(r":_ObserveTransmitGain\s+(-?\d+)", header_text)

print("rx_gain: ", rx_gain)
print("tx_gain: ", tx_gain)

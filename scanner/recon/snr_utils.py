"""SNR estimation for the magnitude images produced by the EPI and FSE recons.

Noise sigma comes from four corner squares, signal from a threshold mask.
"""

import numpy as np

# Magnitude background noise is Rayleigh, so the measured background standard
# deviation understates the true sigma by this factor.
RAYLEIGH_STD = np.sqrt(2.0 - np.pi / 2.0)


def corner_noise(img, width=16):
    """Noise sigma and a sanity flag from the four corners of a magnitude image."""
    w = int(width)
    corners = [img[:w, :w], img[:w, -w:], img[-w:, :w], img[-w:, -w:]]
    stds = np.array([c.std() for c in corners])
    pooled = np.concatenate([c.ravel() for c in corners])

    # Rayleigh noise has mean / std = 1.913. A large departure, or corners that
    # disagree with each other, means the corners hold something besides noise.
    suspect = stds.max() > 1.5 * stds.min() or not 1.6 < pooled.mean() / pooled.std() < 2.3
    return float(pooled.std() / RAYLEIGH_STD), bool(suspect)


def signal_mask(img, method="max_fraction", level=0.5):
    """Boolean signal mask. method is "max_fraction" (level of the peak) or "otsu"."""
    if method == "max_fraction":
        return img > level * img.max()

    if method == "otsu":
        counts, edges = np.histogram(img.ravel(), bins=256)
        centres = 0.5 * (edges[:-1] + edges[1:])
        w0 = np.cumsum(counts)
        w1 = counts.sum() - w0
        csum = np.cumsum(counts * centres)
        m0 = csum / np.maximum(w0, 1)
        m1 = (csum[-1] - csum) / np.maximum(w1, 1)
        return img > centres[int(np.argmax((w0 * w1 * (m0 - m1) ** 2)[:-1]))]

    raise ValueError(f"unknown mask method {method!r}")


def image_snr(img, noise_width=16, mask_method="max_fraction", mask_level=0.5):
    """SNR of one 2-D magnitude image."""
    img = np.asarray(img, dtype=float)
    sigma, suspect = corner_noise(img, noise_width)
    mask = signal_mask(img, mask_method, mask_level)
    signal = float(img[mask].mean()) if mask.any() else 0.0
    return {
        "snr": signal / sigma if sigma > 0 else np.inf,
        "signal_mean": signal,
        "noise_sigma": sigma,
        "n_signal_px": int(mask.sum()),
        "corners_suspect": suspect,
    }


def print_snr(vol, labels=None, **kwargs):
    """Print one SNR line per 2-D image in a stack shaped (rows, cols, ...)."""
    vol = np.asarray(vol, dtype=float)
    flat = vol.reshape(vol.shape[0], vol.shape[1], -1)

    print("=== SNR ===")
    results = []
    for i in range(flat.shape[2]):
        r = image_snr(flat[:, :, i], **kwargs)
        results.append(r)
        label = labels[i] if labels is not None else f"image {i + 1}"
        warn = "  [check corners]" if r["corners_suspect"] else ""
        print(
            f"{label}: SNR {r['snr']:7.1f}   signal {r['signal_mean']:.3g}"
            f"   sigma {r['noise_sigma']:.3g}   {r['n_signal_px']} px{warn}"
        )
    return results

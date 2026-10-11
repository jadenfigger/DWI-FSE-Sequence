"""1D readout-projection phase correction for appended per-shot echoes."""
import numpy as np


def readout_projection(k):
    return np.fft.fftshift(np.fft.ifft(np.fft.ifftshift(k, axes=-1), axis=-1), axes=-1)


def projection_kspace(p):
    return np.fft.fftshift(np.fft.fft(np.fft.ifftshift(p, axes=-1), axis=-1), axes=-1)


def split_mode2(k_acq, etl, imaging_views):
    """Leading ETL+1 volume train, then ETL+1 rows per imaging shot.

    Embedded NO_VIEWS is the raw count; VIEWS_PER_SEGMENT remains imaging
    ETL. nav_on=2 selects this contract. MRD views=(ETL+1)*(1+imaging_views/ETL).
    Each final row is unencoded; the leading appended row is discarded.
    """
    if etl < 1 or imaging_views <= 0 or imaging_views % etl:
        raise ValueError("nav_on=2 requires positive imaging views divisible by ETL")
    expected = (etl + 1) * (1 + imaging_views // etl)
    if len(k_acq) != expected:
        raise ValueError(f"nav_on=2 raw layout mismatch: MRD has {len(k_acq)} views; embedded protocol requires {expected}")
    blocks = k_acq[etl + 1:].reshape(-1, etl + 1, k_acq.shape[1])
    return k_acq[:etl], blocks[:, :etl].reshape(imaging_views, -1), blocks[:, etl]


def correct_shot_phase(k_img, navigators, etl, mode="constant+linear",
                       min_snr=3., min_coherence=.65):
    """Magnitude-weighted unwrap/fit, conjugate correction in hybrid x-ky.

    The strongest navigator is the reference. Noise is estimated from outer
    readout projection pixels, so no high-b assumption or adjacent PPR is used.
    Rejected shots remain untouched. Slope is radians per readout voxel; the
    intercept is at readout coordinate (n-1)/2. A shared absolute phase is
    unobservable and intentionally retained.
    """
    if mode not in ("off", "constant", "constant+linear"):
        raise ValueError(f"unsupported per-shot phase mode {mode!r}")
    if len(k_img) != len(navigators) * etl:
        raise ValueError("one navigator is required for every imaging shot")
    p = readout_projection(navigators)
    n = p.shape[1]
    x = np.arange(n) - (n - 1) / 2
    edge = max(4, n // 8)
    # Median(|complex Gaussian|^2)/ln2 estimates E|noise|^2.
    noise_power = np.median(np.abs(np.concatenate([p[:, :edge], p[:, -edge:]], axis=1))**2, axis=1) / np.log(2)
    peak_power = np.percentile(np.abs(p)**2, 90, axis=1)
    snr = np.sqrt(np.maximum(peak_power - noise_power, 0) / np.maximum(noise_power, np.finfo(float).tiny))
    reference = int(np.argmax(snr))
    reference_mask = np.abs(p[reference]) > .15 * np.max(np.abs(p[reference]))
    estimates = []
    corrected = k_img.copy()
    for shot in range(len(p)):
        mask = reference_mask & (np.abs(p[shot]) > .15 * np.max(np.abs(p[shot])))
        intercept, slope, coherence, applied = 0., 0., 0., False
        reason = "mode-off" if mode == "off" else "noise-dominated"
        if mode != "off" and snr[shot] >= min_snr and snr[reference] >= min_snr and mask.sum() >= 8:
            ratio = p[shot, mask] * np.conj(p[reference, mask])
            weights = np.abs(ratio)
            phase = np.unwrap(np.angle(ratio))
            if mode == "constant":
                intercept = float(np.angle(np.sum(ratio)))
            else:
                design = np.stack([np.ones(mask.sum()), x[mask]], axis=1)
                intercept, slope = np.linalg.lstsq(design * np.sqrt(weights[:, None]), phase * np.sqrt(weights), rcond=None)[0]
            residual = phase - intercept - slope * x[mask]
            coherence = float(np.abs(np.sum(weights * np.exp(1j * residual))) / np.sum(weights))
            applied = coherence >= min_coherence
            reason = "applied" if applied else "incoherent"
            if applied:
                start = shot * etl
                hybrid = readout_projection(k_img[start:start + etl])
                corrected[start:start + etl] = projection_kspace(hybrid * np.exp(-1j * (intercept + slope * x)))
        estimates.append(dict(shot=shot, constant_rad=float(intercept), linear_rad_per_voxel=float(slope),
                              navigator_snr=float(snr[shot]), coherence=coherence,
                              applied=bool(applied), disposition=reason))
    return corrected, dict(Mode=mode, ReferenceShot=reference, MinimumSNR=min_snr,
                           MinimumCoherence=min_coherence, Estimates=estimates,
                           Units="constant_rad; linear_rad_per_voxel at x-(samples-1)/2")

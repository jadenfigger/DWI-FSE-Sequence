"""
rf_pulses.py - RF shapes for the MR Solutions sinc frames used by the PPL, plus
Bloch slice profiles.

The vendor RF library (c:\\smis\\seqlib\\RFstd44.seq) is not available, so the
frames are rebuilt from their names. Every sinc frame in the NEWSHAPE table
(PPL:598-616) satisfies  bandwidth x duration = lobes + 1:
    3lobe_sinc_3kHz   1332 us x 3000 Hz  = 4
    5lobe_sinc_3kHz   2000 us x 3000 Hz  = 6
    9lobe_sinc_5kHz   2000 us x 5000 Hz  = 10
    19lobe_sinc_2ms   2000 us x 10000 Hz = 20
i.e. a sinc with zero crossings every t0 = 1/BW, truncated after N lobes
(central lobe + (N-1)/2 side lobes each side).

Models
  'truncated_sinc'  (default) exactly that. Its excitation FWHM is about the
                    nominal BW (3 kHz), so with the PPL's slice gradient (set for
                    71 % of it, 2130 Hz) the slice is ~1.4x the nominal thickness.
  'bw_matched_sinc' sinc stretched so its zero-crossing BW equals the PPL's
                    slice bandwidth (bw_override 71 %, PPL:1327-1333; the manual's
                    GEDEM_MC example lists this frame as 2140 Hz). Same duration,
                    so it is truncated inside the first side lobes; the slice is
                    the nominal thickness.
  apodization a:    window (1-a) + a*cos(2 pi t/T); 0.5 = Hanning, 0.46 = Hamming.

    python rf_pulses.py            # writes rf/<frame>_<model>.txt and rf/rf_pulses.png
"""
import os
import re

import numpy as np

# NEWSHAPE_MAC table (PPL:598-618): rfnum -> (frame, duration us, bandwidth Hz)
RF_TABLE = {
    1: ('3lobe_sinc_3kHz', 1332, 3000), 2: ('3lobe_sinc_1500Hz', 2664, 1500),
    3: ('3lobe_sinc_750Hz', 5328, 750), 4: ('5lobe_sinc_3kHz', 2000, 3000),
    5: ('5lobe_sinc_1500Hz', 4000, 1500), 6: ('5lobe_sinc_750Hz', 8000, 750),
    7: ('3lobe_sinc_6kHz', 666, 6000), 8: ('3lobe_sinc_4kHz', 1000, 4000),
    9: ('hypsec_1500Hz', 10000, 1500), 10: ('hypsec_1875Hz', 8000, 1875),
    11: ('hypsec_3000Hz', 5000, 3000), 12: ('hypsec_3750Hz', 4000, 3750),
    13: ('hypsec_7500Hz', 2000, 7500), 14: ('gauss', 7000, 180),
    15: ('9lobe_sinc_5kHz', 2000, 5000), 16: ('19lobe_sinc_2ms', 2000, 10000),
    17: ('gauss', 20000, 10),
}
MODELS = ('truncated_sinc', 'bw_matched_sinc')


def n_lobes(frame):
    m = re.match(r'(\d+)lobe_sinc', frame)
    if not m:
        raise ValueError(f'{frame} is not a sinc frame; supply a shape file')
    return int(m.group(1))


def sinc_frame(rfnum, n, model='truncated_sinc', apodization=0.0, bw_fraction=0.71):
    """Real amplitude samples (peak 1) at n points across the frame duration (sample centres)."""
    frame, dur_us, bw = RF_TABLE[rfnum]
    nl = n_lobes(frame)
    t = (np.arange(n) + 0.5) / n - 0.5                    # -0.5 .. 0.5 of the duration
    tbw = (nl + 1) if model == 'truncated_sinc' else (nl + 1) * bw_fraction
    if model not in MODELS:
        raise ValueError(f'model must be one of {MODELS}')
    w = np.sinc(tbw * t) * ((1 - apodization) + apodization * np.cos(2 * np.pi * t))
    return w / np.abs(w).max()


def rotate(m, b1x, b1y, bz, dt):
    """Left-handed rotation of M (3,N) about B = (b1x, b1y, bz) [Hz] for dt [s]."""
    bn = np.sqrt(b1x ** 2 + b1y ** 2 + bz ** 2)
    th = -2 * np.pi * bn * dt
    k = np.vstack([np.full_like(bz, b1x) / bn, np.full_like(bz, b1y) / bn, bz / bn])
    c, s = np.cos(th), np.sin(th)
    kd = (k * m).sum(0)
    return m * c + np.cross(k.T, m.T).T * s + k * kd * (1 - c)


def profiles(w, dur_s, freqs, flip_deg_exc=90.0, flip_deg_ref=180.0):
    """Excitation |Mxy| (with ideal rephasing) and refocusing efficiency (1-Mz)/2 vs frequency offset."""
    dt = dur_s / len(w)
    out = []
    for flip in (flip_deg_exc, flip_deg_ref):
        amp = np.deg2rad(flip) / (2 * np.pi * w.sum() * dt)      # Hz per unit of w
        m = np.vstack([np.zeros_like(freqs), np.zeros_like(freqs), np.ones_like(freqs)])
        for wk in w:
            m = rotate(m, amp * wk, 0.0, freqs, dt)
        out.append(m)
    me, mr = out
    t_mid = dur_s / 2                                             # undo the linear phase of a centred pulse
    mxy = np.abs((me[0] + 1j * me[1]) * np.exp(1j * 2 * np.pi * freqs * t_mid))
    return mxy, (1 - mr[2]) / 2


def fwhm(x, y):
    m = y >= y.max() / 2
    return x[m].max() - x[m].min()


def profile_summary(rfnum, model='truncated_sinc', apodization=0.0, flip_ref=180.0, bw_fraction=0.71):
    frame, dur_us, bw = RF_TABLE[rfnum]
    w = sinc_frame(rfnum, dur_us, model, apodization, bw_fraction)
    f = np.linspace(-2.5 * bw, 2.5 * bw, 2001)
    exc, ref = profiles(w, dur_us * 1e-6, f, 90.0, flip_ref)
    return dict(freq=f, exc=exc, ref=ref, se=exc * ref, fwhm_exc=fwhm(f, exc), fwhm_ref=fwhm(f, ref),
                fwhm_se=fwhm(f, exc * ref), shape=w)


if __name__ == '__main__':
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, 'rf')
    os.makedirs(out, exist_ok=True)
    fig, ax = plt.subplots(1, 2, figsize=(12, 4))
    slice_bw = 0.71 * 3000
    for model, apo, c in (('truncated_sinc', 0.0, 'C0'), ('truncated_sinc', 0.5, 'C1'), ('bw_matched_sinc', 0.0, 'C2')):
        s = profile_summary(1, model, apo)
        lab = f'{model}{" Hanning" if apo else ""}'
        np.savetxt(os.path.join(out, f'3lobe_sinc_3kHz_{lab.replace(" ", "_")}.txt'), s['shape'], fmt='%.6f')
        t = (np.arange(1332) + 0.5)
        ax[0].plot(t, s['shape'], color=c, label=lab)
        ax[1].plot(s['freq'] / slice_bw, s['exc'], color=c, label=f'{lab}: 90 FWHM {s["fwhm_exc"]/slice_bw:.2f} mm')
        ax[1].plot(s['freq'] / slice_bw, s['ref'], '--', color=c, label=f'{lab}: 180 FWHM {s["fwhm_ref"]/slice_bw:.2f} mm')
        print(f'{lab:28s} FWHM exc {s["fwhm_exc"]:6.0f} Hz ({s["fwhm_exc"]/slice_bw:.2f} mm)  ref {s["fwhm_ref"]:6.0f} Hz '
              f'({s["fwhm_ref"]/slice_bw:.2f} mm)  spin-echo {s["fwhm_se"]:6.0f} Hz ({s["fwhm_se"]/slice_bw:.2f} mm)')
    ax[0].set_xlabel('time [us]')
    ax[0].set_title('3lobe_sinc_3kHz (1332 us) models')
    ax[0].legend(fontsize=8)
    ax[1].axvspan(-0.5, 0.5, color='0.9', zorder=0)
    ax[1].set_xlim(-1.5, 1.5)
    ax[1].set_xlabel('position [mm] at the PPL slice gradient (2130 Hz/mm for 1 mm)')
    ax[1].set_title('Bloch profiles: 90 |Mxy| (solid), 180 refocusing (dashed)')
    ax[1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(out, 'rf_pulses.png'), dpi=110)
    print('wrote', out)

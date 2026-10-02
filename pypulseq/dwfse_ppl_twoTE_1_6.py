"""
PyPulseq re-implementation of ONE variant of FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppl:
diffusion-weighted fast spin echo, ETL > 1, b > 0, as configured by
FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppr.

Purpose: simulation (MRzero / KomaMRI). The waveforms reproduce the scanner's
commanded gradient amplitudes, crusher sizes/polarities, RF phases and timings.
Nothing is rebalanced or idealised. Citations:
    PPL:n  -> line n of FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppl
    PPR:n  -> line n of FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppr
    var/m3040/m3031/offst -> the .pph include files
    MAN    -> EVO Pulse Sequence Program Manual.pdf

All PPL arithmetic is replayed with 16/32-bit-style integer division that
truncates toward zero (PPL '/', scale() = (a*b)/c, MAN 4.8.12.1).

Time unit inside the builder: integer microseconds. Gradient unit: PPL DAC
(logical axis), converted to Hz/m only when the Pulseq events are made.
Logical axes -> Pulseq axes: read -> x, phase -> y, slice -> z (PPL:2160-2162
names acq_x/acq_y/acq_z as read/phase/slice).

Usage:
    python dwfse_ppl_twoTE_1_6.py            # full protocol  -> dwfse_full.seq
    python dwfse_ppl_twoTE_1_6.py --reduced  # simulation cut -> dwfse_reduced.seq
"""

import argparse
import math
import warnings
from types import SimpleNamespace

import numpy as np
import pypulseq as pp

# =============================================================================
# 0. USER SWITCHES  (every item here is an OPEN QUESTION or a sim-only choice)
# =============================================================================

# Gradient-vs-RF/ADC alignment. 0 = literal commanded timing from the PPL code.
# The PPL delays every RF pulse and the ADC by rfdelay (=60 us) relative to the
# commanded gradient plateau (PPL:3425, 3443-3448, 3726) to compensate a
# hardware gradient delay ("rf delay added to compensate for gradient group
# delay", PPL:4100). Set to RFDELAY_US (60) to model that hardware delay
# (all gradients shifted +60 us). OPEN QUESTION - see README.
GRAD_DELAY_US = 0

# Refocusing flip angle. None -> linear amplifier assumption:
#   flip = 90 deg * p180_mul / p90_mul = 90*1098/594 = 166.36 deg (PPL:2347-2352).
# Set to 180.0 if p180_scale=185 % is a calibration for amplifier compression.
# OPEN QUESTION.
REFOCUS_FLIP_DEG = None

# RF shape for rfnum=1 "3lobe_sinc_3kHz" (PPL:598, frame in c:\smis\seqlib\RFstd44.seq).
# None -> PLACEHOLDER: un-apodised sinc, duration 1332 us, time-bandwidth 4
# (3 lobes; 3000 Hz * 1.332 ms = 3.996). Give a path to a text file with one
# real amplitude per line (any number of points; resampled to 1 us) to replace it.
RF_SHAPE_FILE = None

# acqpad(sample_period=500) in 100 ns ticks (PPL:623, 644). Needed ONLY for the
# per-echo phase correction of OFF-CENTRE slices (PPL:2795-2813, 3735-3754).
# None -> correction not applied (warned + written to [DEFINITIONS]).
# The centre slice (offset 0 Hz) is exact without it.
ACQPAD_TICKS = None

# Reduced-simulation cut (--reduced). Timing inside every TR is unchanged.
REDUCED_SLICE_POS_INDEX = 1   # pos_index 1 = centre slice (fov_slice_off 0, PPR:54-55)
REDUCED_ACQ_ROWS = [1]        # acquisition-table row 1 = b 6000 s/mm^2, dir (1,0,0)
REDUCED_SHOTS = [1]           # shot 0 = navigator train; 1..4 = imaging shots
REDUCED_N_DUMMY = 0           # PPR no_disacq=4; 0 here to keep the sim short
REDUCED_KEEP_SLICE_SLOTS = True  # keep the other slices' time slots as dead time

# =============================================================================
# 1. PPR VALUES  (PPR line numbers)
# =============================================================================
PPR = SimpleNamespace(
    sample_period=500,      # PPR:4   (100 ns units -> 50 us dwell, 20 kHz)
    grad_var=[25447, 25447, 25910, 25925],  # PPR:5 (Hz/mm; [0] = isotropic full scale)
    no_samples=128,         # PPR:6
    no_views=160,           # PPR:7   (includes 32 navigator views)
    views_per_seg=32,       # PPR:8   ETL
    no_views_2=1,           # PPR:9   (2D)
    oversample=0, oversample2=0, oversample3=0,  # PPR:10-12
    nav_on=1,               # PPR:13
    no_discard=0,           # PPR:14
    no_experiments=2,       # PPR:15
    no_averages=1,          # PPR:16
    view_block=1,           # PPR:17
    slice_block=1,          # PPR:18
    phase_cycle=1,          # PPR:19
    gs_var=-1377,           # PPR:24  (slice thickness 1 mm)
    no_slices=3,            # PPR:26
    batch_slices=0,         # PPR:27  (0 -> = no_slices, PPL:1338)
    batch_interleave=1, slice_interleave=1,  # PPR:28-29
    gr_var=-735,            # PPR:34
    gp_init_var=-1177,      # PPR:35
    fov_mm=35,              # PPR:36
    phase_var=0,            # PPR:49
    fov_read_off=[0, 0, 0],       # PPR:50-51
    fov_phase_off=[0, 0, 0],      # PPR:52-53
    fov_slice_off=[-480, 0, 480], # PPR:54-55 (FOV_OFFSETS -1.2, 0, 1.2 mm PPR:56-59)
    FOVf=8,                 # PPR:60
    slab_ratio=100,         # PPR:61
    rfnum=1,                # PPR:62
    rfcal=594,              # PPR:64
    alpha=90,               # PPR:65
    p180_scale=185,         # PPR:66
    tr=2000,                # PPR:67  ms
    esp=16,                 # PPR:68  ms
    te=54,                  # PPR:69  ms
    PF_echoes=0,            # PPR:70
    tramp=200,              # PPR:72  us
    tref_setup=700,         # PPR:73  us
    tcrush=1000,            # PPR:74  us
    diff_tcrush=1000,       # PPR:75  us
    crush_independent_on=1, # PPR:76
    crush_amp=5482,         # PPR:77  DAC
    diff_crush_amp=2754,    # PPR:78  DAC
    gsp_lobe=0,             # PPR:79  %
    gs_comp_scale=0,        # PPR:80
    grp_lobe=110,           # PPR:81  %
    gr_comp_scale=2,        # PPR:82
    slice_mm_10=0,          # PPR:83
    sat_on=0,               # PPR:84
    gs_on=1, gr_on=1, gp_on=1, gp_sl_on=1,   # PPR:101-104
    PE_order=1,             # PPR:105
    pe2_centric_on=0,       # PPR:106
    flow_comp_on=0,         # PPR:108
    phcor_plus=23, phcor_minus=23, r_phcor=0,  # PPR:109-111
    echoes_to_discard=0,    # PPR:112
    de_on=0,                # PPR:113
    gating=0,               # PPR:114
    slice_clustering_on=0,  # PPR:115
    interslice_delay=0,     # PPR:119
    chess_on=0,             # PPR:121
    mtc_on=0,               # PPR:129
    diff_on=1,              # PPR:268
    b_input_mode=1,         # PPR:269
    sm_delta=4000,          # PPR:270 us
    big_delta=40000,        # PPR:271 us
    no_diff_acq=2,          # PPR:272
    acq_b=[0, 6000],        # PPR:273-274
    acq_grad_ppr=[1, 20119],  # PPR:338-339 (overwritten by the b-mode search, PPL:757-763)
    acq_x=[1000, 1000],     # PPR:403-404
    acq_y=[0, 0],           # PPR:468-469
    acq_z=[0, 0],           # PPR:533-534
    diff_tramp=200,         # PPR:598
    diff_grad_scale=100,    # PPR:599
    rfdelay=60,             # PPR:600
    rfgate_delay=23,        # PPR:601
    post_90_delay1=0,       # PPR:602
    phcor0=0,               # PPR:603
    post_crush_on=1,        # PPR:604
    post_tcrush=3000,       # PPR:605
    post_crush_amp=-6000,   # PPR:606
    no_disacq=4,            # PPR:607
    dixon_on=0,             # PPR:608
    TR_array_size=0,        # PPR:621
    rec_freq=0,             # PPR:3
)

# Include-file constants
DACMAX = 32767            # var_20.pph:96, 101; CREATE_MATRIX divisor (m3040_15.pph:274)
PHASE_RES = 225           # var_20.pph:108 (0.225 deg per phase unit)
RF_LENGTH = {1: 1332}     # PPL:598 NEWSHAPE_MAC(1, pf1, "3lobe_sinc_3kHz", 1332, 3000)
RF_BWDTH = {1: 3000}      # PPL:598


# =============================================================================
# 2. PPL INTEGER ARITHMETIC
# =============================================================================
def tdiv(a, b):
    """PPL integer '/' : truncation toward zero (assumed; FloorDiv exists separately in stdfn_15.pph)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def tmod(a, b):
    """PPL '%' consistent with truncating division."""
    return a - b * tdiv(a, b)


def scale(a, b, c):
    """MAN 4.8.12.1: scale(e1,e2,e3) = (e1*e2)/e3, 32-bit product."""
    return tdiv(a * b, c)


def derive(P):
    """Replay the PPL set-up arithmetic for this PPR. Returns a namespace D."""
    D = SimpleNamespace()
    D.G0 = P.grad_var[0]  # Hz/mm at DAC = DACMAX

    # ---- views / ordering (PPL:803-1121) -----------------------------------
    assert P.diff_on == 1
    D.te_eff = 1                                           # PPL:815
    D.no_views_eff = P.no_views - P.views_per_seg * (P.nav_on == 1)  # PPL:854-855
    PF = P.PF_echoes if P.PF_echoes else P.views_per_seg  # PPL:867
    D.views_per_echo = tdiv(D.no_views_eff, 2 * P.views_per_seg)  # PPL:878
    D.view_shift = (PF - P.views_per_seg) * D.views_per_echo       # PPL:879
    assert D.no_views_eff % (2 * P.views_per_seg) == 0           # PPL:951
    gp_order = []
    if P.nav_on:                                           # PPL:918-926
        gp_order += [0] * P.views_per_seg
    assert P.PE_order == 1
    # PE_order_1 (egen), PPL:1058-1088
    shot = 1
    gp_loc = tdiv(D.no_views_eff, 2) - D.views_per_echo - 1
    while shot < D.views_per_echo * 2 + 1:
        gp_loc += 1
        for echo in range(1, P.views_per_seg + 1):
            if shot > D.views_per_echo:
                gp_mul = gp_loc + D.views_per_echo * (echo - D.te_eff)
            else:
                gp_mul = gp_loc - D.views_per_echo * (echo - D.te_eff)
            gp_order.append(gp_mul - tdiv(D.no_views_eff, 2))
        shot += 1
    assert len(gp_order) == P.no_views
    D.gp_order = gp_order
    D.n_shots = P.no_views // P.views_per_seg   # incl. navigator shot

    # ---- 3D slice PE table (PPL:1211-1221): no_views_2 = 1 -> [0] ----------
    D.gp_var_mul2 = [tdiv(-P.no_views_2, 2)]   # = 0

    # ---- timing basics -----------------------------------------------------
    D.deg_90 = scale(90, 1000, PHASE_RES)      # PPL:1255 -> 400
    D.deg_360 = scale(360, 1000, PHASE_RES)    # PPL:1256 -> 1600
    D.tacq = (P.sample_period * (P.no_samples + P.no_discard)) // 10  # PPL:1258 -> 6400 us
    D.tacq_2 = D.tacq // 2                     # PPL:1259
    D.tsel90 = RF_LENGTH[P.rfnum]              # PPL:1270
    D.tsel180 = D.tsel90                       # PPL:1271
    # independent crushers (PPL:1276-1318)
    assert P.crush_independent_on == 1
    tmp = P.tramp // 10
    D.crush_rf_flat = ((D.tsel90 + 2 * P.rfdelay + tmp - 1) // tmp) * tmp   # PPL:1313
    if D.crush_rf_flat % 2 != 0:
        D.crush_rf_flat += tmp                 # PPL:1314
    D.crush_rf_pad = D.crush_rf_flat - D.tsel90                       # PPL:1315
    D.crush_pre_pad = 2 * P.tramp + D.crush_rf_pad // 2 - P.rfdelay  # PPL:1316
    D.crush_post_pad = 2 * P.tramp + D.crush_rf_pad // 2 + P.rfdelay  # PPL:1317
    assert (P.tcrush * 50) % P.tramp == 0 and (P.diff_tcrush * 50) % P.tramp == 0  # PPL:1297,1302
    D.tcrush_play = P.tcrush + D.crush_pre_pad                        # PPL:1319
    D.tcrush1_play = P.diff_tcrush + D.crush_pre_pad                  # PPL:1321
    D.first_crush_flat = P.diff_tcrush                                # PPL:1756-1762
    D.bw_override = 71 if P.no_views_2 == 1 else 100                  # PPL:1327-1331
    D.pulse_bwdth = tdiv(D.bw_override * RF_BWDTH[P.rfnum], 100)      # PPL:1332-1333 -> 2130 Hz
    D.tref = 4 * P.tref_setup                  # PPL:1356 -> 2800 us
    D.tdp = P.tref_setup                       # PPL:1357 -> 700 us
    D.gr_oversample = 3 + P.oversample         # PPL:1358
    D.gr_undersample = 3 - P.oversample        # PPL:1359
    D.gp_oversample = 3 + P.oversample2        # PPL:1360
    D.gp_undersample = 3 - P.oversample2       # PPL:1361
    assert P.FOVf == 8
    D.clock = P.tramp // 5                     # PPL:1714 (100 ns units: 4 us/point, 50 points/ramp)

    # ---- phase encode increment (PPL:1393-1404) ----------------------------
    t1 = tdiv(P.gp_init_var * D.gp_undersample * 2500, D.gp_oversample)
    t1 = tdiv(t1, D.tdp + P.tramp)
    D.gp_inc = scale(t1, 2, P.no_views)        # -> -40

    # ---- slice select amplitude (PPL:1437-1448) ----------------------------
    gs_var1 = P.gs_var
    D.gs_var_rescale = tdiv(gs_var1 * D.pulse_bwdth, 1070)   # -> -2741

    # ---- read dephase (PPL:1454-1465) --------------------------------------
    t1 = tdiv(D.tacq + P.tramp, 2)
    t1 = t1 * P.gr_var
    t1 = tdiv(t1, D.tdp + P.tramp)
    D.gr_comp = tdiv(t1 * D.gr_undersample, D.gr_oversample)  # -> -2695

    # ---- slice refocus (PPL:1487-1496) -------------------------------------
    t1 = tdiv(D.tsel90 + P.tramp, 2)
    t2 = D.tref + P.tramp
    D.gs_comp = tdiv(D.gs_var_rescale * t1, t2)              # -> -699

    # ---- real-time adjustments (PPL:2976-3013) -----------------------------
    t1 = D.gs_comp
    t1 = t1 + tdiv(t1 * (P.gs_comp_scale + 0), 1000)          # fse_gs_comp = 0 (PPL:519)
    t2 = tdiv(t1 * P.gsp_lobe, 100)
    t3 = t1 - t2
    D.gs_rp = t3                                              # PPL:2984 -> -699
    D.gsp_rp = tdiv(t2 * (D.tref + P.tramp), D.tdp + P.tramp)  # PPL:2985 -> 0
    t1 = D.gr_comp
    t1 = t1 + tdiv(tdiv(t1 * P.gr_comp_scale, 8), 1000)       # PPL:3004
    t2 = tdiv(t1 * P.grp_lobe, 100)                           # PPL:3006
    t3 = t1 - t2
    D.gr_dp = t3                                              # PPL:3012 -> 269
    D.grp_dp = -tdiv(t2 * (D.tdp + P.tramp), D.tref + P.tramp)  # PPL:3013 -> 889
    assert P.flow_comp_on == 0
    D.G1 = D.grp_dp                                           # PPL:3063
    D.G2 = 0                                                  # PPL:3015, 3064
    D.read_amp = (P.gr_on * D.gr_undersample) * tdiv(P.gr_var, D.gr_oversample)  # PPL:3688 -> -735

    # ---- b-value -> DAC search (PPL:575-585, 685-780) -----------------------
    sm, bd = P.sm_delta, P.big_delta
    b_kfac = 0
    if 0 < sm <= 10000 and bd > sm and bd <= 80000:
        a = (sm * sm + 500) // 1000
        b = bd - sm // 3
        a = a * ((b + 50) // 100)
        a = (a + 500) // 1000
        a = (a * 63) // 10
        a = (a * 63) // 10
        b_kfac = (a + 50) // 100
    D.b_kfac = b_kfac

    def b_of_dac(d):
        g = (d * D.G0) // 32767                 # PPL:740 (positive operands)
        return (((g * g + 5000) // 10000) * b_kfac + 5000) // 10000

    D.b_of_dac = b_of_dac
    max_diff_grad = 30000                       # PPL:710
    acq_grad = list(P.acq_grad_ppr)
    D.acq_b_achieved_ppl = []
    for i in range(P.no_diff_acq):
        target = P.acq_b[i]
        lo, hi = 1, max_diff_grad
        for _ in range(20):
            mid = lo + (hi - lo + 1) // 2
            if b_of_dac(mid) <= target:
                lo = mid
            else:
                hi = mid - 1
            if lo >= hi:
                break
        dac = scale(lo, 100, P.diff_grad_scale)
        if P.b_input_mode == 1:
            acq_grad[i] = 1 if target <= 0 else dac   # PPL:757-763
        D.acq_b_achieved_ppl.append(b_of_dac(scale(dac, P.diff_grad_scale, 100)))
    D.acq_grad = acq_grad
    D.diff_grad = [scale(g, P.diff_grad_scale, 100) for g in acq_grad]  # PPL:2106
    # PPL:2160-2162 ; diffusion matrix negates all three (PPL:3094)
    D.diff_rps = [(P.diff_on * scale(g, P.acq_x[i], 1000),
                   P.diff_on * scale(g, P.acq_y[i], 1000),
                   P.diff_on * scale(g, P.acq_z[i], 1000)) for i, g in enumerate(D.diff_grad)]

    # ---- TE / big-delta arithmetic (PPL:2365-2567, 2629-2771) ---------------
    tcrush1 = P.diff_tcrush                      # PPL:2176-2177
    D.tcrush1 = tcrush1
    sm_us, bd_us = P.sm_delta, P.big_delta
    min_pre = (D.tsel90 // 2 + 4 * P.tramp + 1000 + D.tsel180 // 2 + tcrush1 + 20)
    min_pre += D.crush_pre_pad + P.diff_on * (sm_us + P.diff_tramp)
    min_post = (D.tsel180 // 2 + 3 * P.tramp + 500 + tcrush1) + (D.tacq * 100) // 200 + 30 + 1 + 35
    min_post += D.crush_post_pad + P.diff_on * (sm_us + P.diff_tramp)
    half_te = P.te * 500
    space_pre, space_post = half_te - min_pre, half_te - min_post
    assert space_pre > 0 and space_post > 0, 'TE too short (PPL:2423)'
    big_delta_min = sm_us + (P.diff_tramp + D.tsel180 + 2 * (P.tramp + tcrush1)
                             + D.crush_pre_pad + D.crush_post_pad)  # PPL:2440
    assert big_delta_min <= bd_us <= big_delta_min + space_pre + space_post
    D.extra_delta = P.diff_on * (bd_us - sm_us - (P.diff_tramp + D.tsel180 + 2 * P.tramp
                                                  + 2 * tcrush1 + D.crush_pre_pad + D.crush_post_pad))  # PPL:2485
    assert D.extra_delta // 2 <= space_pre and D.extra_delta // 2 <= space_post   # PPL:2496 (branch 1)
    D.extra_delta_ticks = D.extra_delta * 5     # PPL:2563-2567 (100 ns ticks, each side)
    assert D.extra_delta_ticks % 10 == 0, 'odd extra_delta: half-us delay, needs 0.1 us raster'
    D.extra_delta_side_us = D.extra_delta_ticks // 10
    D.min_te = max(min_pre, min_post) * 2 + D.extra_delta + 1000   # PPL:2415-2418, 2647
    assert P.te * 1000 >= D.min_te                                  # PPL:2688
    D.te_a = D.tsel90 + P.tcrush + D.tref + 4 * P.tramp + D.crush_pre_pad   # PPL:2629
    D.te_b = D.tsel90 // 2 + P.tcrush + D.tdp + 4 * P.tramp + D.tacq_2 + D.crush_post_pad  # PPL:2632
    D.te_balance_al = half_te - D.te_a           # PPL:2708
    D.te_balance_bl = half_te - D.te_b           # PPL:2707
    D.te_balance_bl_esp = P.esp * 500 - D.te_b   # PPL:2762
    assert P.esp * 500 - (D.te_b + 21) >= 0      # PPL:2766

    # ---- min TR / slice period (PPL:2822-2946) ------------------------------
    t1 = P.te * 1000 + (P.views_per_seg - 1 + P.echoes_to_discard) * P.esp * 1000
    t1 += P.tramp + D.tsel90 // 2
    t1 += 3 * P.tramp + P.tref_setup + D.tacq_2 + 26
    t1 += 10200 + 70 + 69
    t3 = (2 * P.tramp + P.post_tcrush + 240) if P.post_crush_on else 0
    D.tr_min_us = t1 + 0 + t3                    # no CHESS / presat / MTC
    batch = P.batch_slices or P.no_slices
    D.batch_slices = batch
    D.slice_period_us = (P.tr * 1000) // batch   # PPL:2929 (tr_extend = this - tr_min)
    D.tr_extend_us = D.slice_period_us - D.tr_min_us
    assert D.tr_extend_us >= 0

    # ---- RF amplitudes / phases (PPL:2295-2296, 2347-2352) ------------------
    D.p90_mul = min(scale(P.rfcal, P.alpha, 90), 2047)
    D.p180_mul = min(scale(P.rfcal, P.p180_scale, 100), 2047)
    # aqphase(no_acq=0, phase_cycle) = 0 : no_acq = view_av + image_av = 0 for every
    # train here (PPL:2232; averages=1, view_block=1) and the first phase of any cycle is 0.
    D.phase_90 = 0 * D.deg_90
    D.phase_180 = D.phase_90 + 3 * D.deg_90      # 1200 units = 270 deg

    # ---- slice frequencies (PPL:2253-2265) ---------------------------------
    scale_slice_off = 400                        # PPL:1382
    D.slice_freq = [tdiv(o * D.pulse_bwdth, scale_slice_off) + 0 for o in P.fov_slice_off]
    D.read_freq = [0 for _ in P.fov_read_off]    # READOFF of 0 offset (offst_20.pph:25-37)

    # ---- per-echo phase correction for off-centre slices (PPL:2795-2813) ----
    def phase_corr_table(pos):
        n = P.views_per_seg
        t_1 = D.slice_freq[pos]
        t_2 = -D.read_freq[pos] - P.rec_freq
        if t_1 == 0 and t_2 == 0:
            return [0] * (n + 1), True
        if ACQPAD_TICKS is None:
            return [0] * (n + 1), False
        group_delay = ACQPAD_TICKS
        extra_val = 51 if P.sample_period > 19 else None   # PPL:629
        overhead = ((group_delay + 16 + extra_val) * 16) // 100  # PPL:640-643
        phcor = P.phcor_plus if t_1 > 0 else P.phcor_minus
        t3_ = overhead + tdiv((D.tacq + P.tramp) * 16, 10)
        t4_ = (t_1 + t_2) * t3_
        t5_ = tdiv(16 * (phcor * t_1 + P.r_phcor * t_2), 10)
        t4_ = t4_ + t5_
        t5_ = tdiv(t4_, 1000)
        phase_ang = tmod(t5_, D.deg_360)
        rem = t4_ - t5_ * 1000
        out = [0]
        for k in range(1, n + 1):          # PPL:3735-3754, templ2 = total_echo_cnt
            c0 = tmod(phase_ang * k, D.deg_360)
            t5k = k * rem
            c1 = tdiv(t5k, 1000)
            r = tmod(t5k, 1000)
            c2 = 1 if r > 500 else (-1 if r < -500 else 0)
            out.append(tmod(c0 + c1 + c2, D.deg_360))
        return out, True

    D.phase_corr_table = phase_corr_table
    return D


# =============================================================================
# 3. ONE SLICE ECHO TRAIN AS AN ABSOLUTE-TIME EVENT LIST
# =============================================================================
class Train:
    """Breakpoint lists per logical axis (us, DAC), plus RF and ADC events."""

    def __init__(self):
        self.g = {'r': [], 'p': [], 's': []}  # list of segments, each [(t, a), ...]
        self.rf = []
        self.adc = []

    def seg(self, axis, pts):
        self.g[axis].append(list(pts))


def trap(t0, amp, flat, ramp):
    """Trapezoid (one POSPULSE/NEGPULSE/..._SEC): ramp - plateau - ramp. Returns breakpoints, t_end."""
    return [(t0, 0), (t0 + ramp, amp), (t0 + ramp + flat, amp), (t0 + 2 * ramp + flat, 0)], t0 + 2 * ramp + flat


def build_train(P, D, gp_mul_list, nav, acq_row, pos_index, flip180_deg):
    """
    One excitation + full echo train for one slice. t = 0 is the MR3040_Start of the
    excitation slice gradient (PPL:3418). Times follow the PPL's intended timing
    (balance equations); see README for the code-overhead residuals not modelled.
    gp_mul_list: gp_order entries for echoes 1..ETL of this shot.
    """
    T = Train()
    tr_, rfd = P.tramp, P.rfdelay
    gsr = P.gs_on * D.gs_var_rescale
    corr, _ = D.phase_corr_table(pos_index)
    f_slice = D.slice_freq[pos_index]

    # ---- 90 excitation (PPL:3414-3487) ------------------------------------
    # slice_list: POSPULSE_HOLD (primary x gs_var_rescale) then NEGPULSE_SEC(tref)
    # x gs_rp (fse_mat / fse_mat_sec, PPL:1721-1723, 3071-3075).
    rf90_start = tr_ + rfd                        # intent of PPL:3425-3442 ("rfdelay = end of ramp to RF")
    t_cont = rf90_start + D.tsel90 - rfd          # MR3040_CONTINUE after tsel90-3-rfdelay (PPL:3443-3445)
    pts = [(0, 0), (tr_, gsr), (t_cont, gsr), (t_cont + tr_, 0)]
    neg, t_end_exc = trap(t_cont + tr_, -(P.gs_on * D.gs_rp), D.tref, tr_)
    T.seg('s', pts + neg[1:])
    # read_pre_list: zeros | hold | zeros | NEGPULSE_SEC(tref) x G1 (PPL:1726-1738, 3074)
    # ASSUMPTION: frame "zeros" lasts one ramp (50 points), like every other frame.
    neg_r, _ = trap(t_cont + tr_, -(P.gr_on * D.G1), D.tref, tr_)
    T.seg('r', neg_r)
    assert t_end_exc == t_cont + 3 * tr_ + D.tref   # = templ3 wait, PPL:3455-3487
    T.rf.append(dict(kind='exc', start=rf90_start, dur=D.tsel90, flip=90.0,
                     phase=D.phase_90, freq=f_slice))
    c90 = rf90_start + D.tsel90 // 2

    # ---- first refocusing pulse centre (TE/2 after 90 centre) --------------
    list_len = 2 * (2 * tr_ + D.first_crush_flat) + 2 * tr_ + D.crush_rf_flat
    rf_off_in_list1 = D.tcrush1_play + tr_ + rfd   # PPL:3543 intent (temp_mac + 40 - 40 + gate)
    c180 = [c90 + P.te * 500]                      # PPL:2409, 3471 (te/2 balance)
    adc_c = [c180[0] + P.te * 500]                 # PPL:3656 (te/2 balance, first echo)
    for k in range(1, P.views_per_seg):
        c180.append(adc_c[-1] + P.esp * 500)       # PPL:3790 (esp/2 echo -> next 180)
        adc_c.append(c180[-1] + P.esp * 500)       # PPL:2763, 3675 (esp/2 180 -> echo)

    # ---- diffusion lobes (PPL:3503-3526, 3603-3622) ------------------------
    dr, dp, ds = D.diff_rps[acq_row]
    s1 = c180[0] - D.tsel180 // 2 - rf_off_in_list1          # first 180 list start
    lobe_len = P.sm_delta + P.diff_tramp                      # Start, delay(sm_delta), Continue, ramp
    l1_end = s1 - D.extra_delta_side_us                       # delay32(extra_delta_us), PPL:3519-3523
    l1_start = l1_end - lobe_len
    l2_start = s1 + list_len + D.extra_delta_side_us          # PPL:3605-3616
    for start in (l1_start, l2_start):
        for ax, v in (('r', -dr), ('p', -dp), ('s', -ds)):    # diff_mat = (-s, -p, -r), PPL:3094
            if v != 0:
                T.seg(ax, [(start, 0), (start + P.diff_tramp, v),
                           (start + P.sm_delta, v), (start + lobe_len, 0)])
    assert l1_start >= t_end_exc, 'diffusion lobe 1 overlaps excitation rephaser'

    # ---- refocusing pulses + crushers (PPL:3530-3601) ----------------------
    for k, c in enumerate(c180):
        first = (k == 0)
        tc = D.first_crush_flat if first else P.tcrush
        camp = P.gs_on * (P.diff_crush_amp if first else P.crush_amp) * P.crush_independent_on  # PPL:3080, 3089
        this_tcrush = D.tcrush1_play if first else D.tcrush_play       # PPL:3540-3542
        rf_start = c - D.tsel180 // 2
        S = rf_start - (this_tcrush + tr_ + rfd)                       # PPL:3543-3559
        a, t = trap(S, camp, tc, tr_)                  # POSPULSE_SEC(tcrush)   x crusher (secondary)
        b, t = trap(t, gsr, D.crush_rf_flat, tr_)      # POSPULSE(crush_rf_flat) x gs_var_rescale
        cc, t = trap(t, camp, tc, tr_)                 # POSPULSE_SEC(tcrush)   x crusher
        T.seg('s', a + b[1:] + cc[1:])
        rf_end = rf_start + D.tsel180
        wait = tr_ + this_tcrush - rfd + D.crush_post_pad - D.crush_pre_pad   # PPL:3596
        assert rf_end + wait == t, 'refocusing list/RF timing mismatch'
        ph = D.phase_180 - P.phcor0 if first else D.phase_180 + corr[k]     # PPL:3459, 3786
        T.rf.append(dict(kind='ref', start=rf_start, dur=D.tsel180, flip=flip180_deg,
                         phase=ph, freq=f_slice, list_start=S, list_end=t))
        if first:
            assert l2_start >= t

    # ---- readouts (PPL:3630-3780) -----------------------------------------
    read_lists_end = []
    for k, ac in enumerate(adc_c):
        adc_start = ac - D.tacq_2
        R = adc_start - (2 * tr_ + D.tdp) - (tr_ + rfd)     # PPL:3700 (tramp*20+tdp*10) + PPL:3726
        gp_mul = gp_mul_list[k]
        nav_cnt = 0 if nav else 1
        gp_var = (-D.gp_inc * gp_mul) * nav_cnt              # PPL:3570
        # read_list: NEGPULSE_SEC(tdp) x gr_dp | POSPULSE(tacq) x read | NEGPULSE_SEC(tdp) x gr_dp
        a, t = trap(R, -(P.gr_on * D.gr_dp), D.tdp, tr_)
        b, t = trap(t, D.read_amp, D.tacq, tr_)
        cc, t = trap(t, -(P.gr_on * D.gr_dp), D.tdp, tr_)
        T.seg('r', a + b[1:] + cc[1:])
        read_lists_end.append(t)
        # phase_list: NEGPULSE_SEC(tdp) x gp_var | zeros | POSPULSE_SEC(tdp) x gp_var (PPL:1797-1802)
        pv = P.gp_on * gp_var
        if pv != 0:
            a, t2 = trap(R, -pv, D.tdp, tr_)
            b, _ = trap(t2 + 2 * tr_ + D.tacq, pv, D.tdp, tr_)
            T.seg('p', a + [(t2 + 2 * tr_ + D.tacq, 0)] + b[1:])
        # slice_list_rp: POSPULSE_SEC(tdp) x gsp_rp ... (PPL:1804-1811); gsp_rp = 0 here
        sv = P.gs_on * D.gsp_rp
        if sv != 0:
            a, t2 = trap(R, sv, D.tdp, tr_)
            b, _ = trap(t2 + 2 * tr_ + D.tacq, sv, D.tdp, tr_)
            T.seg('s', a + [(t2 + 2 * tr_ + D.tacq, 0)] + b[1:])
        # receiver phase rphase(phase_rec + phase_correction) PPL:3693-3701; phase_rec = 0
        T.adc.append(dict(start=adc_start, n=P.no_samples, dwell_us=P.sample_period / 10,
                          phase=corr[k], echo=k + 1, gp_mul=gp_mul, nav=nav))
        if k + 1 < len(c180):
            assert read_lists_end[-1] <= c180[k + 1] - D.tsel180 // 2 - (D.tcrush_play + tr_ + rfd)
    first_R = adc_c[0] - D.tacq_2 - (3 * tr_ + D.tdp + rfd)
    assert T.rf[1]['list_end'] <= l2_start and l2_start + lobe_len <= first_R, 'lobe 2 overlaps readout'

    # ---- post echo-train crusher (PPL:3939-3950) ---------------------------
    if P.post_crush_on:
        # ASSUMPTION: start = last read list end + 26 + 240 us (tr_min accounting, PPL:2829, 2870)
        t0 = read_lists_end[-1] + 26 + 240
        amp_s = -P.gs_on * P.post_crush_amp
        amp_p = -P.gp_on * P.post_crush_amp
        amp_r = -P.gr_on * P.post_crush_amp
        for ax, v in (('s', amp_s), ('p', amp_p), ('r', amp_r)):
            pts, t_end_pc = trap(t0, v, P.post_tcrush, tr_)
            T.seg(ax, pts)
        T.t_end = t_end_pc
    else:
        T.t_end = read_lists_end[-1]
    T.c90 = c90
    T.c180 = c180
    T.adc_c = adc_c
    T.l1 = (l1_start, l1_start + lobe_len)
    T.l2 = (l2_start, l2_start + lobe_len)
    return T


# =============================================================================
# 4. PULSEQ CONVERSION
# =============================================================================
def make_system(P):
    G0_hz_per_m = P.grad_var[0] * 1000.0
    return pp.Opts(
        max_grad=G0_hz_per_m, grad_unit='Hz/m',            # full scale, PPR:5 / var_20.pph:96
        max_slew=G0_hz_per_m / 100e-6, slew_unit='Hz/m/s',  # full scale in the shortest tramp allowed (100 us, PPL:114,1708)
        grad_raster_time=1e-6,      # CPU timer places gradient starts on 0.1 us; 1 us suffices for this PPR
        rf_raster_time=1e-6,
        adc_raster_time=1e-7,       # 100 ns timer tick (MAN 3.x waittimer)
        block_duration_raster=1e-6,
        rf_dead_time=20e-6,         # warmup = 20 us (var_20.pph:107)  [placeholder, see README]
        rf_ringdown_time=0.0,       # not in files [placeholder]
        adc_dead_time=0.0,          # not in files [placeholder]
    )


def rf_shape(n):
    if RF_SHAPE_FILE is None:
        return None
    w = np.loadtxt(RF_SHAPE_FILE).astype(float).ravel()
    x_old = np.linspace(0, 1, len(w))
    x_new = (np.arange(n) + 0.5) / n
    return np.interp(x_new, x_old, w)


def make_rf_event(ev, system, delay_s, n):
    ph = ev['phase'] * PHASE_RES / 1000.0 * math.pi / 180.0
    use = 'excitation' if ev['kind'] == 'exc' else 'refocusing'
    shape = rf_shape(n)
    if shape is None:
        # PLACEHOLDER for "3lobe_sinc_3kHz": sinc, TBW 4, no apodisation
        rf = pp.make_sinc_pulse(flip_angle=math.radians(ev['flip']), duration=ev['dur'] * 1e-6,
                                time_bw_product=4.0, apodization=0.0, center_pos=0.5,
                                delay=delay_s, phase_offset=ph, freq_offset=float(ev['freq']),
                                system=system, use=use, return_gz=False)
    else:
        rf = pp.make_arbitrary_rf(signal=shape, flip_angle=math.radians(ev['flip']), system=system,
                                  delay=delay_s, phase_offset=ph, freq_offset=float(ev['freq']),
                                  use=use, return_gz=False)
    return rf


def train_to_blocks(seq, system, P, D, T, t_offset_us, labels, grad_delay_us, with_adc=True):
    """Cut the absolute-time train into Pulseq blocks; gaps become delay blocks."""
    dac2hz = P.grad_var[0] * 1000.0 / DACMAX
    axis_map = {'r': 'x', 'p': 'y', 's': 'z'}
    # activity intervals
    iv = []
    for ax in T.g:
        for s in T.g[ax]:
            iv.append((s[0][0] + grad_delay_us, s[-1][0] + grad_delay_us))
    for ev in T.rf:
        iv.append((ev['start'], ev['start'] + ev['dur']))
    if with_adc:
        for ev in T.adc:
            iv.append((ev['start'], int(round(ev['start'] + ev['n'] * ev['dwell_us']))))
    iv.sort()
    merged = []
    for a, b in iv:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    t_cursor = 0
    blocks_t = []
    for a, b in merged:
        if a > t_cursor:
            seq.add_block(pp.make_delay((a - t_cursor) * 1e-6))
        events = []
        for ax in T.g:
            pts = []
            for s in T.g[ax]:
                if a <= s[0][0] + grad_delay_us and s[-1][0] + grad_delay_us <= b:
                    pts += [(t + grad_delay_us - a, v) for t, v in s]
            if not pts:
                continue
            pts.sort(key=lambda x: x[0])
            clean = []
            for t, v in pts:
                if clean and clean[-1][0] == t:
                    assert clean[-1][1] == 0 and v == 0, 'overlapping segments on one axis'
                    continue
                clean.append((t, v))
            if all(v == 0 for _, v in clean):
                continue
            tt = np.array([c[0] for c in clean], float) * 1e-6
            aa = np.array([c[1] for c in clean], float) * dac2hz
            events.append(pp.make_extended_trapezoid(channel=axis_map[ax], times=tt, amplitudes=aa,
                                                     system=system))
        for ev in T.rf:
            if a <= ev['start'] < b:
                events.append(make_rf_event(ev, system, (ev['start'] - a) * 1e-6, ev['dur']))
                blocks_t.append(('rf', ev['kind'], t_offset_us + ev['start'] + ev['dur'] / 2))
        if with_adc:
            for ev in T.adc:
                if a <= ev['start'] < b:
                    ph = ev['phase'] * PHASE_RES / 1000.0 * math.pi / 180.0
                    events.append(pp.make_adc(num_samples=ev['n'], dwell=ev['dwell_us'] * 1e-6,
                                              delay=(ev['start'] - a) * 1e-6, phase_offset=ph,
                                              system=system))
                    lin = 0 if ev['nav'] else ev['gp_mul'] + D.no_views_eff // 2
                    events += [pp.make_label(type='SET', label='LIN', value=int(lin)),
                               pp.make_label(type='SET', label='ECO', value=ev['echo'] - 1),
                               pp.make_label(type='SET', label='NAV', value=bool(ev['nav']))]
                    events += labels
        events.append(pp.make_delay((b - a) * 1e-6))
        seq.add_block(*events)
        t_cursor = b
    return t_cursor


def build_sequence(reduced=False):
    P = PPR
    D = derive(P)
    system = make_system(P)
    seq = pp.Sequence(system)
    flip180 = REFOCUS_FLIP_DEG if REFOCUS_FLIP_DEG is not None else 90.0 * D.p180_mul / D.p90_mul

    pre90 = 10200 + 70          # pre-90 code time per slice (PPL:2841 accounting)
    period = D.slice_period_us  # 666666 us (PPL:2929)

    # slice time order: BatchTimeToPos(batch_interleave=1, slice_interleave=1) ->
    # ASSUMPTION sequential pos_index 0,1,2 (function body not provided)
    slice_order = list(range(P.no_slices))
    if reduced:
        rows, shots = REDUCED_ACQ_ROWS, REDUCED_SHOTS
        n_dummy = REDUCED_N_DUMMY
        active_pos = [REDUCED_SLICE_POS_INDEX]
    else:
        rows = [ex % P.no_diff_acq for ex in range(P.no_experiments)]   # PPL:2082-2103, 4047-4055
        shots = list(range(D.n_shots))
        n_dummy = P.no_disacq                                          # PPL:2081, 3718, 3999-4006
        active_pos = slice_order

    unresolved_phase = any(not D.phase_corr_table(p)[1] for p in active_pos)
    if unresolved_phase:
        warnings.warn('Off-centre slice phase correction NOT applied (ACQPAD_TICKS unknown).')

    log = []
    t_abs = 0

    def one_tr(shot, row, rep, dummy):
        nonlocal t_abs
        gp = D.gp_order[shot * P.views_per_seg:(shot + 1) * P.views_per_seg]
        nav = (P.nav_on == 1 and shot == 0)
        for slot, pos in enumerate(slice_order):
            if pos not in active_pos:
                if reduced and REDUCED_KEEP_SLICE_SLOTS:
                    seq.add_block(pp.make_delay(period * 1e-6))
                    t_abs += period
                continue
            T = build_train(P, D, gp, nav, row, pos, flip180)
            seq.add_block(pp.make_delay(pre90 * 1e-6))
            labels = [pp.make_label(type='SET', label='SLC', value=pos),
                      pp.make_label(type='SET', label='REP', value=rep)]
            t_end = train_to_blocks(seq, system, P, D, T, t_abs + pre90, labels, GRAD_DELAY_US,
                                    with_adc=not dummy)
            t_end_all = max(t_end, T.t_end + GRAD_DELAY_US)
            tail = period - pre90 - t_end_all
            assert tail > 0
            seq.add_block(pp.make_delay(tail * 1e-6))
            log.append(dict(t0=t_abs, pos=pos, shot=shot, row=row, rep=rep, dummy=dummy, train=T))
            t_abs += period

    # dummies: navigator train, first table row, all slices (PPL:2210-2215, 3999-4003)
    for _ in range(n_dummy):
        one_tr(0, rows[0], 0, True)
    for rep, row in enumerate(rows):
        for shot in shots:
            one_tr(shot, row, rep, False)

    # ---- definitions -------------------------------------------------------
    thk_mm = DACMAX * D.pulse_bwdth / (abs(D.gs_var_rescale) * D.G0)
    seq.set_definition('Name', 'dwfse_ppl_twoTE_1_6' + ('_reduced' if reduced else ''))
    seq.set_definition('FOV', [P.fov_mm * 1e-3, P.fov_mm * 1e-3, thk_mm * 1e-3])
    seq.set_definition('TE', P.te * 1e-3)
    seq.set_definition('EchoSpacing', P.esp * 1e-3)
    seq.set_definition('ETL', P.views_per_seg)
    seq.set_definition('TR', P.tr * 1e-3)
    seq.set_definition('SlicePeriod', period * 1e-6)
    seq.set_definition('bValuesRequested', [float(P.acq_b[r]) for r in (rows if reduced else range(P.no_diff_acq))])
    seq.set_definition('bValuesPPLNominal', [float(D.acq_b_achieved_ppl[r]) for r in (rows if reduced else range(P.no_diff_acq))])
    seq.set_definition('DiffusionDAC', [float(D.diff_grad[r]) for r in (rows if reduced else range(P.no_diff_acq))])
    dirs = []
    for r in (rows if reduced else range(P.no_diff_acq)):
        dirs += [P.acq_x[r] / 1000.0, P.acq_y[r] / 1000.0, P.acq_z[r] / 1000.0]
    seq.set_definition('DiffusionDirectionsRPS', dirs)
    seq.set_definition('SmallDelta', P.sm_delta * 1e-6)
    seq.set_definition('BigDelta', P.big_delta * 1e-6)
    seq.set_definition('SliceThickness', thk_mm * 1e-3)
    seq.set_definition('RefocusFlipDeg', flip180)
    seq.set_definition('RFShape', 'PLACEHOLDER_sinc_TBW4' if RF_SHAPE_FILE is None else str(RF_SHAPE_FILE))
    seq.set_definition('GradientDelayModel_us', GRAD_DELAY_US)
    if unresolved_phase:
        pc = 'NOT_APPLIED_acqpad_unknown'
    elif all(D.slice_freq[p] == 0 for p in active_pos):
        pc = 'not_needed_centre_slice_only'
    else:
        pc = 'applied'
    seq.set_definition('OffsetSlicePhaseCorr', pc)
    seq.set_definition('AxisMap', 'x=read y=phase z=slice (logical)')
    seq.set_definition('Reduced', int(reduced))
    seq.set_definition('Source', 'FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppl/.ppr')
    return seq, P, D, log


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--reduced', action='store_true')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    seq, P, D, log = build_sequence(reduced=args.reduced)
    out = args.out or ('dwfse_reduced.seq' if args.reduced else 'dwfse_full.seq')
    ok, rep = seq.check_timing()
    print('check_timing:', 'PASS' if ok else 'FAIL', '' if ok else rep[:5])
    seq.write(out)
    print('wrote', out, 'duration %.3f s' % seq.duration()[0], 'blocks', len(seq.block_events))

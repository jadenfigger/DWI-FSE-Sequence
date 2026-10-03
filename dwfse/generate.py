"""
PyPulseq re-implementation of ONE variant of FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppl:
diffusion-weighted fast spin echo, ETL > 1, diffusion on.

Every scan parameter comes from a .ppr file (default: the protocol PPR in the
repository root) and can be overridden, so the sequence is controlled the same
way as on the scanner. A few extra hardware/simulation parameters (hw_*, sim_*)
cover things the PPR does not hold. See README.md for the parameter list.

Citations in comments:
    PPL:n  -> line n of FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppl
    PPR:n  -> line n of FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppr
    var_20 / m3040_15 / m3031_15 / offst_20 -> the .pph include files
    MAN    -> EVO Pulse Sequence Program Manual.pdf

All PPL arithmetic is replayed with integer division that truncates toward
zero (PPL '/', scale() = (a*b)/c, MAN 4.8.12.1). Internal time unit: the PPL
timer tick, 100 ns (MAN 4.8 waittimer). Gradients: logical-axis DAC.
Logical axes -> Pulseq axes: read -> x, phase -> y, slice -> z.

Usage (normally through the project CLI, see README.md):
    python dw.py gen out.seq                     # full protocol from scanner/*.ppr
    python dw.py gen out.seq --reduced           # simulation cut
    python dw.py gen out.seq --set te=60 --set acq_b=0,1000 --params my.json
"""

import csv
import json
import math
import os
import warnings
from types import SimpleNamespace

import numpy as np
import pypulseq as pp

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PPR = os.path.join(HERE, '..', 'scanner', 'FSE_dwi_CPMG_non_CPMG_twoTE-1.6.ppr')

DACMAX = 32767      # var_20:96, 101; CREATE_MATRIX divisor (m3040_15:274)
PHASE_RES = 225     # var_20:108 (0.225 deg per phase unit)
TICK = 1e-7         # 100 ns PPL timer tick (MAN 4.8)

# NEWSHAPE_MAC table (PPL:598-618) and the sinc frame models live in rf_pulses.py
from .rf_pulses import RF_TABLE, profile_summary, sinc_frame  # noqa: E402

# =============================================================================
# Hardware / simulation parameters that are NOT in the PPR (all overridable)
# =============================================================================
EXTRA_DEFAULTS = dict(
    # Physical gradient lag behind the commanded waveform. The PPL delays RF
    # and ADC by rfdelay "to compensate for (isotropic) gradient group delay"
    # (PPL:4100), so the scanner is assumed to lag by the PPR rfdelay (60 us).
    # 0 = play the commanded timing literally.
    hw_grad_delay_us=60,
    hw_gamma_hz_per_t=42.577478e6,
    hw_max_grad_hz_per_m=None,         # None -> grad_var[0] full scale (PPR:5)
    hw_max_slew_hz_per_m_per_s=None,   # None -> full scale / 100 us (min tramp, PPL:114)
    hw_rf_dead_time_us=100,            # typical Pulseq values; checks only
    hw_rf_ringdown_time_us=30,
    hw_adc_dead_time_us=10,
    # RF
    sim_excitation_flip_deg=None,      # None -> alpha (PPR, 90 deg scale factor)
    sim_refocus_flip_deg=180.0,        # p180_scale assumed calibrated; 'linear' -> 90*p180_mul/p90_mul
    sim_excitation_phase_deg=0,        # excitation-only offset, quantized to 0.225 deg hardware units
    sim_refocus_phase_offsets_deg=None,  # None -> zero; otherwise one relative offset per echo
    # RF frame model (vendor frames unavailable; see rf_pulses.py). 'truncated_sinc' =
    # N-lobe sinc, zero crossings every 1/BW, cut after N lobes (3lobe_sinc_3kHz: TBW 4).
    # 'bw_matched_sinc' = stretched so its BW equals the PPL slice bandwidth (71 %).
    sim_rf_model='truncated_sinc',
    sim_rf_apodization=0.0,            # 0 = none, 0.5 = Hanning, 0.46 = Hamming
    sim_rf_bw_fraction=None,           # bw_matched_sinc only; None -> bw_override/100 (0.71)
    sim_rf_shape_file=None,            # one amplitude per line; overrides the model
    # v1.6 [CRUSH-PE] centres the 180s on the COMMANDED plateau (PPL:1316-1317
    # cancel rfdelay), unlike the 90 and ADC. False = replicate the PPL as
    # written. True = command the 180 slice lists (and the diffusion lobes that
    # are chained to them) rfdelay earlier, so the 180s get the same group-
    # delay compensation as the 90 (intended behaviour, not in the PPL).
    sim_fix_refocus_centering=False,
    sim_acqpad_ticks=None,             # acqpad(sample_period) for off-centre slice phase correction
    sim_aqphase_table=None,            # aqphase(no_acq, phase_cycle) values if phase_cycle != 1
    sim_slice_order=None,              # None -> sequential pos 0..n-1 (confirmed)
    sim_parsetup=True,                 # recompute gs_var/gr_var/gp_init_var/offsets from mm values
    sim_zeros_frame_us=None,           # duration of frame "zeros" (None -> one ramp)
    sim_train_crusher_scales=None,     # independent mode only; one signed-DAC multiplier per refocusing RF
    sim_post_crush_gap_us=266,         # last read list end -> post crusher (26+240, PPL:2829, 2870)
    sim_pre90_us=10270,                # slot start -> 90 gradient start (10200+70, PPL:2841)
    # reduced (--reduced) cut; timing inside every TR is unchanged
    sim_reduced_slices=None,           # pos indices; None -> centre slice
    sim_reduced_rows=None,             # acq-table rows; None -> first row with b > 0
    sim_reduced_shots=None,            # shot indices (0 = navigator); None -> first imaging shot
    sim_reduced_n_dummy=0,
    sim_reduced_keep_slots=True,       # keep other slices' slots as dead time
)

ARRAY_KW = {'VAR_ARRAY', 'GRADIENT_STRENGTH', 'FOV_READ_OFF', 'FOV_PHASE_OFF',
            'FOV_SLICE_OFF', 'X_ANGLE', 'Y_ANGLE', 'Z_ANGLE'}


class PPLAbort(RuntimeError):
    """A condition on which the PPL prints an error and jumps to 'end'."""


# =============================================================================
# 1. PARAMETERS
# =============================================================================
def _num(s):
    s = s.strip()
    for f in (int, float):
        try:
            return f(s)
        except ValueError:
            pass
    return s.strip('"')


def read_ppr(path):
    """Parse a .ppr file into {ppl_variable: value}. Continuation lines start with ','."""
    stmts = []
    with open(path, encoding='latin-1') as f:
        for line in f:
            line = line.rstrip('\r\n')
            if line.startswith(':'):
                stmts.append(line[1:])
            elif line.startswith(',') and stmts:
                stmts[-1] += line
    out = {}
    for st in stmts:
        toks = next(csv.reader([st], skipinitialspace=True))
        head = toks[0].split(None, 1)
        kw, name = head[0], (head[1].strip() if len(head) > 1 else '')
        vals = [_num(t) for t in toks[1:] if t.strip() != '']
        if kw == 'FOV':
            out['fov_mm'] = _num(name)
            continue
        if kw == 'FOV_OFFSETS':
            n = int(_num(name))
            out['fov_offsets_mm'] = [vals[3 * i:3 * i + 3] for i in range(n)]
            continue
        if not name or not name.replace('_', '').isalnum() or name[0].isdigit() or not vals:
            continue
        if kw in ARRAY_KW:
            out[name] = vals[1:1 + int(vals[0])]
            continue
        out[name] = vals[0]
        if kw == 'SLICE_THICKNESS' and len(vals) > 1:
            out['slice_thickness_mm'] = vals[1]
        if kw == 'SLICE_SEPARATION' and len(vals) > 1:
            out['slice_separation_mm'] = vals[1]
    return out


def load_params(ppr_path=None, overrides=None):
    """PPR values + EXTRA_DEFAULTS + overrides -> namespace C."""
    p = read_ppr(ppr_path or DEFAULT_PPR)
    p.update({k: v for k, v in EXTRA_DEFAULTS.items() if k not in p})
    for k, v in (overrides or {}).items():
        if k not in p:
            raise KeyError(f'unknown parameter {k!r}')
        p[k] = v
    return SimpleNamespace(**p)


def parse_set(s):
    k, v = s.split('=', 1)
    v = v.strip()
    try:
        val = json.loads(v)
    except json.JSONDecodeError:
        val = [_num(x) for x in v.split(',')] if ',' in v else _num(v)
    return k.strip(), val


# =============================================================================
# 2. PPL INTEGER ARITHMETIC
# =============================================================================
def tdiv(a, b):
    """PPL '/': truncation toward zero (FloorDiv exists separately, stdfn_15)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def tmod(a, b):
    return a - b * tdiv(a, b)


def scale(a, b, c):
    """MAN 4.8.12.1: (e1*e2)/e3, 32-bit product."""
    return tdiv(a * b, c)


def parsetup(C, D):
    """Values PARSETUP writes into the PPR, recomputed from the mm values.
    Formulas inferred; they reproduce gs_var, gr_var, gp_init_var and
    fov_slice_off of the protocol PPR exactly (truncation)."""
    G0 = C.grad_var[0]
    new = {}
    new['gs_var'] = int(-1070.0 * DACMAX / (C.slice_thickness_mm * G0))          # 1070 Hz ref, PPL:1435
    new['gr_var'] = int(-DACMAX / (C.fov_mm * C.sample_period * 1e-7 * G0))       # FOV keyword, PPL:94
    new['gp_init_var'] = int(-(C.no_views / 2) * DACMAX / (C.fov_mm * 2.5e-3 * G0))  # phase_time 2.5 ms, PPL:94
    n = C.no_slices
    offs = getattr(C, 'fov_offsets_mm', None)
    if offs is None or len(offs) != n:
        sep = C.slice_separation_mm
        offs = [[0.0, 0.0, (i - (n - 1) / 2) * sep] for i in range(n)]
    new['fov_slice_off'] = [int(round(o[2] * 400)) for o in offs]                 # scale 400/mm, PPL:96
    new['fov_read_off'] = [int(round(o[0] * 4000 / C.fov_mm)) for o in offs]      # scale 4000/FOV (inferred)
    new['fov_phase_off'] = [int(round(o[1] * 4000 / C.fov_mm)) for o in offs]
    D.parsetup_diffs = {k: (getattr(C, k, None), v) for k, v in new.items() if getattr(C, k, None) != v}
    for k, v in new.items():
        setattr(C, k, v)


def derive(C):
    """Replay the PPL set-up arithmetic and checks. Returns namespace D."""
    D = SimpleNamespace(warnings=[])
    abort = PPLAbort
    L = C.views_per_seg

    # Resolve bounded experiment controls before replaying the PPL arithmetic.
    # RF phase is stored in integer var_20 units (PHASE_RES = 0.225 deg/unit).
    def phase_units(value, name):
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise abort(f'{name} must be finite') from None
        if not math.isfinite(value):
            raise abort(f'{name} must be finite')
        if abs(value) > 360:
            value = math.fmod(value, 360)
        return int(round(value * 1000 / PHASE_RES))

    D.excitation_phase_offset = phase_units(C.sim_excitation_phase_deg, 'sim_excitation_phase_deg')
    refocus_offsets = C.sim_refocus_phase_offsets_deg
    if refocus_offsets is None:
        D.refocus_phase_offsets = [0] * L
    else:
        try:
            if len(refocus_offsets) != L:
                raise abort(f'sim_refocus_phase_offsets_deg must contain exactly ETL={L} values')
        except TypeError:
            raise abort(f'sim_refocus_phase_offsets_deg must contain exactly ETL={L} values') from None
        D.refocus_phase_offsets = [phase_units(v, f'sim_refocus_phase_offsets_deg[{k}]')
                                   for k, v in enumerate(refocus_offsets)]
    D.excitation_phase_offset_deg = D.excitation_phase_offset * PHASE_RES / 1000.0
    D.refocus_phase_offsets_deg = [v * PHASE_RES / 1000.0 for v in D.refocus_phase_offsets]

    crusher_scales = C.sim_train_crusher_scales
    if crusher_scales is not None:
        if C.crush_independent_on != 1:
            raise abort('sim_train_crusher_scales requires crush_independent_on=1')
        try:
            if len(crusher_scales) != L:
                raise abort(f'sim_train_crusher_scales must contain exactly ETL={L} values')
        except TypeError:
            raise abort(f'sim_train_crusher_scales must contain exactly ETL={L} values') from None
        multipliers = []
        for k, value in enumerate(crusher_scales):
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise abort(f'sim_train_crusher_scales[{k}] must be finite') from None
            if not math.isfinite(value):
                raise abort(f'sim_train_crusher_scales[{k}] must be finite')
            multipliers.append(value)
        bases = [C.diff_crush_amp] + [C.crush_amp] * (L - 1)
        for k, (base, multiplier) in enumerate(zip(bases, multipliers)):
            if base and abs(multiplier) > (DACMAX + 0.5) / abs(base):
                raise abort(f'sim_train_crusher_scales[{k}] gives an out-of-range crusher amplitude; '
                            f'must be -{DACMAX}..{DACMAX} DAC')
        D.train_crusher_amplitudes_dac = [int(round(base * multiplier))
                                           for base, multiplier in zip(bases, multipliers)]
        for k, amp in enumerate(D.train_crusher_amplitudes_dac):
            if not -DACMAX <= amp <= DACMAX:
                raise abort(f'sim_train_crusher_scales[{k}] gives crusher amplitude {amp} DAC; '
                            f'must be -{DACMAX}..{DACMAX}')
    else:
        D.train_crusher_amplitudes_dac = ([C.diff_crush_amp] + [C.crush_amp] * (L - 1)
                                           if C.crush_independent_on == 1 else None)

    if C.sim_parsetup:
        parsetup(C, D)
    else:
        D.parsetup_diffs = {}
    G0 = C.grad_var[0]
    D.G0 = G0

    # ---- variant / unsupported options -------------------------------------
    if C.diff_on != 1:
        raise abort('This generator implements the diffusion-ON variant only (diff_on=1)')
    if C.views_per_seg <= 1:
        raise abort('This generator implements ETL > 1 only')
    for k, ok in (('flow_comp_on', 0), ('de_on', 0), ('sat_on', 0), ('chess_on', 0), ('mtc_on', 0),
                  ('gating', 0), ('dixon_on', 0), ('echoes_to_discard', 0), ('no_views_2', 1),
                  ('slice_block', 1)):
        if getattr(C, k, ok) != ok:
            raise abort(f'{k}={getattr(C, k)} is not implemented (only {ok})')

    # ---- PPL:512, 655 -------------------------------------------------------
    if C.tramp - 40 + C.rfdelay - (C.rfgate_delay - 17) < 10:
        raise abort('Illegal parameter')
    if C.tramp * 3 + C.tref_setup - C.rfdelay < 43:
        raise abort('Illegal parameter (2)')

    # ---- experiments vs acquisition table (PPL:673-684) ---------------------
    if C.no_experiments % C.no_diff_acq != 0:
        raise abort(f'No expts should be divisible by no of diffusion acqs ({C.no_diff_acq})')
    if C.no_experiments < C.no_diff_acq:
        raise abort('Number of expts must be = no_diff_acq')

    # ---- b-value -> DAC (PPL:575-585, 685-780) ------------------------------
    sm, bd = C.sm_delta, C.big_delta
    if bd < 0:
        bd += 65536                                    # PPL:559
    b_kfac = 0
    if 0 < sm <= 10000 and sm < bd <= 80000:
        a = (sm * sm + 500) // 1000
        a = a * ((bd - sm // 3 + 50) // 100)
        a = (a + 500) // 1000
        a = (a * 63) // 10
        a = (a * 63) // 10
        b_kfac = (a + 50) // 100
    D.b_kfac = b_kfac

    def b_of_dac(d):
        g = tdiv(d * G0, 32767)
        return (((g * g + 5000) // 10000) * b_kfac + 5000) // 10000

    D.b_of_dac = b_of_dac
    acq_grad = list(C.acq_grad[:C.no_diff_acq])
    bmode = (C.b_input_mode == 1)
    if bmode:
        for i in range(C.no_diff_acq):                 # PPL:689-705
            s2 = C.acq_x[i] ** 2 + C.acq_y[i] ** 2 + C.acq_z[i] ** 2
            if not 902500 <= s2 <= 1102500:
                raise abort(f'Row {i} not unit length: b-value mode needs all directions normalised to 1000')
        if b_kfac == 0:
            raise abort('b-value mode needs delta <= 10 ms and Delta <= 80 ms')
    max_diff_grad = 30000
    D.b_max = b_of_dac(max_diff_grad)
    D.acq_b_nominal = []
    for i in range(C.no_diff_acq):
        target = C.acq_b[i]
        if bmode and target > D.b_max:
            raise abort(f'b={target} too high for current delta/Delta. Max b = {D.b_max}')
        lo, hi = 1, max_diff_grad
        for _ in range(20):
            mid = lo + (hi - lo + 1) // 2
            if b_of_dac(mid) <= target:
                lo = mid
            else:
                hi = mid - 1
            if lo >= hi:
                break
        dac = scale(lo, 100, C.diff_grad_scale)
        if bmode:
            acq_grad[i] = 1 if target <= 0 else dac
    D.acq_grad = acq_grad
    D.diff_grad = [scale(g, C.diff_grad_scale, 100) for g in acq_grad]       # PPL:2106
    for g in D.diff_grad:
        if g > 30000:
            raise abort(f'Diffusion gradient amp {g}DAC is too high')
    D.acq_b_nominal = [b_of_dac(g) for g in D.diff_grad]
    D.diff_rps = [(scale(g, C.acq_x[i], 1000), scale(g, C.acq_y[i], 1000), scale(g, C.acq_z[i], 1000))
                  for i, g in enumerate(D.diff_grad)]                          # PPL:2160-2162

    # ---- phase-encode table (PPL:788-1121) ----------------------------------
    nv = C.no_views
    if not (1 <= nv <= 1024 and 1 <= L <= nv):
        raise abort('Views (including navigator) must be 1..1024; ETL must be 1..views')
    if C.PE_order not in (1, 6, 7):
        raise abort('Set PE order to 1, 6 or 7 for multi-echo DWI (5 = single echo)')
    te_eff = 1                                                                # PPL:815
    if C.PE_order in (6, 7) and C.PF_echoes not in (0, L):
        raise abort('PE 6/7 requires full Fourier: PF echoes = 0 or ETL')
    nve = nv - L * (C.nav_on == 1)
    if nve < 1:
        raise abort('Navigator leaves no imaging views')
    if nve % 2:
        raise abort('Effective number of views must be even number')
    PF = C.PF_echoes or L
    if PF < L:
        raise abort('PF eff echoes must be >= VPS')
    if PF >= 2 * L:
        raise abort('PF eff echoes must be < 2*VPS')
    vpe = tdiv(nve, 2 * L)
    if te_eff > L:
        raise abort('The eff echo time is too large')
    if C.PE_order in (1, 6) and nve % (2 * L):
        raise abort('Number of views / (2*views per segment) must be an integer')
    if C.PE_order == 7 and nve % L:
        raise abort('Linear interleaved requires imaging views divisible by ETL')
    gp = [0] * L if C.nav_on == 1 else []
    if C.PE_order == 1:                                                       # PPL:1058-1088
        gp_loc = tdiv(nve, 2) - vpe - 1
        for shot in range(1, 2 * vpe + 1):
            gp_loc += 1
            for echo in range(1, L + 1):
                m = gp_loc + vpe * (echo - te_eff) if shot > vpe else gp_loc - vpe * (echo - te_eff)
                gp.append(m - tdiv(nve, 2))
    else:                                                                     # PPL:1090-1121
        pe_shots = tdiv(nve, L)
        for shot in range(pe_shots):
            for echo in range(L):
                if C.PE_order == 6:
                    idx = L - 1 - echo
                    m = shot - vpe - vpe * idx if shot < vpe else shot - vpe + vpe * idx
                else:
                    m = -tdiv(nve, 2) + shot + echo * pe_shots
                gp.append(m)
    if len(gp) != nv:
        raise abort('Internal PE table length error')
    D.gp_order, D.no_views_eff, D.views_per_echo = gp, nve, vpe
    D.pe_center_echo = {1: 1, 6: L, 7: tdiv(tdiv(nve, 2), tdiv(nve, L)) + 1}[C.PE_order]   # PPL:1201-1203

    # ---- imaging parameters (PPL:1253-1496) --------------------------------
    D.deg_90 = scale(90, 1000, PHASE_RES)
    D.deg_360 = scale(360, 1000, PHASE_RES)
    D.tacq = (C.sample_period * (C.no_samples + C.no_discard)) // 10        # us
    if D.tacq > 32767:
        raise abort('Sampling time too long')
    D.tacq_2 = D.tacq // 2
    if C.rfnum not in RF_TABLE:
        raise abort(f'rfnum {C.rfnum} not in NEWSHAPE table')
    D.rf_frame, D.tsel90, rf_bw = RF_TABLE[C.rfnum]
    D.tsel180 = D.tsel90
    ind = C.crush_independent_on
    if ind not in (0, 1):
        raise abort('Independent crusher switch must be 0 or 1')
    D.crush_pre_pad = D.crush_post_pad = D.crush_rf_pad = 0
    D.crush_rf_flat = D.tsel90
    if ind == 1:                                                              # PPL:1285-1318
        if not (100 <= C.tramp <= 1000 and C.tramp % 10 == 0):
            raise abort('Independent crushers require ramp 100..1000 us, multiple of 10')
        if C.crush_amp == -32768 or C.diff_crush_amp == -32768:
            raise abort('Crusher amplitudes must be -32767..32767 DAC')
        if not (0 < C.tcrush <= 5000 and (C.tcrush * 50) % C.tramp == 0):
            raise abort('tcrush must be 1..5000 us and an exact multiple of tramp/50 us')
        if not (0 < C.diff_tcrush <= 10000 and (C.diff_tcrush * 50) % C.tramp == 0):
            raise abort('diff_tcrush must be 1..10000 us and an exact multiple of tramp/50 us')
        t = C.tramp // 10
        D.crush_rf_flat = ((D.tsel90 + 2 * C.rfdelay + t - 1) // t) * t
        if D.crush_rf_flat % 2:
            D.crush_rf_flat += t
        D.crush_rf_pad = D.crush_rf_flat - D.tsel90
        D.crush_pre_pad = 2 * C.tramp + D.crush_rf_pad // 2 - C.rfdelay
        D.crush_post_pad = 2 * C.tramp + D.crush_rf_pad // 2 + C.rfdelay
    D.tcrush_play = C.tcrush + D.crush_pre_pad                                # PPL:1319
    D.tcrush1_play = C.diff_tcrush + D.crush_pre_pad                          # PPL:1321
    D.bw_override = 71                                                        # 2D, PPL:1327
    D.pulse_bwdth = tdiv(D.bw_override * rf_bw, 100)
    batch = C.batch_slices or C.no_slices
    if C.no_slices % batch:
        raise abort('No of slices should be an integer number of batch size')
    D.batch_slices = batch
    D.tref = 4 * C.tref_setup
    D.tdp = C.tref_setup
    D.gr_oversample, D.gr_undersample = 3 + C.oversample, 3 - C.oversample
    D.gp_oversample, D.gp_undersample = 3 + C.oversample2, 3 - C.oversample2
    if C.FOVf != 8:
        if C.oversample2 != 0:
            raise abort("Can't do phase oversampling with rect FOV - adjust FOVf!")
        D.gp_oversample, D.gp_undersample = C.FOVf, 8
    D.scale_read_off = scale(4000, D.gr_oversample, D.gr_undersample)
    D.scale_phase_off = scale(4000, D.gp_oversample, D.gp_undersample)
    t1 = tdiv(C.gp_init_var * D.gp_undersample * 2500, D.gp_oversample)
    t1 = tdiv(t1, D.tdp + C.tramp)
    if not -32768 <= t1 <= 32767:
        raise abort('FOV too small in PE dir')
    D.gp_inc = scale(t1, 2, nv)
    D.gs_var_rescale = tdiv(C.gs_var * D.pulse_bwdth, 1070)
    if DACMAX + D.gs_var_rescale < 0:
        raise abort('Slice thickness too small for pulse selected')
    t1 = tdiv(D.tacq + C.tramp, 2) * C.gr_var
    t1 = tdiv(t1, D.tdp + C.tramp)
    D.gr_comp = tdiv(t1 * D.gr_undersample, D.gr_oversample)
    if DACMAX + D.gr_comp < 0:
        raise abort('FOV too small for read comp')
    D.gs_comp = tdiv(D.gs_var_rescale * tdiv(D.tsel90 + C.tramp, 2), D.tref + C.tramp)
    if DACMAX + D.gs_comp < 0:
        raise abort('Slice refocussing lobe is excessive')
    # PPL:2976-3013
    t1 = D.gs_comp + tdiv(D.gs_comp * (C.gs_comp_scale + 0), 1000)
    t2 = tdiv(t1 * C.gsp_lobe, 100)
    if DACMAX + t2 < 0 or DACMAX + (t1 - t2) < 0:
        raise abort('Reduce slice grad comp')
    D.gs_rp = t1 - t2
    D.gsp_rp = tdiv(t2 * (D.tref + C.tramp), D.tdp + C.tramp)
    t1 = D.gr_comp + tdiv(tdiv(D.gr_comp * C.gr_comp_scale, 8), 1000)
    t2 = tdiv(t1 * C.grp_lobe, 100)
    if DACMAX + t2 < 0 or DACMAX + (t1 - t2) < 0:
        raise abort('Reduce read grad comp')
    D.gr_dp = t1 - t2
    D.grp_dp = -tdiv(t2 * (D.tdp + C.tramp), D.tref + C.tramp)
    D.G1, D.G2 = D.grp_dp, 0
    D.read_amp = (C.gr_on * D.gr_undersample) * tdiv(C.gr_var, D.gr_oversample)   # PPL:3688
    D.clock = C.tramp // 5                                                   # PPL:1714 (100 ns)
    D.ramp_ticks = 50 * D.clock                                              # 50-point frames
    if C.diff_tramp != C.tramp:
        raise abort(f'diff_tramp ({C.diff_tramp} us) must equal tramp ({C.tramp} us) for consistent DW timing')
    if C.diff_tcrush < C.tcrush:
        D.warnings.append(f'Warning: diff_tcrush ({C.diff_tcrush} us) is SMALLER than tcrush ({C.tcrush} us)')

    # ---- TE / big delta (PPL:2365-2567) -------------------------------------
    tcrush1 = C.diff_tcrush
    D.tcrush1 = tcrush1
    min_pre = (D.tsel90 // 2 + 4 * C.tramp + 1000 + D.tsel180 // 2 + tcrush1 + 20)
    min_pre += D.crush_pre_pad + sm + C.diff_tramp
    min_post = (D.tsel180 // 2 + 3 * C.tramp + 500 + tcrush1) + (D.tacq * 100) // 200 + 66
    min_post += D.crush_post_pad + sm + C.diff_tramp
    if C.te == 0:
        raise abort('Set TE explicitly when diffusion is on')
    half = C.te * 500
    sp_pre, sp_post = half - min_pre, half - min_post
    D.min_te = max(min_pre, min_post) * 2
    if sp_pre <= 0 or sp_post <= 0:
        raise abort(f'TE is too short, increase to {D.min_te // 1000 + 1} ms (={D.min_te} us)')
    big_min = sm + (C.diff_tramp + D.tsel180 + 2 * (C.tramp + tcrush1) + D.crush_pre_pad + D.crush_post_pad)
    if bd > big_min + sp_pre + sp_post:
        raise abort(f'Big delta ({bd}) is too big for given TE, max Big delta = {big_min + sp_pre + sp_post} us')
    if bd < big_min:
        raise abort(f'Big delta is too small, min Big delta = {big_min // 1000 + 1} ms ({big_min} us)')
    D.extra_delta = bd - sm - (C.diff_tramp + D.tsel180 + 2 * C.tramp + 2 * tcrush1
                               + D.crush_pre_pad + D.crush_post_pad)
    t3 = tdiv(D.extra_delta, 2)
    if not (t3 <= sp_pre and t3 <= sp_post):
        raise abort(f'TE is too short to realise given diffusion timing; increase to '
                    f'{(D.min_te + 2 * t3) // 1000 + 1} ms')
    if t3 < 3:
        raise abort(f'Increase TE and Big delta by {(3 - t3) * 2} us')
    # each-side delay in ticks (PPL:2559-2567)
    D.extra_side_ticks = D.extra_delta * 5 if ind == 1 else 10 * t3
    D.min_te += D.extra_delta + 1000                                         # PPL:2647
    D.te_a = D.tsel90 + C.tcrush + D.tref + 4 * C.tramp + D.crush_pre_pad
    D.te_b = D.tsel90 // 2 + C.tcrush + D.tdp + 4 * C.tramp + D.tacq_2 + D.crush_post_pad
    if C.te * 1000 < D.min_te:
        raise abort(f'Echo time should be greater than Minimum TE (= {D.min_te} us)')
    if half - (D.te_a + 21) < 0 or half - (D.te_b + 21) < 0:
        raise abort(f'TE is too short, increase to {(max(D.te_a, D.te_b) + 21) // 500 + 1} ms')
    D.te_balance_al = half - D.te_a
    D.te_balance_bl = half - D.te_b
    pre = (D.te_balance_al - 27 + C.post_90_delay1 - sm - C.diff_tramp - (tcrush1 - C.tcrush)) * 10 \
        - D.extra_side_ticks - 185
    if pre <= 25:
        raise abort(f'TE too short: pre-180 balance = {pre} ticks')
    post = (D.te_balance_bl * 10 - 210) - sm * 10 - D.extra_side_ticks - C.diff_tramp * 10 \
        - (tcrush1 - C.tcrush) * 10 - 156
    if post <= 25:
        raise abort(f'TE too short: first-echo balance = {post} ticks')
    D.te_balance_bl_esp = C.esp * 500 - D.te_b
    if C.esp * 500 - (D.te_b + 21) < 0:
        raise abort(f'esp too short: increase esp to at least {(D.te_b + 21) // 500 + 1} ms')
    D.min_esp_us = 2 * (D.te_b + 21)

    # ---- TR (PPL:2822-2946) -------------------------------------------------
    t1 = C.te * 1000 + (L - 1) * C.esp * 1000 + C.tramp + D.tsel90 // 2
    t1 += 3 * C.tramp + C.tref_setup + D.tacq_2 + 26
    t1 += 17 * (C.tramp < 130) + 30 * (C.tramp < 120) + 30 * (C.tramp < 110)
    t1 += 10200 + 70 + 69
    t3 = (2 * C.tramp + C.post_tcrush + 240) if C.post_crush_on else 0
    D.tr_min_us = t1 + t3

    def tr_for(completed_ex):
        tr = C.tr
        if C.TR_array_size > 0:
            if C.no_experiments % C.TR_array_size:
                raise abort('Exper array size must be divisable by the TR array size')
            tr = C.TR_array[completed_ex % C.TR_array_size]
        if tr == 0:
            tr = (D.tr_min_us * batch) // 1000 + 1                           # PPL:2903
        if (tr * 1000) // batch - D.tr_min_us < 0:
            raise abort(f'TR too short, increase to {(D.tr_min_us * batch) // 1000 + 1} ms')
        return tr

    D.tr_for = tr_for
    D.min_tr_ms = (D.tr_min_us * batch) // 1000 + 1

    # ---- RF -----------------------------------------------------------------
    D.p90_mul = min(scale(C.rfcal, C.alpha, 90), 2047)
    D.p180_mul = min(scale(C.rfcal, C.p180_scale, 100), 2047)
    D.flip90 = float(C.alpha if C.sim_excitation_flip_deg is None else C.sim_excitation_flip_deg)
    if C.sim_refocus_flip_deg == 'linear':
        D.flip180 = D.flip90 * D.p180_mul / D.p90_mul
    else:
        D.flip180 = float(C.sim_refocus_flip_deg)

    def aqphase(no_acq):
        if C.phase_cycle == 1 or no_acq == 0:
            return 0
        if C.sim_aqphase_table is None:
            raise abort('aqphase() for phase_cycle != 1 is firmware; give sim_aqphase_table')
        return C.sim_aqphase_table[no_acq % len(C.sim_aqphase_table)]

    D.aqphase = aqphase

    # ---- frequencies and phase offsets (PPL:2249-2304, offst_20) ------------
    D.slice_freq, D.read_freq, D.fov_phase_deg = [], [], []
    sfv = tdiv(C.slice_mm_10 * D.pulse_bwdth, 10)                            # PPL:2253
    for pos in range(C.no_slices):
        D.slice_freq.append(tdiv(C.fov_slice_off[pos] * D.pulse_bwdth, 400) + sfv)
        rfl = tdiv(C.fov_read_off[pos] * 10000, (D.scale_read_off // 1000) * C.sample_period)
        D.read_freq.append(rfl)
        if abs(rfl + C.rec_freq) > 32767:
            raise abort('Reduce receive frequency')
        tm = scale(D.scale_phase_off, PHASE_RES, 1000)
        fpd = scale(C.fov_phase_off[pos], 360, tm)
        if fpd < 0:
            fpd += scale(360, 1000, PHASE_RES)
        D.fov_phase_deg.append(fpd)

    def phase_corr_table(pos):
        """phase_correction after k echoes, k = 0..ETL (PPL:2795-2813, 3735-3754)."""
        t_1 = D.slice_freq[pos]
        t_2 = -D.read_freq[pos] - C.rec_freq
        if t_1 == 0 and t_2 == 0:
            return [0] * (L + 1), True
        if C.sim_acqpad_ticks is None:
            return [0] * (L + 1), False
        extra_val = {20: 3, 15: 3, 10: 38, 5: 59}.get(C.sample_period, 51 if C.sample_period > 19 else 0)
        overhead = ((C.sim_acqpad_ticks + 16 + extra_val) * 16) // 100
        phcor = C.phcor_plus if t_1 > 0 else C.phcor_minus
        t3_ = overhead + tdiv((D.tacq + C.tramp) * 16, 10)
        t4_ = (t_1 + t_2) * t3_ + tdiv(16 * (phcor * t_1 + C.r_phcor * t_2), 10)
        t5_ = tdiv(t4_, 1000)
        ang = tmod(t5_, D.deg_360)
        rem = t4_ - t5_ * 1000
        out = [0]
        for k in range(1, L + 1):
            c0 = tmod(ang * k, D.deg_360)
            c1 = tdiv(k * rem, 1000)
            r = tmod(k * rem, 1000)
            c2 = 1 if r > 500 else (-1 if r < -500 else 0)
            out.append(tmod(c0 + c1 + c2, D.deg_360))
        return out, True

    D.phase_corr_table = phase_corr_table
    D.phase_180 = 3 * D.deg_90                                               # + phase_90, PPL:2296
    return D


# =============================================================================
# 3. ONE SLICE ECHO TRAIN (absolute ticks; t = 0 at the 90 slice-gradient start)
# =============================================================================
class Train:
    def __init__(self):
        self.g = {'r': [], 'p': [], 's': []}
        self.rf, self.adc = [], []


def build_train(C, D, gp_mul_list, nav, row, pos, no_acq):
    T = Train()
    us = 10                                   # ticks per us
    rmp = D.ramp_ticks
    rfd = C.rfdelay * us

    def q(t_us):                              # plateau via MR3040_Delay (m3040_15:41-51)
        return (t_us * 10 // D.clock) * D.clock

    def trap(t0, amp, flat_ticks):
        return [(t0, 0), (t0 + rmp, amp), (t0 + rmp + flat_ticks, amp), (t0 + 2 * rmp + flat_ticks, 0)], \
            t0 + 2 * rmp + flat_ticks

    gsr = C.gs_on * D.gs_var_rescale
    corr, _ = D.phase_corr_table(pos)
    f_slice = D.slice_freq[pos]
    phase_90 = D.aqphase(no_acq) * D.deg_90                                  # PPL:2295
    phase_180 = phase_90 + D.phase_180

    # ---- 90 excitation (PPL:1721-1738, 3414-3487) --------------------------
    rf90 = (C.tramp + C.rfdelay) * us                 # RF start = end of ramp + rfdelay (PPL:3423-3425)
    t_cont = rf90 + D.tsel90 * us - rfd               # MR3040_CONTINUE (PPL:3443-3445)
    neg, t_end_exc = trap(t_cont + rmp, -(C.gs_on * D.gs_rp), q(D.tref))
    T.g['s'].append([(0, 0), (rmp, gsr), (t_cont, gsr), (t_cont + rmp, 0)] + neg[1:])
    zeros = rmp if C.sim_zeros_frame_us is None else C.sim_zeros_frame_us * us
    negr, _ = trap(t_cont + zeros, -(C.gr_on * D.G1), q(D.tref))
    T.g['r'].append(negr)
    # Keep the experimental excitation offset out of phase_90: phase_180 and
    # receiver phase must continue to follow the original PPL phase cycle.
    T.rf.append(dict(kind='exc', start=rf90, dur=D.tsel90 * us, flip=D.flip90,
                     phase=phase_90 + D.excitation_phase_offset, freq=f_slice))
    c90 = rf90 + D.tsel90 * us // 2

    # ---- RF / echo centres (balance equations) -----------------------------
    L = C.views_per_seg
    c180 = [c90 + C.te * 500 * us + C.post_90_delay1 * us]       # PPL:3471 (te/2 + post_90_delay1)
    adc_c = [c180[0] + C.te * 500 * us]                          # PPL:3656
    for _ in range(1, L):
        c180.append(adc_c[-1] + C.esp * 500 * us)                # PPL:3790
        adc_c.append(c180[-1] + C.esp * 500 * us)                # PPL:2763, 3675

    fix = rfd if (C.sim_fix_refocus_centering and C.crush_independent_on == 1) else 0
    lobe = (C.sm_delta + C.tramp) * us                           # Start, delay(sm_delta), Continue, ramp

    # ---- refocusing pulses (PPL:1740-1770, 3530-3601) ----------------------
    lobe2_start = None
    for k, c in enumerate(c180):
        first = (k == 0)
        this_tcrush = D.tcrush1_play if first else D.tcrush_play
        rf_start = c - D.tsel180 * us // 2
        S = rf_start - (this_tcrush + C.tramp + C.rfdelay) * us - fix          # PPL:3543
        tc = C.diff_tcrush if first else C.tcrush
        if C.crush_independent_on == 1:
            # The two crusher matrices are loaded at PPL:3080/3089 and selected
            # for playback at the refocusing-list switch (PPL:3737).  Each RF
            # therefore uses one signed DAC value symmetrically on both sides.
            camp = C.gs_on * D.train_crusher_amplitudes_dac[k]
            a, t = trap(S, camp, q(tc))
            b, t = trap(t, gsr, q(D.crush_rf_flat))
            cc, t = trap(t, camp, q(tc))
            seg = a + b[1:] + cc[1:]
        else:
            seg, t = trap(S, gsr, q(D.tsel90 + 2 * tc))                         # PPL:1749, 1769
        T.g['s'].append(seg)
        rf_end = rf_start + D.tsel180 * us
        wait = (C.tramp + this_tcrush - C.rfdelay + D.crush_post_pad - D.crush_pre_pad) * us   # PPL:3596
        # Relative per-echo offsets augment the existing phase expressions at
        # PPL:3459/3786; they do not alter excitation or receiver phase.
        ph = ((phase_180 - C.phcor0) if first else (phase_180 + corr[k])) \
            + D.refocus_phase_offsets[k]
        T.rf.append(dict(kind='ref', start=rf_start, dur=D.tsel180 * us, flip=D.flip180, phase=ph,
                         freq=f_slice, list_start=S, list_end=t))
        if first:
            l1_end = S - D.extra_side_ticks                                     # PPL:3519-3526
            lobe2_start = rf_end + wait + D.extra_side_ticks - fix              # PPL:3603-3616
            T.l1 = (l1_end - lobe, l1_end)
            T.l2 = (lobe2_start, lobe2_start + lobe)
            dr, dp, ds = D.diff_rps[row]
            for st in (l1_end - lobe, lobe2_start):
                for ax, v in (('r', -dr), ('p', -dp), ('s', -ds)):              # diff_mat (-s,-p,-r), PPL:3094
                    if v:
                        T.g[ax].append([(st, 0), (st + rmp, v), (st + C.sm_delta * us, v), (st + lobe, 0)])
            if T.l1[0] < t_end_exc:
                raise PPLAbort('Diffusion lobe 1 overlaps the excitation rephaser')

    # ---- readouts (PPL:3630-3780) -----------------------------------------
    read_end = []
    for k, ac in enumerate(adc_c):
        adc_start = ac - D.tacq_2 * us
        R = adc_start - (3 * C.tramp + D.tdp + C.rfdelay) * us                 # PPL:3700, 3726
        gp_mul = gp_mul_list[k]
        nav_cnt = 0 if nav else 1
        gp_var = (-D.gp_inc * gp_mul) * nav_cnt                                 # PPL:3570
        a, t = trap(R, -(C.gr_on * D.gr_dp), q(D.tdp))
        b, t = trap(t, D.read_amp, q(D.tacq))
        cc, t = trap(t, -(C.gr_on * D.gr_dp), q(D.tdp))
        T.g['r'].append(a + b[1:] + cc[1:])
        read_end.append(t)
        mid = q(C.tramp) + q(D.tacq) + q(C.tramp)                                # DELAYs, PPL:1799-1801
        for ax, v_pre, v_post in (('p', -C.gp_on * gp_var, C.gp_on * gp_var),
                                  ('s', C.gs_on * D.gsp_rp, C.gs_on * D.gsp_rp)):
            if v_pre or v_post:
                a, t2 = trap(R, v_pre, q(D.tdp))
                b, _ = trap(t2 + mid, v_post, q(D.tdp))
                T.g[ax].append(a + [(t2 + mid, 0)] + b[1:])
        phase_rec = tmod(D.fov_phase_deg[pos] * gp_mul, D.deg_360) * nav_cnt if C.gp_on else 0
        T.adc.append(dict(start=adc_start, n=C.no_samples + C.no_discard, dwell=C.sample_period,
                          phase=phase_rec + corr[k], freq=D.read_freq[pos] + C.rec_freq,
                          echo=k + 1, gp_mul=gp_mul, nav=nav))
        if k == 0 and T.l2[1] > R:
            raise PPLAbort('Diffusion lobe 2 overlaps the first readout')
        if k + 1 < L and t > T.rf[k + 2]['list_start']:
            raise PPLAbort('Readout overlaps the next refocusing list')

    # ---- post-train crusher (PPL:3939-3950) --------------------------------
    T.t_end = read_end[-1]
    if C.post_crush_on:
        t0 = read_end[-1] + C.sim_post_crush_gap_us * us
        for ax, on in (('s', C.gs_on), ('p', C.gp_on), ('r', C.gr_on)):
            pts, T.t_end = trap(t0, -on * C.post_crush_amp, q(C.post_tcrush))
            if on:
                T.g[ax].append(pts)
    T.c90, T.c180, T.adc_c = c90, c180, adc_c
    return T


# =============================================================================
# 4. LOOP STRUCTURE (PPL:2080-4055), emulated statement by statement
# =============================================================================
def emulate_loops(C, D):
    """List of slot dicts in time order (one per slice train)."""
    slots = []
    batch = D.batch_slices
    order = C.sim_slice_order or list(range(C.no_slices))
    completed_ex = 0
    disacq_cnt = 0
    while True:                                           # experiment_loop
        tr = D.tr_for(completed_ex)                       # PPL:2091-2095
        diff_acq_cnt = 0
        while True:                                       # diff_acq_loop
            image_av = 0
            while True:                                   # averages_loop
                sbs = 0
                while True:                               # slice_batch_loop
                    while True:                           # disacq_loop
                        current_view = 0
                        nav_cnt = 0 if C.nav_on == 1 else 1
                        restart = False
                        while True:                       # phase_encode_loop
                            view_av = 0
                            while True:                   # view_block_loop
                                cs = sbs
                                while True:               # multislice_loop
                                    cs += 1
                                    slots.append(dict(
                                        pos=order[cs - 1], slice_idx=cs - 1, batch_start=sbs,
                                        last_in_batch=(cs == sbs + batch),
                                        shot=current_view // C.views_per_seg, view=current_view,
                                        nav=(nav_cnt == 0), row=diff_acq_cnt, rep=completed_ex,
                                        dummy=(disacq_cnt < C.no_disacq), no_acq=view_av + image_av,
                                        image_av=image_av, view_av=view_av, tr=tr))
                                    if cs < sbs + batch:
                                        continue
                                    break
                                disacq_cnt += 1
                                if disacq_cnt <= C.no_disacq:
                                    restart = True
                                    break
                                disacq_cnt = C.no_disacq
                                view_av += 1
                                if view_av < C.view_block:
                                    continue
                                break
                            if restart:
                                break
                            current_view += C.views_per_seg
                            nav_cnt = 1
                            if current_view < C.no_views:
                                continue
                            break
                        if restart:
                            continue
                        break
                    sbs += batch
                    if sbs < C.no_slices:
                        continue
                    break
                image_av += C.view_block
                if image_av < C.no_averages:
                    continue
                break
            completed_ex += 1
            diff_acq_cnt += 1
            if diff_acq_cnt < C.no_diff_acq:
                continue
            break
        if completed_ex < C.no_experiments:
            continue
        break
    for s in slots:                                       # slot duration (PPL:2929, 3955-3983)
        if C.slice_clustering_on == 0:
            s['dur_us'] = (s['tr'] * 1000) // batch
        else:
            ext = s['tr'] - (D.tr_min_us // 1000 + C.interslice_delay) * batch if s['last_in_batch'] else 0
            s['dur_us'] = D.tr_min_us + max(ext, 0) * 1000
    return slots


def reduce_slots(C, D, slots):
    """Keep whole slice-batch passes matching the reduced selection."""
    shots = C.sim_reduced_shots
    if shots is None:
        shots = [1 if C.nav_on == 1 else 0]
    rows = C.sim_reduced_rows
    if rows is None:
        rows = [next((i for i, b in enumerate(C.acq_b[:C.no_diff_acq]) if b > 0), 0)] \
            if C.b_input_mode == 1 else [next((i for i, g in enumerate(D.diff_grad) if g > 1), 0)]
    keep = C.sim_reduced_slices
    if keep is None:
        keep = [C.no_slices // 2]
    groups, cur = [], []
    for s in slots:
        cur.append(s)
        if s['last_in_batch']:
            groups.append(cur)
            cur = []
    out = []
    dummy_proto = next(g for g in groups if g[0]['dummy']) if C.no_disacq > 0 else \
        next(g for g in groups if g[0]['nav'] or g[0]['shot'] == 0)
    sel = [g for g in groups if not g[0]['dummy'] and g[0]['image_av'] == 0 and g[0]['view_av'] == 0
           and g[0]['row'] in rows and g[0]['shot'] in shots and any(s['pos'] in keep for s in g)]
    if not sel:
        raise PPLAbort(f'reduced selection matches nothing: rows {rows}, shots {shots}, slices {keep}')
    for _ in range(C.sim_reduced_n_dummy):
        g = [dict(s, row=sel[0][0]['row'], dummy=True) for s in dummy_proto]
        out.append(g)
    out += sel
    flat = []
    for g in out:
        for s in g:
            if s['pos'] in keep:
                flat.append(s)
            elif C.sim_reduced_keep_slots:
                flat.append(dict(s, skip=True))
    return flat, dict(rows=rows, shots=shots, slices=keep)


# =============================================================================
# 5. PULSEQ OUTPUT
# =============================================================================
def make_system(C, raster):
    G0 = C.grad_var[0] * 1000.0
    return pp.Opts(
        max_grad=C.hw_max_grad_hz_per_m or G0, grad_unit='Hz/m',
        max_slew=C.hw_max_slew_hz_per_m_per_s or G0 / 100e-6, slew_unit='Hz/m/s',
        grad_raster_time=raster, rf_raster_time=raster, adc_raster_time=TICK,
        block_duration_raster=raster, gamma=C.hw_gamma_hz_per_t,
        rf_dead_time=C.hw_rf_dead_time_us * 1e-6, rf_ringdown_time=C.hw_rf_ringdown_time_us * 1e-6,
        adc_dead_time=C.hw_adc_dead_time_us * 1e-6,
    )


def make_rf(C, ev, system, delay_s):
    ph = ev['phase'] * PHASE_RES / 1000.0 * math.pi / 180.0
    use = 'excitation' if ev['kind'] == 'exc' else 'refocusing'
    dur = ev['dur'] * TICK
    if C.sim_rf_shape_file:
        w = np.loadtxt(C.sim_rf_shape_file).astype(float).ravel()
        n = int(round(dur / system.rf_raster_time))
        w = np.interp((np.arange(n) + 0.5) / n, np.linspace(0, 1, len(w)), w)
        return pp.make_arbitrary_rf(signal=w, flip_angle=math.radians(ev['flip']), system=system,
                                    delay=delay_s, phase_offset=ph, freq_offset=float(ev['freq']), use=use)
    frame, d_us, bw = RF_TABLE[C.rfnum]
    if 'sinc' not in frame:
        raise PPLAbort(f'rfnum {C.rfnum} ({frame}) is not a sinc frame; give sim_rf_shape_file')
    n = int(round(dur / system.rf_raster_time))
    w = sinc_frame(C.rfnum, n, C.sim_rf_model, C.sim_rf_apodization, rf_bw_fraction(C))
    return pp.make_arbitrary_rf(signal=w, flip_angle=math.radians(ev['flip']), system=system,
                                delay=delay_s, phase_offset=ph, freq_offset=float(ev['freq']), use=use)


def rf_bw_fraction(C):
    return C.sim_rf_bw_fraction if C.sim_rf_bw_fraction is not None else 71 / 100   # bw_override, PPL:1327


def rf_label(C, D):
    if C.sim_rf_shape_file:
        return str(C.sim_rf_shape_file)
    apo = f'_apod{C.sim_rf_apodization:g}' if C.sim_rf_apodization else ''
    return f'{D.rf_frame}_{C.sim_rf_model}{apo}'


def slice_profiles(C, D):
    """FWHM [mm] of the 90, 180 and spin-echo slice profiles at the PPL slice gradient."""
    if C.sim_rf_shape_file:
        return None
    s = profile_summary(C.rfnum, C.sim_rf_model, C.sim_rf_apodization, D.flip180, rf_bw_fraction(C))
    g_hz_mm = abs(D.gs_var_rescale) / DACMAX * D.G0
    return {k: s['fwhm_' + k] / g_hz_mm for k in ('exc', 'ref', 'se')}


def train_blocks(C, D, T, gd):
    """Split a train into [(start_tick, end_tick, grads{axis:[(t,a)]}, rfs, adcs)]."""
    iv = []
    for ax in T.g:
        for s in T.g[ax]:
            iv.append((s[0][0] + gd, s[-1][0] + gd))
    for ev in T.rf:
        iv.append((ev['start'], ev['start'] + ev['dur']))
    for ev in T.adc:
        iv.append((ev['start'], ev['start'] + ev['n'] * ev['dwell']))
    iv.sort()
    merged = []
    for a, b in iv:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    blocks = []
    for a, b in merged:
        grads = {}
        for ax in T.g:
            pts = []
            for s in T.g[ax]:
                if a <= s[0][0] + gd and s[-1][0] + gd <= b:
                    pts += [(t + gd - a, v) for t, v in s]
            pts.sort(key=lambda x: x[0])
            clean = []
            for t, v in pts:
                if clean and clean[-1][0] == t:
                    if clean[-1][1] != 0 or v != 0:
                        raise PPLAbort(f'overlapping gradient lists on axis {ax}')
                    continue
                clean.append((t, v))
            if any(v for _, v in clean):
                grads[ax] = clean
        rfs = [dict(ev, d=ev['start'] - a) for ev in T.rf if a <= ev['start'] < b]
        adcs = [dict(ev, d=ev['start'] - a) for ev in T.adc if a <= ev['start'] < b]
        blocks.append((a, b, grads, rfs, adcs))
    return blocks


def build_sequence(C=None, reduced=False, ppr=None, overrides=None):
    if C is None:
        C = load_params(ppr, overrides)
    D = derive(C)
    slots = emulate_loops(C, D)
    sel = None
    if reduced:
        slots, sel = reduce_slots(C, D, slots)
    gd = int(round(C.hw_grad_delay_us * 10))
    pre90 = C.sim_pre90_us * 10

    # build every train first (ticks), then pick the raster
    plan = []
    cache = {}
    for s in slots:
        if s.get('skip'):
            plan.append((s, None, None))
            continue
        gp = D.gp_order[s['view']:s['view'] + C.views_per_seg]
        key = (s['view'], s['nav'], s['row'], s['pos'], s['no_acq'])
        if key not in cache:
            T = build_train(C, D, gp, s['nav'], s['row'], s['pos'], s['no_acq'])
            cache[key] = (T, train_blocks(C, D, T, gd))
        T, blocks = cache[key]
        end = max(blocks[-1][1], T.t_end + gd)
        if pre90 + end > s['dur_us'] * 10:
            raise PPLAbort('Train does not fit in its TR slot')
        plan.append((s, T, blocks))
    ticks = {pre90}
    for s, T, blocks in plan:
        ticks.add(s['dur_us'] * 10)
        for a, b, grads, rfs, adcs in blocks or []:
            ticks |= {a, b}
            for pts in grads.values():
                ticks |= {t for t, _ in pts}
            ticks |= {r['d'] for r in rfs} | {r['dur'] for r in rfs}
    raster = 1e-6 if all(t % 10 == 0 for t in ticks) else 1e-7
    system = make_system(C, raster)
    seq = pp.Sequence(system)
    dac2hz = C.grad_var[0] * 1000.0 / DACMAX
    axis = {'r': 'x', 'p': 'y', 's': 'z'}
    log, t_abs = [], 0
    for s, T, blocks in plan:
        if T is None:
            seq.add_block(pp.make_delay(s['dur_us'] * 1e-6))
            t_abs += s['dur_us'] * 10
            continue
        seq.add_block(pp.make_delay(pre90 * TICK))
        cur = 0
        for a, b, grads, rfs, adcs in blocks:
            if a > cur:
                seq.add_block(pp.make_delay((a - cur) * TICK))
            ev = []
            for ax, pts in grads.items():
                ev.append(pp.make_extended_trapezoid(channel=axis[ax],
                                                     times=np.array([p[0] for p in pts]) * TICK,
                                                     amplitudes=np.array([p[1] for p in pts], float) * dac2hz,
                                                     system=system))
            for r in rfs:
                ev.append(make_rf(C, r, system, r['d'] * TICK))
            if not s['dummy']:
                for r in adcs:
                    ph = r['phase'] * PHASE_RES / 1000.0 * math.pi / 180.0
                    ev.append(pp.make_adc(num_samples=r['n'], dwell=r['dwell'] * TICK, delay=r['d'] * TICK,
                                          phase_offset=ph, freq_offset=float(r['freq']), system=system))
                    lin = 0 if r['nav'] else r['gp_mul'] + D.no_views_eff // 2
                    ev += [pp.make_label(type='SET', label='LIN', value=int(lin)),
                           pp.make_label(type='SET', label='ECO', value=r['echo'] - 1),
                           pp.make_label(type='SET', label='NAV', value=bool(r['nav'])),
                           pp.make_label(type='SET', label='SLC', value=s['pos']),
                           pp.make_label(type='SET', label='REP', value=s['rep']),
                           pp.make_label(type='SET', label='AVG', value=s['image_av'])]
            ev.append(pp.make_delay((b - a) * TICK))
            seq.add_block(*ev)
            cur = b
        seq.add_block(pp.make_delay((s['dur_us'] * 10 - pre90 - cur) * TICK))
        log.append(dict(s, t0=t_abs, train=T))
        t_abs += s['dur_us'] * 10

    # ---- definitions -------------------------------------------------------
    rows = sel['rows'] if reduced else list(range(C.no_diff_acq))
    thk = DACMAX * D.pulse_bwdth / (abs(D.gs_var_rescale) * D.G0)
    unresolved = any(not D.phase_corr_table(p)[1] for p in {s['pos'] for s, T, _ in plan if T})
    seq.set_definition('Name', 'dwfse_ppl_twoTE_1_6' + ('_reduced' if reduced else ''))
    seq.set_definition('FOV', [C.fov_mm * 1e-3, C.fov_mm * 1e-3 * D.gp_oversample / D.gp_undersample, thk * 1e-3])
    seq.set_definition('TE', C.te * 1e-3)
    seq.set_definition('EchoSpacing', C.esp * 1e-3)
    seq.set_definition('ETL', C.views_per_seg)
    seq.set_definition('PEOrder', C.PE_order)
    seq.set_definition('KCentreEcho', D.pe_center_echo)
    seq.set_definition('TR', slots[0]['tr'] * 1e-3)
    seq.set_definition('SliceThickness', thk * 1e-3)
    seq.set_definition('bValuesRequested', [float(C.acq_b[r]) for r in rows])
    seq.set_definition('bValuesPPLNominal', [float(D.acq_b_nominal[r]) for r in rows])
    seq.set_definition('DiffusionDAC', [float(D.diff_grad[r]) for r in rows])
    seq.set_definition('DiffusionDirectionsRPS', sum([[C.acq_x[r] / 1e3, C.acq_y[r] / 1e3, C.acq_z[r] / 1e3]
                                                      for r in rows], []))
    seq.set_definition('SmallDelta', C.sm_delta * 1e-6)
    seq.set_definition('BigDelta', C.big_delta * 1e-6)
    seq.set_definition('ExcitationFlipDeg', D.flip90)
    seq.set_definition('RefocusFlipDeg', D.flip180)
    seq.set_definition('ExcitationPhaseOffsetDeg', D.excitation_phase_offset_deg)
    seq.set_definition('RefocusPhaseOffsetsDeg', D.refocus_phase_offsets_deg)
    if D.train_crusher_amplitudes_dac is not None:
        seq.set_definition('TrainCrusherAmplitudesDAC', D.train_crusher_amplitudes_dac)
    seq.set_definition('RFShape', rf_label(C, D))
    prof = slice_profiles(C, D)
    if prof:
        seq.set_definition('SliceFWHM_mm_exc_ref_SE', [round(prof[k], 4) for k in ('exc', 'ref', 'se')])
    seq.set_definition('GradientDelay_us', C.hw_grad_delay_us)
    seq.set_definition('RefocusCentering', 'fixed' if C.sim_fix_refocus_centering else 'as_PPL_v1.6')
    seq.set_definition('OffsetSlicePhaseCorr', 'NOT_APPLIED_acqpad_unknown' if unresolved else 'applied_or_not_needed')
    seq.set_definition('AxisMap', 'x=read y=phase z=slice (logical)')
    seq.set_definition('Reduced', int(reduced))
    if unresolved:
        warnings.warn('Off-centre slice phase correction NOT applied (sim_acqpad_ticks unknown).')
    return seq, C, D, log


def report(C, D):
    """Like the PPL's report_on output plus the derived set-up values."""
    lines = [f'PARSETUP differences vs PPR: {D.parsetup_diffs or "none"}']
    lines += D.warnings
    lines += [f'Minimum TE = {D.min_te} us; Minimum esp = {D.min_esp_us // 1000 + 1} ms ({D.min_esp_us} us); '
              f'Minimum TR = {D.min_tr_ms} ms (tr_min per slice {D.tr_min_us} us)',
              f'gs_var_rescale {D.gs_var_rescale}, gs_rp {D.gs_rp}, gsp_rp {D.gsp_rp}, grp_dp {D.grp_dp}, '
              f'gr_dp {D.gr_dp}, read {D.read_amp}, gp_inc {D.gp_inc}',
              f'crush pads pre/post {D.crush_pre_pad}/{D.crush_post_pad} us, RF plateau {D.crush_rf_flat} us, '
              f'extra_delta {D.extra_delta} us',
              f'p90_mul {D.p90_mul}, p180_mul {D.p180_mul}; flips {D.flip90:.2f}/{D.flip180:.2f} deg',
              f'max b = {D.b_max} s/mm^2']
    prof = slice_profiles(C, D)
    thk = DACMAX * D.pulse_bwdth / (abs(D.gs_var_rescale) * D.G0)
    if prof:
        lines.append(f'RF {rf_label(C, D)}: slice FWHM 90 {prof["exc"]:.2f} mm, 180 {prof["ref"]:.2f} mm, '
                     f'spin echo {prof["se"]:.2f} mm (PPL nominal {thk:.2f} mm)')
    for i in range(C.no_diff_acq):
        lines.append(f'row {i}: b req {C.acq_b[i]}, DAC {D.diff_grad[i]}, nominal b {D.acq_b_nominal[i]}, '
                     f'dir ({C.acq_x[i]},{C.acq_y[i]},{C.acq_z[i]})')
    lines.append(f'zero-PE echo {D.pe_center_echo}: TE {C.te + (D.pe_center_echo - 1) * C.esp} ms')
    return '\n'.join(lines)


def params_dict(C):
    """JSON-friendly parameter dump (large unused arrays dropped)."""
    return {k: v for k, v in vars(C).items() if not k.startswith('mtc_freq_array')}

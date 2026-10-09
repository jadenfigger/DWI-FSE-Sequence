"""Additive decoded-waveform isolated refocusing study; never a train validation.

Run from the repository: python examples/v181_refocus_width_study.py
All RF scaling is the repository's integral-normalized model, not scanner B1.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace

import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse.ppl.bloch import rf_calibration_hz_per_unit
from dwfse.ppl.events import gradient_pwc
from dwfse.ppl.ledger import build_ledger, list_starts, list_duration_us, dac_us_to_cyc_m
from dwfse.vendor_seq import decode
from examples import v19_validate_events as old

OUT = ROOT / 'docs/v181_v1911'


def transfer(amplitude_hz, dt_s, offset_hz, phase_deg):
    """Rows are output magnetization for independent x/y/z input vectors."""
    off = np.atleast_1d(offset_hz)
    state = np.broadcast_to(np.eye(3), (len(off), 3, 3)).copy()
    p = np.deg2rad(phase_deg)
    for a in amplitude_hz:
        b = np.column_stack((np.full(len(off), a*np.cos(p)),
                             np.full(len(off), a*np.sin(p)), off))
        norm = np.linalg.norm(b, axis=1)
        n = b / np.where(norm > 0, norm, 1)[:, None]
        theta = -2*np.pi*norm*dt_s
        c, s = np.cos(theta)[:, None, None], np.sin(theta)[:, None, None]
        state = state*c + np.cross(n[:, None, :], state)*s + np.sum(
            state*n[:, None, :], axis=-1)[..., None]*n[:, None, :]*(1-c)
    return state


def conjugate_coherence(t):
    # m_out = c_direct*m_in + c_conjugate*conj(m_in) + c_z*Mz_in.
    a = t[:, 0, 0] + 1j*t[:, 0, 1]
    b = t[:, 1, 0] + 1j*t[:, 1, 1]
    return (a + 1j*b)/2


def checks(amplitude_hz, dt_s):
    errors = []
    for flip in (30., 90., 166.3636363636, 180.):
        for p in (0., 37., 270.):
            t = transfer(np.array([flip/360/dt_s]), dt_s, [0.], p)
            expected = np.sin(np.deg2rad(flip)/2)**2
            errors.append(abs(abs(conjugate_coherence(t)[0])-expected))
            assert np.max(abs(t@t.transpose(0, 2, 1)-np.eye(3))) < 1e-12
    ode_errors = []
    for offset in (0., 128., 1192.3):
        result = transfer(amplitude_hz*.8, dt_s, [offset], 270.)[0]
        state = np.eye(3)
        for a in amplitude_hz*.8:
            bx, by, bz = 2*np.pi*np.array([0., -a, offset])
            mat = np.array([[0., bz, -by], [-bz, 0., bx], [by, -bx, 0.]])
            sol = solve_ivp(lambda _, y: (y.reshape(3, 3)@mat.T).ravel(),
                            [0., dt_s], state.ravel(), method='DOP853',
                            rtol=1e-10, atol=1e-12)
            state = sol.y[:, -1].reshape(3, 3)
        ode_errors.append(float(np.max(abs(result-state))))
    assert max(errors) < 1e-12 and max(ode_errors) < 1e-9
    return {'hard_pulse_analytic_max_error': max(errors),
            'independent_piecewise_ODE_offsets_hz': [0., 128., 1192.3],
            'independent_piecewise_ODE_max_component_errors': ode_errors}


def isolated_selector(it):
    # Retain only primary slice matrices21/22, suppress all other terms. This
    # preserves decoded raster/ramp and real matrix selection times.
    g = deepcopy(it.grad)
    g.mats = {k: [tuple([d[0], d[1], d[2] if k in (21, 22) else 0, *d[3:]])
                  for d in definitions] for k, definitions in g.mats.items()}
    return gradient_pwc(SimpleNamespace(grad=g), 'S')[0]


def raw_stock_check(path, stock):
    raw = path.read_bytes()
    kind, n, _ = struct.unpack_from('<BHH', raw)
    assert kind == 6
    for ptr in struct.unpack_from('<'+'I'*n, raw, 5):
        wait, words, name_len, name_ptr, record_ptr = struct.unpack_from('<HHBII', raw, ptr)
        name = raw[name_ptr:name_ptr+name_len-1].decode('ascii')
        if name == stock.name:
            rec = np.frombuffer(raw[record_ptr:record_ptr+4*words], '<u2').reshape(-1, 4)
            signed = (rec[:, 0] & 4095).astype(int)
            signed[signed >= 2048] -= 4096
            assert np.array_equal(signed, stock.samples) and wait == stock.wait_ticks
            assert np.array_equal(signed[1:-1], np.rint(2047*np.sinc((np.arange(666)-333)*2/333)))
            return {'sha256': hashlib.sha256(raw).hexdigest(), 'independent_raw_decode_match': True,
                    'independent_quantized_sinc_formula_match': True}
    raise AssertionError('missing stock frame')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    it = old.mapping(old.V18, old.CTRL_PPR)
    led = build_ledger(it)
    excitation, refocus = led['rf'][:2]
    stock_path = ROOT/'scanner/utilities/rfstd44.seq'
    stock = decode(stock_path).frame('3lobe_sinc_3kHz')
    cal = rf_calibration_hz_per_unit(stock.samples, stock.wait_ticks/10, it.vars['rfcal'].value)
    amp = refocus['amp']*cal
    dt = refocus['dt']*1e-6
    selector = int(it.vars['gs_var_rescale'].value)
    k = led['H']*1000/32767
    z = np.linspace(-.0015, .0015, 1201)
    nominal = abs(z) <= .0005
    edge = (abs(z) >= .00035) & nominal
    center = abs(z) <= .00025
    data = []
    for b1 in (.8, 1., 1.1):
        for b0 in (-128., 0., 128.):
            e = transfer(excitation['amp']*cal*b1, excitation['dt']*1e-6,
                         selector*k*z+b0, excitation['phase_deg'])
            weight = abs(e[:, 2, 0]+1j*e[:, 2, 1])
            for ratio in (1., 1.2, 1.5):
                gz = int(selector/ratio)  # PPL signed integer truncation
                t = transfer(amp*b1, dt, gz*k*z+b0, refocus['phase_deg'])
                efficiency = abs(conjugate_coherence(t))
                data.append(dict(b1=b1, b0_hz=b0, spatial_width_requested=ratio,
                    selector_DAC=gz, spatial_width_achieved=selector/gz,
                    nominal_slice_mean_conjugate_transfer=float(np.mean(efficiency[nominal])),
                    nominal_slice_min_conjugate_transfer=float(np.min(efficiency[nominal])),
                    edge_mean_conjugate_transfer=float(np.mean(efficiency[edge])),
                    center_mean_conjugate_transfer=float(np.mean(efficiency[center])),
                    excitation_weighted_isolated_refocus=float(np.sum(weight[nominal]*efficiency[nominal])/np.sum(weight[nominal])),
                    scope='Magnitude of isolated m-to-conjugate(m) transfer; no train, relaxation, molecular diffusion or coherent spatial averaging.'))
    w = isolated_selector(it)
    starts = list_starts(it, led, 'slice_180_refocus_diff') + list_starts(it, led, 'slice_180_refocus')
    compensation = []
    for j, (p, (start, _)) in enumerate(zip(led['rf'][1:], starts)):
        end = start + list_duration_us(it, 'slice_180_refocus_diff' if j == 0 else 'slice_180_refocus')
        before = w.integral(start, p['t_center'])
        after = w.integral(p['t_center'], end)
        for ratio in (1.2, 1.5):
            scale = int(selector/ratio)/selector
            compensation.append(dict(refocus_index=j+1, requested_width=ratio,
                selector_pre_DAC_us=before, selector_post_DAC_us=after,
                required_added_pre_DAC_us=before*(1-scale), required_added_post_DAC_us=after*(1-scale),
                uncompensated_desired_path_delta_cycles_per_m=dac_us_to_cyc_m((after-before)*(scale-1), led['H']),
                note='Restores geometric-center interval areas only. Finite RF transfer changed intentionally; this is not an exact pathway-equivalence proof.'))
    linked = old.mapping(old.V18, old.CTRL_PPR, overrides={'crush_independent_on': 0})
    ll = build_ledger(linked)
    linked_areas = []
    for j, (p, (start, _)) in enumerate(zip(ll['rf'][1:], list_starts(linked, ll, 'slice_180_refocus_diff')+list_starts(linked, ll, 'slice_180_refocus'))):
        end = start + list_duration_us(linked, 'slice_180_refocus_diff' if j == 0 else 'slice_180_refocus')
        linked_areas.append(dict(refocus_index=j+1, before_DAC_us=ll['G']['S'].integral(start,p['t_center']),
                                 after_DAC_us=ll['G']['S'].integral(p['t_center'],end)))
    result = {'scope': 'Actual archived v1.8 source mapping and stock RF, isolated finite refocus transfer study. Not a full train or scanner qualification.',
        'baseline_inputs': it.inputs, 'raw_RF_check': raw_stock_check(stock_path, stock),
        'mathematical_checks': checks(amp, dt),
        'actual_RF': {'full_records': len(amp), 'nonzero_transmitted_records': int(np.count_nonzero(amp)),
            'dwell_us':refocus['dt'], 'multiplier':refocus['mul'], 'nominal_integral_flip_deg':float(360*np.sum(amp)*dt),
            'energy_model_Hz2_s':float(np.sum(amp**2)*dt), 'energy_width_ratio':1.,
            'calibration':'Stock signed integral at multiplier594 is90degrees; inferred relative scaling, not achieved scanner flip.'},
        'spatial_geometry': {'nominal_excited_slice_mm':1., 'edge_region_abs_mm':[.35,.5],
            'center_region_abs_mm':[0.,.25], 'sample_grid_mm':[-1.5,1.5], 'points':len(z)},
        'profiles':data, 'geometric_center_compensation':compensation,
        'frequency': [{'width':r, 'selector_DAC':int(selector/r),
            'offset_frequency_Hz_per_mm':int(selector/r)*led['H']/32767,
            'rule':'Refocus frequency offset must scale by actual refocus/excitation Gz ratio to retain slice center.'} for r in (1.,1.2,1.5)],
        'linked_crusher_baseline_areas':linked_areas,
        'linked_crusher_consequence':'Shared primary gradient contains selection and crushers. Simple selector scaling reduces all crusher areas by16.7% or33.3%, violates preserved-pathway requirement, and is excluded.',
        'implementation_recommendation':'Study supports useful spatial widening, but source must use independent refocus primary matrices, unchanged excitation and separate pre/post compensation. Current symmetric crusher primitive cannot supply both required corrections by a single amplitude change. Nonzero offsets require separate scaled refocus frequency. Do not ship simple selector scaling; require integrated finite-train and moment/pathway review.'}
    (OUT/'refocus_width_study.json').write_text(json.dumps(result, indent=2, default=float)+'\n', encoding='utf-8')
    lines=['# v1.81 isolated finite-waveform refocusing-width study', '', result['scope'], '',
        'The stock RF is decoded from actual vendor bytes and gated through the archived v1.8 source. The excitation gradient is retained. Refocusing-only gradient scaling uses signed integer DAC truncation. RF duration, amplitude and modeled energy are unchanged. No measured B1, power or SAR is inferred.', '',
        '| B1 | B0 Hz | Width | Edge conjugate transfer | Excitation-weighted transfer |',
        '|---:|---:|---:|---:|---:|']
    for row in data:
        lines.append(f"| {row['b1']:.1f} | {row['b0_hz']:.0f} | {row['spatial_width_requested']:.1f} | {row['edge_mean_conjugate_transfer']:.4f} | {row['excitation_weighted_isolated_refocus']:.4f} |")
    lines += ['', 'These are isolated conjugate-coherence coefficients, not complete train signal or an image-quality prediction. They measure how much incoming transverse coherence can enter the refocused conjugate branch. Excitation weighting uses the actual isolated excitation profile, and is an incoherent magnitude diagnostic.', '',
        '## Compensation and implementation', '', result['implementation_recommendation'], '',
        'The complete selector ramp/plateau is asymmetric around the mapped RF center because of inherited RF delay and instruction timing. Scaling only that selector changes effective moment. Geometric-center correction areas for every RF are recorded in the JSON; they are not a finite-RF equivalence claim. A symmetric crusher-amplitude change cannot independently restore these two different areas. Excitation compensation gs_comp/gs_rp must remain unchanged. Refocus phase/offset and compensation must be audited in a complete finite-RF train before packaging.', '',
        result['linked_crusher_consequence'], '',
        'For nonzero slice position the refocus frequency must use the scaled selector; at isocenter both frequencies are zero. A restricted zero-offset independent-crusher implementation can avoid a second frequency buffer, but still needs the two compensation areas and independent timing review.', '',
        '## Independent model checks', '',
        f"Hard-pulse conjugate-transfer identity sin²(flip/2) maximum error: {max(result['mathematical_checks']['hard_pulse_analytic_max_error'],0):.3g}. The piecewise continuous ODE comparison at offsets0,128,1192.3Hz gives maximum component error {max(result['mathematical_checks']['independent_piecewise_ODE_max_component_errors']):.3g}.", '',
        'Raw records independently match the library decoder and the exact quantized stock sinc formula. The source-mapped flip integral is reported explicitly; p180_scale185 does not imply a measured physical180degree pulse.', '',
        'Recommendation: evaluate1.2x first, since1.5x gives more coverage but changes a larger spatial slab and more gradient area. Strong isolated-profile benefit justifies a separately reviewed integrated implementation; this study alone is insufficient for upload.']
    (OUT/'refocus_width_study.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({'rows':len(data), 'check':result['mathematical_checks'], 'nominal_B1_B0_profiles':[r for r in data if r['b1']==1 and r['b0_hz']==0], 'compensation_first':compensation[:2]}, indent=2))


if __name__ == '__main__':
    main()

"""Independent Cartesian and analytic adversarial oracles for pathway audit."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import sys

import numpy as np
from numpy.polynomial.legendre import leggauss

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from examples.v181_v1911_pathway_audit import analyze_pathways, rf_calibration, interval_stats
from dwfse.ppl.events import PWC


def make_it():
    return SimpleNamespace(vars={k: SimpleNamespace(value=v) for k, v in
                           {'rfcal': 594, 'rfdelay': 0, 'no_samples': 2}.items()}, inputs={'synthetic': True})


def make_ledger(it, rf_times, angles, phases, adc_times, edges, gradients):
    cal = rf_calibration(it)
    rf = [{'t_center': t, 'frame': f'synthetic_{i}', 'amp': np.array([a/(2*np.pi*cal*1e-6)]),
           'dt': 1., 'phase_deg': p} for i, (t, a, p) in enumerate(zip(rf_times, angles, phases))]
    adc = [{'t_init': t-1, 'sample_period_ticks': 10, 'discard': 0, 'rx_phase_deg': 0.}
           for t in adc_times]
    return {'H': 32767/1000, 'rf': rf, 'adc': adc,
            'G': {ax: PWC(np.asarray(edges, float), np.asarray(gradients[:, i], float))
                  for i, ax in enumerate('SPR')}}


def cartesian_closure():
    """Coherent box integration versus explicit Cartesian rotations; no RF matrix oracle reuse."""
    it = make_it()
    rf_times = np.arange(7)*4000.
    angles = np.deg2rad([90, 167, 90, 90, 140, 116, 99])
    phases = [17, 93, -71, 13, 89, 97, 77]
    adc_times = rf_times[1:]+1700
    edges = np.arange(0, 30001, 1000.)
    gradients = np.random.default_rng(198181).uniform(-30000, 30000, (30, 3))
    led = make_ledger(it, rf_times, angles, phases, adc_times, edges, gradients)
    widths = np.array([.001, .0008, .0012])
    nodes, weights = leggauss(10)
    grid = np.meshgrid(*(nodes*w/2 for w in widths), indexing='ij')
    xyz = np.stack([v.ravel() for v in grid], axis=1)
    ww = np.prod(np.stack(np.meshgrid(weights/2, weights/2, weights/2, indexing='ij'), axis=-1), axis=-1).ravel()
    worst = 0.
    rows = []
    for df in (-128., 0., 128.):
        for phase0 in (0., 45., 90.):
            path = analyze_pathways(it, led, diffusivity_mm2_s=0, T1_s=.083, T2_s=.047,
                                    df_hz=df, initial_phase_deg=phase0, voxel_widths_m=widths)
            m = np.zeros((len(xyz), 3)); m[:, 2] = 1
            previous = 0.
            actual = []
            events = sorted([(t, 'rf', i) for i, t in enumerate(rf_times)] +
                            [(t, 'adc', i) for i, t in enumerate(adc_times)])
            for t, kind, index in events:
                dt = (t-previous)*1e-6
                area = np.array([led['G'][ax].integral(previous, t)*1e-6 for ax in 'SPR'])
                theta = -2*np.pi*(xyz@area+df*dt)
                trans = (m[:, 0]+1j*m[:, 1])*np.exp(1j*theta)*np.exp(-dt/.047)
                m[:, 0], m[:, 1] = trans.real, trans.imag
                m[:, 2] = 1+(m[:, 2]-1)*np.exp(-dt/.083)
                previous = t
                if kind == 'rf':
                    p = np.deg2rad(phases[index]+(phase0 if index == 0 else 0))
                    axis = np.array([np.cos(p), np.sin(p), 0])
                    a = angles[index]
                    m = m*np.cos(a)-np.cross(axis, m)*np.sin(a)+(m@axis)[:, None]*axis*(1-np.cos(a))
                else:
                    actual.append(np.sum((m[:, 0]+1j*m[:, 1])*ww))
            expected = np.array([complex(*e['signal_real_imag']) for e in path['echoes']])
            error = float(np.max(np.abs(np.array(actual)-expected)))
            worst = max(worst, error)
            rows.append({'B0_Hz': df, 'excitation_phase_deg': phase0, 'maximum_complex_error': error})
    assert worst < 1e-10, worst
    return {'pass': True, 'max_error': worst, 'cases': rows,
            'scope': 'Independent real Cartesian rotations, B0 signs, box averaging, all RF branches, T1 recovery and T2; diffusion disabled.'}


def stored_z_diffusion():
    it = make_it()
    edges = [0., 1000., 51000., 52000.]
    g = 20e6
    led = make_ledger(it, [0., 1000., 51000.], np.deg2rad([90., 90., 90.]), [0., 90., 0.],
                      [52000.], edges, np.array([[g, 0, 0], [0, 0, 0], [-g, 0, 0]]))
    result = analyze_pathways(it, led, diffusivity_mm2_s=.002, T1_s=None, T2_s=None,
                              voxel_widths_m=[0., 0., 0.], top=100)
    stored = next(p for p in result['echoes'][0]['top_paths'] if p['history'] == '+ Z +')
    kval = g*.001
    # First lobe builds k linearly, storage holds it, last lobe erases it.
    b_expected = (2*np.pi)**2 * kval**2 * (.001/3+.05+.001/3)*1e-6
    error = abs(stored['b_trace_s_mm2']-b_expected)
    assert error < 1e-9, error
    assert np.linalg.norm(stored['k_cycles_m']) < 1e-10
    assert abs(stored['diffusion_attenuation']-np.exp(-.002*b_expected)) < 1e-14
    return {'pass': True, 'path': stored, 'analytic_B_s_mm2': b_expected, 'error': error,
            'scope': 'Encoded longitudinal storage with analytic buildup/storage/erase diffusion; not a finite-RF PDE.'}


def polynomial_integration():
    """Independent Gauss integration of q(t)q(t)^T including signed initial wavevector."""
    rng = np.random.default_rng(61181911)
    worst = 0.
    for _ in range(20):
        edges = np.r_[0., np.cumsum(rng.uniform(30, 500, 7))]
        gradients = rng.normal(size=(7, 3))*10000
        led = {'H': 32767/1000, 'G': {ax: PWC(edges, gradients[:, i]) for i, ax in enumerate('SPR')}}
        stats = interval_stats(led, edges[0], edges[-1])
        start = rng.normal(size=3)*80
        for sign in (-1, 0, 1):
            numerical = np.zeros((3, 3)); cur = start.copy()
            for a, b, grad in zip(edges[:-1], edges[1:], gradients):
                dt = (b-a)*1e-6
                for x, w in zip(*leggauss(3)):
                    k = cur+sign*grad*dt*(x+1)/2
                    numerical += np.outer(k, k)*dt*w/2
                cur += sign*grad*dt
            from examples.v181_v1911_pathway_audit import _outer6, _cross6, PAIRS
            formula = stats['dt_s']*_outer6(start)+sign*_cross6(start, stats['int_q_dt'])+(sign != 0)*stats['int_qq_dt']
            expected = np.array([numerical[i, j] for i, j in PAIRS])
            worst = max(worst, float(np.max(np.abs(formula-expected))))
    assert worst < 1e-12, worst
    return {'pass': True, 'max_integral_error': worst, 'coherence_signs': [-1, 0, 1]}


if __name__ == '__main__':
    result = {'pathway_tool_sha256': hashlib.sha256((ROOT/'examples/v181_v1911_pathway_audit.py').read_bytes()).hexdigest(),
              'cartesian_closure': cartesian_closure(), 'stored_Z_diffusion': stored_z_diffusion(),
              'exact_PWC_integration': polynomial_integration()}
    out = Path(__file__).with_suffix('.json')
    out.write_text(json.dumps(result, indent=2)+'\n')
    print(out)

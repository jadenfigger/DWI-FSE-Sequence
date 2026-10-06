"""Independent continuous Bloch ODE check of the existing ss-MGOT preparation."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from examples.compare_prepared_fse import build
from dwfse import simulate


def main():
    seq, info = build('ss_mgot', 45.)
    final = info['reexcitation_block']
    ids, starts, durations = simulate.block_times(seq)
    count = ids.index(final)+1
    t = starts[count-1]+durations[count-1]
    z = np.array([-.0004, 0., .0004])
    y = np.array([0., 1/(4*40000), -1/(4*40000)])
    voxel = dict(x=np.zeros(3), y=y, z=z, df=np.zeros(3))
    actual = simulate.simulate(seq, voxel=voxel, snap_times=[t], max_blocks=final, rf_dt=2e-6)
    m = np.array([np.zeros(3), np.zeros(3), np.ones(3)])
    T1, T2 = 1.5, .08
    for bid, duration in zip(ids[:count], durations[:count]):
        block = seq.get_block(bid)
        gradients = {k:simulate.grad_pts(getattr(block, 'g'+k)) for k in 'xyz'}
        if block.rf is None:
            # Independent integral and free-precession/relaxation solution.
            areas = {k:0 if p is None else float(np.trapezoid(p[1], p[0])) for k,p in gradients.items()}
            angle = -2*np.pi*(areas['y']*y+areas['z']*z)
            xy = (m[0]+1j*m[1])*np.exp(1j*angle-duration/T2)
            m = np.array([xy.real, xy.imag, 1+(m[2]-1)*np.exp(-duration/T1)])
            continue
        rf = block.rf
        def derivative(time, state):
            v = state.reshape(3, 3)
            # Interpolate native RF samples; no Rodrigues rotation or the
            # simulator's RF averaging is used by this independent solver.
            r = time-rf.delay
            bx = np.interp(r, rf.t, rf.signal.real, left=0, right=0)
            by = np.interp(r, rf.t, rf.signal.imag, left=0, right=0)
            b = complex(bx, by)*np.exp(1j*(rf.phase_offset+2*np.pi*rf.freq_offset*r))
            gy = 0 if gradients['y'] is None else np.interp(time, *gradients['y'], left=0, right=0)
            gz = 0 if gradients['z'] is None else np.interp(time, *gradients['z'], left=0, right=0)
            bz = gy*y+gz*z
            return np.array([2*np.pi*(v[1]*bz-v[2]*b.imag)-v[0]/T2,
                             2*np.pi*(v[2]*b.real-v[0]*bz)-v[1]/T2,
                             2*np.pi*(v[0]*b.imag-v[1]*b.real)+(1-v[2])/T1]).ravel()
        solution = solve_ivp(derivative, [0, duration], m.ravel(), method='DOP853',
                             rtol=1e-9, atol=1e-11, max_step=2e-6)
        assert solution.success, solution.message
        m = solution.y[:, -1].reshape(3, 3)
    expected = np.array(actual['snapshots'][0][1:])
    error = float(np.max(abs(m-expected)))
    assert error < 2e-4, error
    result = dict(landmark='after re-excitation and slice compensation', b1=1., phase_deg=45.,
                  positions_y_m=y.tolist(), positions_z_m=z.tolist(),
                  independent_ode=m.tolist(), simulator_2us=expected.tolist(),
                  max_component_error=error,
                  scope='Three spin locations, existing waveform, T1/T2 included; not paper-pulse validation',
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (ROOT/'docs/data/gibbons_bloch_ode_check.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('Independent ODE maximum component difference', error, flush=True)


if __name__ == '__main__': main()

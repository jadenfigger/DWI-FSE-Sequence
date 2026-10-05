"""Static finite-RF imaging qualification, using actual acquired complex ADCs.

python examples/combined_factor_phantom.py
Two actual imaging shots, 16 PE lines, 128 read samples; no molecular motion.
This is a coarse numerical phantom, not scanner image-quality validation.
"""
import argparse
import csv
import json
import sys
import time
from importlib.metadata import version
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.special import j1
from scipy.stats import qmc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dwfse import generate, simulate
from examples.improve_ppl import BASE

RAMP = [1, 1, 1.4, 1.8, 2.2, 2.6, 3, 3.4]
CASES = {
    'original': {},
    'centered_increasing': dict(sim_fix_refocus_centering=True, sim_train_crusher_scales=RAMP),
    'centered_increasing_alternating': dict(sim_fix_refocus_centering=True,
        sim_train_crusher_scales=[v * (-1 if i % 2 else 1) for i, v in enumerate(RAMP)]),
    'centered_weak_ramp': dict(sim_fix_refocus_centering=True,
        sim_train_crusher_scales=[1,1,1.2,1.4,1.6,1.8,2,2.2]),
    'centered_highlow_alternating': dict(sim_fix_refocus_centering=True,
        sim_train_crusher_scales=[1,-1,3.4,-1.4,3,-1.8,2.6,-2.2]),
}
COMPONENTS = [(-.001, 0., .014, .011, 1.), (.007, .003, .003, .003, .8),
              (-.008, -.004, .0006, .0006, 2.)]
Z_SPAN = .002
FOV = .035


def object_spins(n, seed):
    """Sobol quadrature of density: ellipse + bright circular insert + small disk.

    Every spin carries equal mass; sampling probability is proportional to
    component area times added density. All components extend over z=+-1 mm.
    """
    if n & (n - 1):
        raise ValueError('n must be a power of two')
    u = qmc.Sobol(4, scramble=True, seed=seed).random_base2(int(np.log2(n)))
    weights = np.array([rx * ry * density for _, _, rx, ry, density in COMPONENTS])
    weights /= weights.sum()
    component = np.searchsorted(np.cumsum(weights), u[:, 0])
    x = np.empty(n); y = np.empty(n)
    for i, (cx, cy, rx, ry, _) in enumerate(COMPONENTS):
        keep = component == i
        radial = np.sqrt(u[keep, 1]); theta = 2 * np.pi * u[keep, 2]
        x[keep] = cx + rx * radial * np.cos(theta)
        y[keep] = cy + ry * radial * np.sin(theta)
    return dict(x=x, y=y, z=(u[:, 3] - .5) * Z_SPAN, df=np.zeros(n))


def analytic_ft(k):
    weights = np.array([rx * ry * density for _, _, rx, ry, density in COMPONENTS])
    weights /= weights.sum()
    ft = np.zeros(k.shape[1], complex)
    for weight, (cx, cy, rx, ry, _) in zip(weights, COMPONENTS):
        arg = 2 * np.pi * np.sqrt((rx * k[0])**2 + (ry * k[1])**2)
        disk = np.ones_like(arg)
        keep = arg != 0
        disk[keep] = 2 * j1(arg[keep]) / arg[keep]
        ft += weight * disk * np.exp(-2j * np.pi * (k[0] * cx + k[1] * cy))
    return ft * np.sinc(k[2] * Z_SPAN)


def discrete_ft(k, voxel):
    points = np.vstack([voxel[axis] for axis in 'xyz'])
    out = np.empty(k.shape[1], complex)
    for offset in range(0, len(out), 64):
        out[offset:offset+64] = np.exp(-2j * np.pi * k[:, offset:offset+64].T @ points).mean(axis=1)
    return out


def trajectory_and_phase(seq):
    """Independent exact gradient integration with RF-center conjugation.

    Simulator sign: Mxy evolves as exp(-2 pi i k.r); a perfect pi pulse of
    phase theta conjugates Mxy and multiplies it by exp(2 i theta).
    Receiver demodulation is included in the coefficient, not the trajectory.
    """
    ids, starts, durations = simulate.block_times(seq)
    moment = np.zeros(3); coefficient = 0j; excitation_time = 0.
    longitudinal = 1.; longitudinal_time = 0.
    ks = []; cs = []; times = []
    for bid, start, duration in zip(ids, starts, durations):
        block = seq.get_block(bid)
        gradients = [simulate.grad_pts(getattr(block, 'g'+axis)) for axis in 'xyz']
        integral = lambda t: np.array([simulate._cumint(g, t) for g in gradients])
        if block.rf is not None:
            rf = block.rf
            center = rf.delay + getattr(rf, 'center', rf.t[np.argmax(abs(rf.signal))])
            before = integral(center)
            absolute_center = start + center
            longitudinal = 1 + (longitudinal - 1) * np.exp(-(absolute_center-longitudinal_time)/1.5)
            longitudinal_time = absolute_center
            if rf.use.startswith('ref'):
                moment = -(moment + before)
                coefficient = np.exp(2j * rf.phase_offset) * coefficient.conjugate()
                longitudinal = -longitudinal
            else:
                moment[:] = 0.
                coefficient = longitudinal * 1j * np.exp(1j * rf.phase_offset)
                longitudinal = 0.
                excitation_time = start + center
            moment += integral(duration) - before
        else:
            if block.adc is not None:
                adc = block.adc
                t = adc.delay + (np.arange(adc.num_samples) + .5) * adc.dwell
                ks.append(moment[:, None] + integral(t))
                cs.append(coefficient * np.exp(-1j * (adc.phase_offset +
                    2 * np.pi * adc.freq_offset * (t-adc.delay))))
                times.append(start + t - excitation_time)
            moment += integral(duration)
    k = np.concatenate(ks, axis=1)
    pulseq_k = seq.calculate_kspace()[0]
    error = float(np.max(abs(k - pulseq_k)))
    if error > 1e-5:
        raise RuntimeError(f'independent primary trajectory disagrees: {error} cycles/m')
    return k, np.concatenate(cs), np.concatenate(times), error


def image_grid():
    x = (np.arange(128) - 63.5) * FOV / 128
    y = (np.arange(16) - 7.5) * FOV / 16
    xx, yy = np.meshgrid(x, y)
    return xx, yy


def adjoint(signal, k, xx, yy):
    result = np.zeros(xx.size, complex)
    for offset in range(0, len(signal), 64):
        exponent = k[0, offset:offset+64, None] * xx.ravel() + k[1, offset:offset+64, None] * yy.ravel()
        result += signal[offset:offset+64] @ np.exp(2j * np.pi * exponent)
    return (result / len(signal)).reshape(xx.shape)


def nrmse(actual, reference):
    return float(np.linalg.norm(actual - reference) / np.linalg.norm(reference))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--n', type=int, default=32768)
    parser.add_argument('--reuse', action='store_true', help='reuse matching n/seed acquired ADCs and finished audit')
    parser.add_argument('--cases', default=','.join(CASES))
    parser.add_argument('--extra-config', help='JSON mapping case IDs to generator override dictionaries')
    args = parser.parse_args()
    cases = {key: CASES[key] for key in args.cases.split(',')}
    if args.extra_config:
        cases.update(json.loads(Path(args.extra_config).read_text()))
    out = ROOT / 'runs/combined_phantom'
    out.mkdir(exist_ok=True, parents=True)
    data = ROOT / 'docs/data'; data.mkdir(exist_ok=True, parents=True)
    xx, yy = image_grid()
    voxel = object_spins(args.n, 11)
    rows = []; images = []; audit = []
    fourier_cache = {}
    common_peak = None
    common_reference_sum = None
    common_inside_sum = None
    old_audit = None
    if args.reuse and (data/'combined_phantom_audit.json').exists():
        old_audit = json.loads((data/'combined_phantom_audit.json').read_text())
        if old_audit['n'] != args.n:
            raise ValueError('cached audit uses another number of spins')
    conditions = [(1., 0.), (.8, 0.), (.8, 90.), (.9, 22.5)]
    for key, override in cases.items():
        images_for_case = []
        for b1, phase in conditions:
            overrides = dict(BASE, **override)
            overrides.update(sim_reduced_rows=[1], sim_reduced_shots=[0, 1],
                             sim_excitation_phase_deg=phase)
            seq, c, d, log = generate.build_sequence(generate.load_params(overrides=overrides), reduced=True)
            timing_ok, timing_errors = seq.check_timing()
            if not timing_ok:
                raise RuntimeError(timing_errors)
            if c.nav_on != 0 or [(r['shot'], r['view']) for r in log] != [(0, 0), (1, 8)]:
                raise RuntimeError('selection is not exactly the two imaging shots')
            k, coefficient, elapsed, trajectory_error = trajectory_and_phase(seq)
            if k.shape != (3, 2048) or len(np.unique(np.round(k[1], 5))) != 16:
                raise RuntimeError('expected 16 acquired distinct PE lines and 128 read samples')
            tag = f'{key}_rf{round(100*b1):03d}_phase{phase:g}'
            folder = out / tag; folder.mkdir(exist_ok=True)
            seq.write(str(folder / 'seq.seq'))
            start = time.perf_counter()
            cached_row = None
            if args.reuse and (folder/'acquisition.npz').exists():
                cached = np.load(folder/'acquisition.npz')
                if len(cached['x']) != args.n:
                    raise ValueError('cached acquisition uses another number of spins')
                actual = dict(signal=cached['raw_signal'], t_adc=seq.adc_times()[0])
                cached_row = json.loads((folder/'settings.json').read_text())['row']
                seconds = cached_row['seconds']
            else:
                actual = simulate.simulate(seq, b1=b1, voxel=voxel, rf_dt=1e-5)
                seconds = time.perf_counter() - start
            if not np.allclose(seq.adc_times()[0], actual['t_adc'], atol=1e-12, rtol=0):
                raise RuntimeError('trajectory and simulation ADC samples disagree')
            # Fixed prescribed receiver/RF frame. Do not use the imposed unknown
            # excitation-error phase to adapt the reconstruction per condition.
            echo_parity = np.repeat((-1.)**np.tile(np.arange(1, 9), 2), 128)
            receiver_frame = coefficient / abs(coefficient) * np.exp(-1j * echo_parity * np.deg2rad(phase))
            signal = actual['signal'] / receiver_frame
            primary = coefficient / receiver_frame * analytic_ft(k) * np.exp(-elapsed / .08)
            image = adjoint(signal, k, xx, yy)
            ideal_image = adjoint(primary, k, xx, yy)
            if key not in fourier_cache:
                fourier_cache[key] = (k.copy(), discrete_ft(k, voxel))
            if not np.allclose(fourier_cache[key][0], k, atol=1e-7, rtol=0):
                raise RuntimeError('changing excitation phase unexpectedly changed the trajectory')
            discrete_primary = coefficient / receiver_frame * fourier_cache[key][1] * np.exp(-elapsed / .08)
            sampled_ideal_image = adjoint(discrete_primary, k, xx, yy)
            sampled_image_error = nrmse(sampled_ideal_image, ideal_image)
            sampled_signal_error = nrmse(discrete_primary, primary)
            # Encoding-only analytic reference has the same XY ADC k and grid;
            # no RF, relaxation, or slice dephasing. It sets all common scales.
            encoding_k = k.copy(); encoding_k[2] = 0
            encoding_image = adjoint(analytic_ft(encoding_k), k, xx, yy)
            support = ((xx+.001)/.014)**2 + (yy/.011)**2 <= 1
            if common_peak is None:
                common_peak = float(abs(encoding_image).max())
                common_reference_sum = float(abs(encoding_image).sum())
                common_inside_sum = float(abs(encoding_image[support]).sum())
            row = dict(case=key, b1=b1, phase=phase, n=args.n, b_requested=1000,
                image_peak_common_scale=float(abs(image).max()/common_peak),
                image_sum_common_scale=float(abs(image).sum()/common_reference_sum),
                outside_support_common_scale=float(abs(image[~support]).sum()/common_inside_sum),
                image_complex_nrmse_vs_instantaneous_primary=nrmse(image, ideal_image),
                sampled_primary_image_nrmse=sampled_image_error,
                sampled_primary_signal_nrmse=sampled_signal_error,
                trajectory_error_cycles_per_m=trajectory_error, seconds=seconds)
            rows.append(row)
            images_for_case.append((image/common_peak, ideal_image/common_peak, encoding_image/common_peak))
            np.savez_compressed(folder/'acquisition.npz', signal=signal, raw_signal=actual['signal'],
                k_adc=k, coefficient=coefficient, elapsed=elapsed, image=image,
                instantaneous_primary_image=ideal_image, encoding_reference_image=encoding_image,
                x=voxel['x'], y=voxel['y'], z=voxel['z'])
            (folder/'settings.json').write_text(json.dumps(dict(overrides=overrides, row=row,
                seed=11, T1=1.5, T2=.08, B0=0, T2prime=None, z_span_m=Z_SPAN,
                object_components=COMPONENTS, molecular_diffusion=False,
                reconstruction='exact ADC primary k, direct nonuniform adjoint; no density compensation',
                receiver_frame='fixed zero-excitation-error primary phase; no error-dependent correction',
                rf_dt=1e-5), indent=2))
            print(tag, row, flush=True)
            if b1 == 1 and phase == 0:
                if old_audit is not None:
                    audit.append(next(record for record in old_audit['audit'] if record['case'] == key))
                    continue
                # Independent center-slice finite-RF encoding sanity test: perfect
                # slice-center RF should closely match the ideal primary signal.
                center_voxel = object_spins(512, 17)
                center_voxel['z'][:] = 0
                check = simulate.simulate(seq, b1=1, voxel=center_voxel, rf_dt=1e-6)
                oracle = coefficient * discrete_ft(k, center_voxel) * np.exp(-elapsed/.08)
                error = nrmse(check['signal'], oracle)
                if error > .025:
                    raise RuntimeError(f'RF/receiver-frame encoding check failed: {error}')
                convergence = simulate.simulate(seq, b1=.8, voxel=voxel, rf_dt=5e-6)
                nominal = simulate.simulate(seq, b1=.8, voxel=voxel, rf_dt=1e-5)
                second_seed = simulate.simulate(seq, b1=.8, voxel=object_spins(args.n, 12), rf_dt=1e-5)
                coarse = simulate.simulate(seq, b1=.8, voxel=object_spins(8192, 11), rf_dt=1e-5)
                second_image = adjoint(second_seed['signal']/receiver_frame, k, xx, yy)
                nominal_image = adjoint(nominal['signal']/receiver_frame, k, xx, yy)
                coarse_image = adjoint(coarse['signal']/receiver_frame, k, xx, yy)
                audit.append(dict(case=key, center_slice_encoding_signal_nrmse=error,
                    rf_dt_10us_vs_5us_signal_nrmse=nrmse(nominal['signal'], convergence['signal']),
                    second_seed_image_nrmse=nrmse(second_image, nominal_image),
                    spins_8192_vs_final_image_nrmse=nrmse(coarse_image, nominal_image),
                    spins_8192_peak_common_scale=float(abs(coarse_image).max()/common_peak),
                    second_seed_peak_common_scale=float(abs(second_image).max()/common_peak)))
        images.append((key, images_for_case))
    qualified = max(record['second_seed_image_nrmse'] for record in audit) <= .05
    for row in rows:
        row['image_sampling_qualified'] = qualified
    with (data/'combined_phantom_metrics.csv').open('w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    (data/'combined_phantom_audit.json').write_text(json.dumps(dict(audit=audit,
        image_sampling_qualified=qualified, second_seed_image_nrmse_tolerance=.05,
        claim='static model image ranking allowed' if qualified else 'image-quality ranking unverified; unconverged spatial quadrature',
        model='stationary finite-duration sinc-RF Bloch; actual imaging ADC acquisition',
        conditions=conditions, n=args.n, seed=11, xy_fov_mm=35, grid=[128,16],
        dependency_versions={name: version(name) for name in ('numpy','scipy','pypulseq','matplotlib')},
        audit_conditions=dict(center_slice=dict(n=512,seed=17,b1=1,phase=0,z_m=0,rf_dt=1e-6),
            rf_steps=dict(b1=.8,phase=0,steps_s=[1e-5,5e-6]),
            seeds=dict(b1=.8,phase=0,seeds=[11,12],n=args.n),
            spatial_density=dict(b1=.8,phase=0,seed=11,n=[8192,args.n])),
        ideal_reference='analytic Fourier transform, ideal instantaneous RF, uniform 2-mm z support',
        limitations=['16 PE lines limit resolution and cause ringing',
            'Finite-RF slice profile differs from instantaneous-RF ideal reference',
            'Diffusion gradients play; molecular motion and diffusion attenuation absent',
            'No noise, coil response, motion, hardware imperfections, or scanner reconstruction',
            'Metrics have a single analytic encoding-reference scale; no per-image gain fit']), indent=2))
    fig, axes = plt.subplots(len(images)+1, len(conditions), figsize=(16, 2.8*(len(images)+1)), squeeze=False)
    for col, (b1, phase) in enumerate(conditions):
        axes[0,col].imshow(abs(images[0][1][col][2]), origin='lower', extent=[-17.5,17.5,-17.5,17.5],
            vmin=0, vmax=1, cmap='magma', interpolation='nearest', aspect='equal')
        axes[0,col].set_title(f'RF scale {b1:g}; phase error {phase:g}°')
    axes[0,0].set_ylabel('Analytic encoding reference\n(no RF or relaxation)')
    for row, (key, case_images) in enumerate(images, 1):
        for col, (image, _, _) in enumerate(case_images):
            im = axes[row,col].imshow(abs(image), origin='lower', extent=[-17.5,17.5,-17.5,17.5],
                vmin=0, vmax=1, cmap='magma', interpolation='nearest', aspect='equal')
            axes[row,col].set_xlabel('Read x (mm)')
        axes[row,0].set_ylabel(key.replace('_','\n')+'\nPhase y (mm)')
    fig.suptitle('Actual static finite-RF imaging phantom: 2 shots × 8 echoes, 128 × 16\n'
                 'Nominal b=1000 read; TE=36 ms; ESP=16 ms; common absolute scale\n' +
                 ('Sampling audit passed' if qualified else 'Spatial sampling audit failed: do not rank image quality'), fontsize=13)
    fig.text(.5,.015,'All displayed images use one encoding-reference scale. Bright insert and small disk are part of the object.\n'
             'Stationary spins: diffusion gradients played, molecular diffusion absent. Coarse numerical qualification only.',
             ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.055,.9,.95))
    fig.colorbar(im, ax=axes.ravel().tolist(), fraction=.025, pad=.03, label='Magnitude / common reference peak')
    figure = ROOT/'docs/figures/combined_factor_phantom.png'; figure.parent.mkdir(exist_ok=True)
    fig.savefig(figure, dpi=170); plt.close(fig)


if __name__ == '__main__':
    main()

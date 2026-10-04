"""Export complete Pulseq gradients and exact primary-pathway b tensors.

All three played axes, ramps and cross terms are included. Gradient units are
Hz/m (gamma already applied), q is rad/m, B is s/mm^2. RF is represented by
instantaneous excitation/refocusing at its centre; imperfect RF produces many
pathways, so this tensor does not describe their combined acquired signal.

python -m dwfse.btensor sequence.seq --out runs/tensor
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from .simulate import block_times, grad_pts, read_seq
from .view import rf_centre


def integrate_interval(q, g0, g1, dt, sign=1):
    """Analytic integral of q q^T for a linear-gradient interval, including ramps."""
    if dt <= 0:
        raise ValueError('interval duration must be positive')
    coeff = [np.asarray(q, float), 2 * np.pi * sign * np.asarray(g0),
             np.pi * sign * (np.asarray(g1) - g0) / dt]
    b = sum(np.outer(a, c) * dt ** (i + j + 1) / (i + j + 1)
            for i, a in enumerate(coeff) for j, c in enumerate(coeff)) * 1e-6
    end_q = coeff[0] + coeff[1] * dt + coeff[2] * dt ** 2
    return end_q, b


def played_waveform(seq):
    """Piecewise-linear intervals for the entire file, including idle time.

    Read every block rather than the viewer's first-TR selection. Midpoint
    ownership prevents double counting a nonzero boundary shared by two blocks.
    """
    seq = read_seq(seq)
    ids, starts, durations = block_times(seq)
    segments, knots, rf_events, adc_events = [], [0., sum(durations)], [], []
    labels = {}
    for block_id, start, duration in zip(ids, starts, durations):
        block = seq.get_block(block_id)
        for label in (block.label or {}).values():
            if label.type == 'labelinc':
                labels[label.label] = labels.get(label.label,0) + int(label.value)
            else:
                labels[label.label] = int(label.value)
        for axis in range(3):
            gradient = getattr(block, 'g' + 'xyz'[axis])
            points = grad_pts(gradient)
            if points is None:
                continue
            times, amps = points
            # Restore the edge values of sample-centred arbitrary gradients.
            if gradient.type != 'trap':
                edge = getattr(gradient, 'shape_dur', times[-1] - gradient.delay)
                if times[0] > gradient.delay:
                    times = np.r_[gradient.delay, times]
                    amps = np.r_[gradient.first, amps]
                if times[-1] < gradient.delay + edge:
                    times = np.r_[times, gradient.delay + edge]
                    amps = np.r_[amps, gradient.last]
            times = times + start
            knots.extend(times)
            for a, b, ga, gb in zip(times[:-1], times[1:], amps[:-1], amps[1:]):
                if b > a:
                    segments.append((axis, a, b, ga, gb))
        if block.rf is not None:
            use = getattr(block.rf, 'use', '')
            if use not in ('excitation', 'refocusing'):
                raise ValueError('b-tensor export requires explicit RF excitation/refocusing use')
            time = start + rf_centre(block.rf)
            rf_events.append(dict(time_s=float(time), use=use, block=int(block_id), labels=dict(labels)))
            knots.append(time)
        if block.adc is not None:
            adc = block.adc
            centre = start + adc.delay + adc.num_samples * adc.dwell / 2
            sample = start + adc.delay + (adc.num_samples // 2 + .5) * adc.dwell
            adc_events.append(dict(centre_s=float(centre), sample_s=float(sample),
                                   block=int(block_id), labels=dict(labels)))
            knots.extend((centre, sample))
    times = np.unique(np.round(knots, 12))
    left, right = np.zeros((len(times) - 1, 3)), np.zeros((len(times) - 1, 3))
    midpoint = (times[:-1] + times[1:]) / 2
    for axis, a, b, ga, gb in segments:
        mask = (midpoint > a) & (midpoint < b)
        slope = (gb - ga) / (b - a)
        left[mask, axis] += ga + slope * (times[:-1][mask] - a)
        right[mask, axis] += ga + slope * (times[1:][mask] - a)
    return times, left, right, rf_events, adc_events


def calculate(seq):
    seq = read_seq(seq)
    times, left, right, rfs, adcs = played_waveform(seq)
    rf_at, adc_at = {}, {}
    for rf in rfs:
        rf_at.setdefault(round(rf['time_s'], 12), []).append(rf)
    for adc in adcs:
        for kind in ('centre', 'sample'):
            adc_at.setdefault(round(adc[kind + '_s'], 12), []).append((kind, adc))
    q, b, sign, train, echo = np.zeros(3), np.zeros((3, 3)), 1, 0, 0
    records = []
    for i, time in enumerate(times):
        key = round(float(time), 12)
        for rf in rf_at.get(key, []):
            if rf['use'] == 'excitation':
                q, b, sign, echo = np.zeros(3), np.zeros((3, 3)), 1, 0
                train += 1
                excitation_time = time
            else:
                if not train:
                    raise ValueError('refocusing without preceding excitation')
                sign *= -1
        for kind, adc in adc_at.get(key, []):
            if not train:
                raise ValueError('ADC without preceding excitation')
            if kind == 'centre':
                echo += 1
            records.append(dict(train=train, echo=echo, convention=kind, block=adc['block'],
                                labels=adc['labels'],
                                time_s=float(time), time_after_excitation_s=float(time-excitation_time),
                                B_s_mm2=b.tolist(), trace_s_mm2=float(np.trace(b)),
                                q_rad_m=q.tolist()))
        if i + 1 < len(times) and train:
            q, db = integrate_interval(q, left[i], right[i], times[i+1]-time, sign)
            b += db
    metadata = dict(
        method='analytic piecewise-linear integral; q=2*pi*integral(sign*G_Hz_m dt)',
        units=dict(gradient='Hz/m', q='rad/m', B='s/mm^2'),
        axes=seq.definitions.get('AxisMap', 'Pulseq x,y,z axes'),
        scope='primary spin-echo pathway, instantaneous RF at centres; not mixed-pathway effective b',
        requested_diffusion_b_s_mm2=np.atleast_1d(seq.definitions.get('bValuesRequested', [])).tolist(),
        scanner_nominal_diffusion_b_s_mm2=np.atleast_1d(seq.definitions.get('bValuesPPLNominal', [])).tolist(),
        gradient_delay_us=seq.definitions.get('GradientDelay_us', None),
        source='modelled played waveform in the supplied Pulseq file; not a hardware measurement')
    return dict(metadata=metadata, rf_events=rfs, echoes=records), (times, left, right)


def export(seq, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    payload, (times, left, right) = calculate(seq)
    (out/'btensor.json').write_text(json.dumps(payload, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    # Interval endpoints represent every played gradient exactly under the
    # linear-ramp model; there is no downsampled raster or omitted imaging term.
    with (out/'waveform.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['start_s', 'end_s', 'gx_start_Hz_m', 'gy_start_Hz_m', 'gz_start_Hz_m',
                         'gx_end_Hz_m', 'gy_end_Hz_m', 'gz_end_Hz_m'])
        writer.writerows([float(a), float(b), *g0, *g1]
                         for a, b, g0, g1 in zip(times[:-1], times[1:], left, right))
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sequence')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    payload = export(args.sequence, args.out)
    print(f'Exported {len(payload["echoes"])} echo centre/sample tensors to {args.out}')


if __name__ == '__main__':
    main()

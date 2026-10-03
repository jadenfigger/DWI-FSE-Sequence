"""
make_examples.py - very small .seq files that build up, one idea at a time,
to the DW-FSE echo train. All pulses are hard (non-selective) 200 us blocks;
no imaging gradients; long ADC windows so you can see echoes form and move.

    cd pypulseq/examples && python make_examples.py      # writes ex*.seq
    python ../bloch_sim.py ex3_cpmg_train.seq --b1 0.8     # simulate one

Gradients: crushers on z (voxel spans z = +-1 mm in bloch_sim / koma_sim),
diffusion lobes on x. Timing is written as absolute event times so it is
easy to read; see README.md in this folder for what to look for.
"""
import math

import numpy as np
import pypulseq as pp

SYS = pp.Opts(max_grad=600, grad_unit='mT/m', max_slew=3000, slew_unit='T/m/s',
              rf_dead_time=100e-6, rf_ringdown_time=30e-6, adc_dead_time=10e-6,
              grad_raster_time=10e-6, rf_raster_time=1e-6)
T_RF = 200e-6          # hard pulse duration
CRUSH_AREA = 4000.0    # 1/m per crusher lobe = 4 cycles/mm across the voxel
DWELL = 50e-6


class Timeline:
    """Add blocks at absolute times (s); gaps become delay blocks."""

    def __init__(self, name):
        self.seq = pp.Sequence(SYS)
        self.t = 0.0
        self.name = name

    def at(self, t0, *events, dur=None):
        t0 = round(t0 / 10e-6) * 10e-6
        if t0 < self.t - 1e-9:
            raise ValueError(f'{self.name}: event at {t0*1e3:.3f} ms overlaps previous block')
        if t0 > self.t:
            self.seq.add_block(pp.make_delay(t0 - self.t))
        d = pp.calc_duration(*events) if dur is None else dur
        self.seq.add_block(*events, pp.make_delay(d))
        self.t = t0 + d

    def rf(self, t_centre, flip_deg, phase_deg, use):
        p = pp.make_block_pulse(math.radians(flip_deg), duration=T_RF, phase_offset=math.radians(phase_deg),
                                delay=SYS.rf_dead_time, system=SYS, use=use)
        self.at(t_centre - SYS.rf_dead_time - T_RF / 2, p)

    def crushed_180(self, t_centre, phase_deg, area_pre=CRUSH_AREA, area_post=CRUSH_AREA):
        """crusher - 180 - crusher, all in one block centred on the 180."""
        rf = pp.make_block_pulse(math.pi, duration=T_RF, phase_offset=math.radians(phase_deg),
                                 delay=1e-3 + SYS.rf_dead_time, system=SYS, use='refocusing')
        t_post = 1e-3 + SYS.rf_dead_time + T_RF + SYS.rf_ringdown_time
        times, amps = [], []
        for t0, area in ((0.0, area_pre), (t_post, area_post)):
            g = pp.make_trapezoid('z', area=area, duration=1e-3, system=SYS)
            times += [t0, t0 + g.rise_time, t0 + g.rise_time + g.flat_time, t0 + 1e-3]
            amps += [0, g.amplitude, g.amplitude, 0]
        gz = pp.make_extended_trapezoid('z', times=np.round(np.array(times) / 10e-6) * 10e-6,
                                        amplitudes=np.array(amps), system=SYS)
        rf_c = 1e-3 + SYS.rf_dead_time + T_RF / 2
        self.at(t_centre - rf_c, gz, rf)

    def adc(self, t_start, t_end):
        n = int((t_end - t_start) / DWELL)
        self.at(t_start, pp.make_adc(num_samples=n, dwell=DWELL, system=SYS))

    def adc_centred(self, t_echo, width=4e-3):
        self.adc(t_echo - width / 2, t_echo + width / 2)

    def write(self, desc, tr=1.0):
        if tr > self.t:
            self.seq.add_block(pp.make_delay(tr - self.t))
        ok, rep = self.seq.check_timing()
        assert ok, rep[:3]
        self.seq.set_definition('Name', self.name)
        self.seq.set_definition('Description', desc)
        self.seq.write(self.name + '.seq')
        print(f'{self.name + ".seq":34s} {desc}')


def ex1_fid():
    s = Timeline('ex1_fid')
    s.rf(0.5e-3, 90, 0, 'excitation')
    s.adc(0.8e-3, 40.8e-3)
    s.write('90x then a 40 ms ADC: free induction decay, T2* = T2 and T2-prime')


def ex2_spin_echo():
    s = Timeline('ex2_spin_echo')
    t90, tau = 0.5e-3, 10e-3
    s.rf(t90, 90, 0, 'excitation')
    s.adc(t90 + 0.3e-3, t90 + tau - 0.5e-3)
    s.rf(t90 + tau, 180, 90, 'refocusing')
    s.adc(t90 + tau + 0.5e-3, t90 + 3 * tau)
    s.write('90x - 10 ms - 180y: spin echo at TE = 20 ms (no crushers)')


def train(name, phase180, desc, n_echo=4, esp=10e-3):
    s = Timeline(name)
    t90 = 1e-3
    s.rf(t90, 90, 0, 'excitation')
    for k in range(n_echo):
        t180 = t90 + esp / 2 + k * esp
        s.crushed_180(t180, phase180)
        s.adc_centred(t180 + esp / 2, width=6e-3)
    s.write(desc)


def ex5_unequal_first_interval(equal_crushers=True):
    name = 'ex5_unequal_first_interval' + ('' if equal_crushers else '_b')
    s = Timeline(name)
    t90, tau1, tau2 = 1e-3, 20e-3, 5e-3
    c1 = CRUSH_AREA if equal_crushers else CRUSH_AREA / 2     # DW-FSE PPR: 2754 vs 5482 DAC
    s.rf(t90, 90, 0, 'excitation')
    s.crushed_180(t90 + tau1, 90, c1, c1)
    e1 = t90 + 2 * tau1
    s.adc_centred(e1, width=6e-3)
    t2 = e1 + tau2
    s.crushed_180(t2, 90)
    s.adc(t2 + 1.4e-3, t2 + 25e-3)
    tag = 'equal crushers' if equal_crushers else 'first crusher pair = half size, like the DW-FSE PPR'
    s.write(f'90x-20ms-180y-20ms-echo1-5ms-180y, long ADC: echo2 at +5 ms, stimulated echo at +20 ms after the 2nd 180 ({tag})')


def ex6_dw_fse_mini(phase90=0, name='ex6_dw_fse_mini'):
    """Stejskal-Tanner prep around the first 180, then a 3-echo train (esp 10 ms)."""
    s = Timeline(name)
    t90, te1, esp = 1e-3, 40e-3, 10e-3
    g = pp.make_trapezoid('x', amplitude=0.3 * 42.577e6 * 1e-0 * 1.0, flat_time=8e-3, rise_time=300e-6, system=SYS)
    s.rf(t90, 90, phase90, 'excitation')
    t180 = t90 + te1 / 2
    s.at(t180 - 1.3e-3 - pp.calc_duration(g) - 1e-3, g)
    s.crushed_180(t180, 90)
    s.at(t180 + 1.3e-3 + 1e-3, g)
    e = t180 + te1 / 2
    s.adc_centred(e, width=6e-3)
    for k in range(3):
        t = e + esp / 2 + k * esp
        s.crushed_180(t, 90)
        s.adc_centred(t + esp / 2, width=6e-3)
    G = g.amplitude * 2 * np.pi
    d = g.flat_time + g.rise_time
    D = (t180 + 1.3e-3 + 1e-3) - (t180 - 1.3e-3 - pp.calc_duration(g) - 1e-3)
    b = G ** 2 * d ** 2 * (D - d / 3) * 1e-6
    how = 'excitation along x (CPMG-consistent)' if phase90 == 0 else \
        f'excitation phase {phase90} deg: mimics the random phase motion adds during the diffusion lobes'
    s.write(f'mini DW-FSE: TE1 40 ms (b ~ {b:.0f} s/mm^2 on x), then 3 echoes at esp 10 ms; {how}')


if __name__ == '__main__':
    ex1_fid()
    ex2_spin_echo()
    train('ex3_cpmg_train', 90, 'CPMG: 90x then 4 x 180y (crushed), esp 10 ms - robust to B1 error')
    train('ex4_cp_train', 0, 'CP: 90x then 4 x 180x (crushed), esp 10 ms - same timing, refocusing phase = excitation phase')
    ex5_unequal_first_interval(True)
    ex5_unequal_first_interval(False)
    ex6_dw_fse_mini(0)
    ex6_dw_fse_mini(90, 'ex6b_dw_fse_mini_phase90')

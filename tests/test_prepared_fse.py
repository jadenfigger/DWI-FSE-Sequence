"""Physical and acquisition invariants for the research preparation models."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from dwfse import simulate
from examples.compare_prepared_fse import build, landmarks, DEPHASE, SPOIL


class PreparedFSETests(unittest.TestCase):
    def test_prepared_sequences_roundtrip_and_keep_matched_acquisition(self):
        reference, reference_info = build('centered_original')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'reference.seq'
            reference.write(str(path))
            reference = simulate.read_seq(path)
        _, reference_adc = landmarks(reference, reference_info)
        for name in ['alsop', 'ss_mgot']:
            with self.subTest(name=name):
                seq, info = build(name)
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / 'prepared.seq'
                    seq.write(str(path))
                    loaded = simulate.read_seq(path)
                self.assertTrue(loaded.check_timing()[0])
                _, adcs = landmarks(loaded, info)
                self.assertEqual(len(info['imaging_rf_blocks']), 8)
                self.assertEqual(len(adcs), 8)
                self.assertEqual(loaded.definitions['PublishedProtocolReproduction'], 0)
                for a, r in zip(adcs, reference_adc):
                    self.assertAlmostEqual(a['sample_s'] - info['initial_excitation_s'],
                                           r['sample_s'] - reference_info['initial_excitation_s'])
                    for key in ['phase_rad', 'frequency_hz', 'num_samples']:
                        self.assertEqual(a[key], r[key])
                    block, original = loaded.get_block(a['block']), reference.get_block(r['block'])
                    for axis in ['gx', 'gy']:
                        points, expected = simulate.grad_pts(getattr(block, axis)), simulate.grad_pts(getattr(original, axis))
                        if points is None or expected is None:
                            self.assertIsNone(points)
                            self.assertIsNone(expected)
                            continue
                        np.testing.assert_allclose(points[0], expected[0], atol=1e-12)
                        np.testing.assert_allclose(points[1], expected[1], atol=1e-6)
                    # The recall must be complete before the ADC and fully
                    # restored afterwards; no slice gradient during sampling.
                    points = simulate.grad_pts(block.gz)
                    # Serialized gradient amplitudes have finite precision.
                    self.assertAlmostEqual(float(simulate._cumint(points, block.adc.delay)), DEPHASE, delta=.01)
                    self.assertAlmostEqual(float(simulate._cumint(points, block.block_duration)), 0, delta=.01)
                    samples = block.adc.delay + (np.arange(block.adc.num_samples) + .5) * block.adc.dwell
                    np.testing.assert_allclose(np.interp(samples, *points), 0, atol=1e-6)
                # Harmonic averaging requires PE to rewind before subsequent RF.
                net_y = 0.
                for bid in sorted(loaded.block_events):
                    block = loaded.get_block(bid)
                    if block.rf is not None:
                        self.assertIsNone(block.gy)
                        expected = SPOIL if name == 'ss_mgot' and bid > info['spoiler_block'] else 0
                        self.assertAlmostEqual(net_y, expected, delta=.1)
                    if block.gy is not None:
                        net_y += float(simulate._cumint(simulate.grad_pts(block.gy), block.block_duration))

    def test_tip_axes_preserve_or_store_the_same_mg_component(self):
        mx, my, mz = np.array([.3]), np.array([.4]), np.array([0.])
        alsop = simulate._rotate(mx, my, mz, 0., -1., 0., .25)
        ss = simulate._rotate(mx, my, mz, -1., 0., 0., .25)
        np.testing.assert_allclose(np.array(alsop).ravel(), [0, .4, -.3], atol=1e-15)
        np.testing.assert_allclose(np.array(ss).ravel(), [.3, 0, .4], atol=1e-15)
        # After spoiling transverse coherence, re-excitation returns stored My.
        reexcited = simulate._rotate(np.zeros(1), np.zeros(1), ss[2], 1., 0., 0., .25)
        np.testing.assert_allclose(np.array(reexcited).ravel(), [0, .4, 0], atol=1e-15)

    def test_ideal_recalled_mg_signal_is_half_and_phase_independent(self):
        # Integrate an integer number of dephasing cycles. This checks the
        # preparation/recall mechanism independently of finite RF shapes.
        psi = 2 * np.pi * (np.arange(4096) + .5) / 4096 * 2
        for phase in np.linspace(0, 2*np.pi, 13):
            state = (np.cos(phase-psi), np.sin(phase-psi), np.zeros_like(psi))
            for method in ['alsop', 'ss_mgot']:
                if method == 'alsop':
                    prepared = simulate._rotate(*state, 0., -1., 0., .25)
                else:
                    stored = simulate._rotate(*state, -1., 0., 0., .25)
                    prepared = simulate._rotate(np.zeros_like(psi), np.zeros_like(psi), stored[2], 1., 0., 0., .25)
                echo = simulate._rotate(*prepared, 0., -1., 0., .5)
                signal = np.mean((echo[0] + 1j*echo[1]) * np.exp(-1j*psi))
                self.assertAlmostEqual(abs(signal), .5, places=12)


if __name__ == '__main__':
    unittest.main()

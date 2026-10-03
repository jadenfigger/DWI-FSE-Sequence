import hashlib
import math
import re
import tempfile
import unittest
from pathlib import Path

from dwfse.generate import PHASE_RES, PPLAbort, build_sequence, derive, load_params
from dwfse.simulate import read_seq


class ImprovementOptionTests(unittest.TestCase):
    def test_file_roundtrip_preserves_timing_rasters(self):
        seq, _, _, _ = build_sequence(reduced=True)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'roundtrip.seq'
            seq.write(str(path))
            restored = read_seq(path)
        ok, errors = restored.check_timing()
        self.assertTrue(ok, errors)
        self.assertEqual(restored.system.grad_raster_time, seq.system.grad_raster_time)

    def _first_train(self, **overrides):
        seq, _, derived, log = build_sequence(reduced=True, overrides=overrides)
        return seq, derived, log[0]['train']

    def test_default_sequence_events_match_pre_edit_baseline(self):
        # SHA-256 of the full pre-edit .seq event/library sections.  Definitions
        # and signature are omitted because this feature intentionally adds
        # definitions, which necessarily changes the file signature.
        expected = 'a938f67a2f7632fc6d61a4a42d23117e99f5d2a29aee1e735a161e9f8b176a12'
        seq, _, _, _ = build_sequence()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'default.seq'
            seq.write(str(path))
            text = path.read_text(encoding='utf-8')
        text = re.sub(r'\[DEFINITIONS\].*?(?=\n# Format of blocks:)', '', text, flags=re.S)
        text = re.sub(r'\n\[SIGNATURE\].*\Z', '', text, flags=re.S)
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), expected)

    def test_90_degree_excitation_offset_does_not_change_refocus_or_receiver(self):
        _, _, baseline = self._first_train()
        seq, derived, shifted = self._first_train(sim_excitation_phase_deg=90)
        phase_90_units = round(90 * 1000 / PHASE_RES)
        self.assertEqual(shifted.rf[0]['phase'], baseline.rf[0]['phase'] + phase_90_units)
        self.assertEqual([rf['phase'] for rf in shifted.rf[1:]],
                         [rf['phase'] for rf in baseline.rf[1:]])
        self.assertEqual([adc['phase'] for adc in shifted.adc],
                         [adc['phase'] for adc in baseline.adc])
        self.assertEqual(derived.excitation_phase_offset_deg, 90.0)
        self.assertEqual(seq.definitions['ExcitationPhaseOffsetDeg'], 90.0)

    def test_refocus_offsets_are_relative_and_quantized(self):
        _, _, baseline = self._first_train()
        seq, derived, shifted = self._first_train(sim_refocus_phase_offsets_deg=[0.34, -0.34])
        self.assertEqual(derived.refocus_phase_offsets_deg, [0.45, -0.45])
        self.assertEqual([rf['phase'] - base['phase']
                          for rf, base in zip(shifted.rf[1:], baseline.rf[1:])], [2, -2])
        self.assertEqual(shifted.rf[0]['phase'], baseline.rf[0]['phase'])
        self.assertEqual([adc['phase'] for adc in shifted.adc],
                         [adc['phase'] for adc in baseline.adc])
        self.assertEqual(seq.definitions['RefocusPhaseOffsetsDeg'], [0.45, -0.45])

    def test_train_crushers_use_symmetric_per_echo_signed_amplitudes(self):
        seq, derived, train = self._first_train(sim_train_crusher_scales=[2, -1])
        self.assertEqual(derived.train_crusher_amplitudes_dac, [5508, -5482])
        self.assertEqual(seq.definitions['TrainCrusherAmplitudesDAC'], [5508, -5482])
        crusher_segments = train.g['s'][1:3]
        for segment, amplitude in zip(crusher_segments, derived.train_crusher_amplitudes_dac):
            occurrences = [value for _, value in segment if value == amplitude]
            self.assertEqual(len(occurrences), 4)  # two plateau endpoints on each side of the RF

    def test_invalid_crusher_scales_abort_early(self):
        cases = [
            {'sim_train_crusher_scales': [1]},
            {'sim_train_crusher_scales': [math.inf, 1]},
            {'sim_train_crusher_scales': [20, 1]},
            {'sim_train_crusher_scales': [1e308, 1]},
            {'sim_train_crusher_scales': [1, 1], 'crush_independent_on': 0},
        ]
        for overrides in cases:
            with self.subTest(overrides=overrides), self.assertRaises(PPLAbort):
                derive(load_params(overrides=overrides))

    def test_phase_option_lengths_and_finiteness_abort_early(self):
        for overrides in ({'sim_refocus_phase_offsets_deg': [0]},
                          {'sim_refocus_phase_offsets_deg': [0, math.nan]},
                          {'sim_excitation_phase_deg': math.inf}):
            with self.subTest(overrides=overrides), self.assertRaises(PPLAbort):
                derive(load_params(overrides=overrides))

    def test_etl8_te36_esp16_b1000_passes_timing(self):
        seq, _, _, _ = build_sequence(
            reduced=True,
            overrides={
                'views_per_seg': 8,
                'no_views': 16,
                'te': 36,
                'esp': 16,
                'acq_b': [1000] + [0] * 511,
            },
        )
        ok, errors = seq.check_timing()
        self.assertTrue(ok, errors)


if __name__ == '__main__':
    unittest.main()

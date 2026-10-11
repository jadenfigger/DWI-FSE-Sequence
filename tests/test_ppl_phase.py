"""Analytic checks of the manual's cumulative offset phase convention."""
from types import SimpleNamespace
import unittest

from dwfse.ppl.phase import accumulated_phase_deg, circular_difference_deg


class PhaseIntegrationTests(unittest.TestCase):
    def test_manual_one_hz_half_second_example(self):
        it = SimpleNamespace(frequency_events=[
            {"kind": "send", "t_us": 0, "frequency_hz": 1},
            {"kind": "send", "t_us": 500000, "frequency_hz": 0},
        ])
        self.assertAlmostEqual(accumulated_phase_deg(it, 0, 1000000, 0), 180)

    def test_restoring_frequency_does_not_reset_phase(self):
        it = SimpleNamespace(frequency_events=[
            {"kind": "send", "t_us": 0, "frequency_hz": 1000},
            {"kind": "send", "t_us": 100, "frequency_hz": 0},
            {"kind": "send", "t_us": 200, "frequency_hz": -1000},
            {"kind": "send", "t_us": 300, "frequency_hz": 0},
        ])
        self.assertAlmostEqual(accumulated_phase_deg(it, 0, 150, 0), 36)
        self.assertAlmostEqual(accumulated_phase_deg(it, 0, 400, 0), 0)

    def test_separate_mhz_receiver_bank_does_not_accrue_tx_phase(self):
        it = SimpleNamespace(frequency_events=[
            {"kind": "send", "t_us": 0, "frequency_hz": 1000, "mhz": 400},
            {"kind": "send", "t_us": 100, "frequency_hz": 1000, "mhz": 410},
            {"kind": "send", "t_us": 1000, "frequency_hz": 0, "mhz": 400},
        ])
        self.assertAlmostEqual(accumulated_phase_deg(it, 0, 2000, 0, mhz=400), 36)
        self.assertEqual(circular_difference_deg(359, 1), -2)


if __name__ == "__main__":
    unittest.main()

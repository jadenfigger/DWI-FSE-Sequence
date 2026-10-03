import json
import math
import unittest

import MRzeroCore as mr0
import numpy as np

from dwfse.pathways import (
    enumerate_center_pathways,
    metric_record,
    with_mrzero_closure,
)


def _train(echoes=4, phases=(0.37, 1.10, -0.40, 0.82, -1.25)):
    seq = mr0.Sequence(normalized_grads=False)
    excitation = seq.new_rep(1)
    excitation.pulse.angle = np.pi / 2
    excitation.pulse.phase = phases[0]
    excitation.pulse.usage = mr0.PulseUsage.EXCIT
    excitation.event_time[:] = 0.005

    for echo in range(echoes):
        rep = seq.new_rep(2)
        rep.pulse.angle = np.pi
        rep.pulse.phase = phases[echo + 1 if echo + 1 < len(phases) else -1]
        rep.pulse.usage = mr0.PulseUsage.REFOC
        rep.event_time[:] = 0.005
        rep.adc_usage[0] = 1
        rep.adc_phase[0] = 0.19 - 0.07 * echo
    return seq


def _data(b1=0.8):
    return mr0.CustomVoxelPhantom(
        pos=[[0.0, 0.0, 0.0]], PD=1.0,
        T1=1.5, T2=0.080, T2dash=0.030,
        D=0.0, B0=23.0, B1=b1,
        voxel_size=[0.0002, 0.0002, 0.001], voxel_shape="box",
    ).build()


class PathwayTests(unittest.TestCase):
    def test_primary_matches_analytic_and_closes_with_phase_offsets(self):
        b1 = 0.8
        seq = _train()
        metrics = with_mrzero_closure(seq, _data(b1))
        self.assertEqual(len(metrics), 4)
        for metric in metrics:
            expected = (
                math.sin(b1 * math.pi / 2)
                * math.sin(b1 * math.pi / 2) ** (2 * metric.echo)
                * math.exp(-metric.time_s / 0.080)
            )
            self.assertAlmostEqual(abs(metric.primary), expected, places=7)
            self.assertLess(metric.closure_relative_error, 5e-6)
            self.assertEqual(
                metric.primary_history,
                tuple("+" if i % 2 == 0 else "-"
                      for i in range(metric.repetition + 1)),
            )
            self.assertAlmostEqual(metric.primary + metric.other, metric.total)
            self.assertAlmostEqual(
                metric.primary_l1_fraction + metric.other_l1_fraction, 1.0
            )

    def test_json_record_is_strictly_serializable(self):
        metric = enumerate_center_pathways(_train(1), _data())[0]
        encoded = json.dumps(metric_record(metric, top=None), allow_nan=False)
        self.assertIn('"primary_present": true', encoded)

    def test_rejects_more_than_eight_echoes(self):
        with self.assertRaisesRegex(ValueError, "exceed the supported ETL"):
            enumerate_center_pathways(_train(9), _data())


if __name__ == "__main__":
    unittest.main()

"""Tests for jev/calibrate.py (no network)."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jev import calibrate as cal  # noqa: E402


def argmax(xs):
    return max(range(len(xs)), key=xs.__getitem__)


class ApplyTemperatureTest(unittest.TestCase):
    def test_t1_is_identity(self):
        p = [0.6, 0.3, 0.1]
        for a, b in zip(cal.apply_temperature(p, 1.0), p):
            self.assertAlmostEqual(a, b)

    def test_never_changes_chosen_option(self):
        rows = [[0.6, 0.3, 0.1], [0.05, 0.9, 0.05], [0.0, 0.0, 1.0], [0.26, 0.25, 0.25, 0.24]]
        for row in rows:
            for T in (0.05, 0.3, 1.0, 2.5, 20.0):
                scaled = cal.apply_temperature(row, T)
                self.assertEqual(argmax(scaled), argmax(row), (row, T))
                self.assertAlmostEqual(sum(scaled), 1.0)

    def test_high_t_softens_low_t_sharpens(self):
        p = [0.8, 0.2]
        self.assertLess(cal.apply_temperature(p, 3.0)[0], 0.8)
        self.assertGreater(cal.apply_temperature(p, 0.5)[0], 0.8)

    def test_zero_probability_is_handled(self):
        scaled = cal.apply_temperature([1.0, 0.0], 5.0)
        self.assertTrue(all(math.isfinite(x) for x in scaled))
        self.assertEqual(argmax(scaled), 0)

    def test_rejects_nonpositive_t(self):
        with self.assertRaises(ValueError):
            cal.apply_temperature([0.5, 0.5], 0)


class FitTemperatureTest(unittest.TestCase):
    def test_overconfident_rows_get_t_above_1_matching_closed_form(self):
        # Always 99% confident, right 7 times out of 10. The best T makes the
        # top probability 0.7: (0.99/0.01) ** (1/T) = 0.7/0.3.
        rows = [[0.99, 0.01]] * 10
        labels = [0] * 7 + [1] * 3
        T = cal.fit_temperature(rows, labels)
        expected = math.log(99) / math.log(0.7 / 0.3)
        self.assertAlmostEqual(T, expected, places=3)
        self.assertAlmostEqual(cal.apply_temperature(rows[0], T)[0], 0.7, places=4)
        self.assertLess(cal.nll(rows, labels, T), cal.nll(rows, labels, 1.0))

    def test_underconfident_rows_get_t_below_1(self):
        rows = [[0.6, 0.4]] * 20
        labels = [0] * 19 + [1]
        self.assertLess(cal.fit_temperature(rows, labels), 1.0)

    def test_ragged_rows(self):
        rows = [[0.9, 0.1], [0.7, 0.1, 0.1, 0.1], [0.2, 0.8]]
        labels = [0, 1, 1]
        T = cal.fit_temperature(rows, labels)
        self.assertTrue(0.05 <= T <= 20.0)


class EceTest(unittest.TestCase):
    def test_perfectly_calibrated_is_zero(self):
        conf = [0.75] * 4
        correct = [True, True, True, False]
        self.assertAlmostEqual(cal.expected_calibration_error(conf, correct), 0.0)

    def test_known_value(self):
        # Bin 0.9-1.0: conf 0.95, accuracy 0.5 -> gap 0.45, weight 2/4.
        # Bin 0.6-0.7: conf 0.65, accuracy 1.0 -> gap 0.35, weight 2/4.
        conf = [0.95, 0.95, 0.65, 0.65]
        correct = [True, False, True, True]
        self.assertAlmostEqual(cal.expected_calibration_error(conf, correct), 0.4)

    def test_confidence_of_one_goes_in_top_bin(self):
        self.assertAlmostEqual(cal.expected_calibration_error([1.0], [True]), 0.0)


if __name__ == "__main__":
    unittest.main()

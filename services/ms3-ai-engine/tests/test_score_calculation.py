import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.sensors import score_sensor_value


class ScoreCalculationTest(unittest.TestCase):
    def test_normal_profile_values_do_not_score_as_anomalies(self):
        normal_values = {
            "rpm": 10800.0,
            "current_a": 40.5,
            "power_kw": 22.0,
            "flow_lpm": 118.0,
            "pressure_bar": 9.8,
            "temperature_c": 83.0,
        }

        for sensor_name, value in normal_values.items():
            with self.subTest(sensor=sensor_name):
                self.assertEqual(score_sensor_value(value, sensor_name), 0.0)

    def test_values_outside_normal_range_score_by_severity(self):
        self.assertGreaterEqual(score_sensor_value(98.0, "temperature_c"), 0.3)
        self.assertGreaterEqual(score_sensor_value(8.0, "vibration_rms"), 1.0)
        self.assertGreaterEqual(score_sensor_value(16000.0, "rpm"), 1.0)


if __name__ == "__main__":
    unittest.main()

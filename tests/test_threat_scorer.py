import unittest
from vision_system.navhat_vision import threat_score

class TestThreatScorer(unittest.TestCase):
    def test_benign_stationary_object(self):
        det = {
            "label": "chair",
            "af": 0.02,
            "vx": 0.0,
            "vy": 0.0,
            "approaching": False,
            "ttc": None
        }
        score = threat_score(det)
        self.assertLess(score, 30.0)

    def test_critical_approaching_vehicle(self):
        det = {
            "label": "car",
            "af": 0.22,
            "vx": 0.0,
            "vy": 120.0,
            "approaching": True,
            "ttc": 2.1
        }
        score = threat_score(det)
        self.assertGreaterEqual(score, 60.0)
        self.assertLessEqual(score, 100.0)

if __name__ == '__main__':
    unittest.main()

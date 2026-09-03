import unittest
import collections
from vision_system.navhat_vision import estimate_ttc

class TestTrackerAlgorithms(unittest.TestCase):
    def test_ttc_approaching_object(self):
        # Growing bounding box area sequence (approaching)
        history = collections.deque([0.05, 0.07, 0.09, 0.12], maxlen=8)
        ttc = estimate_ttc(history, interval=1.0)
        self.assertIsNotNone(ttc)
        self.assertGreater(ttc, 0.0)
        self.assertLess(ttc, 10.0)

    def test_ttc_receding_object(self):
        # Shrinking bounding box area sequence (moving away)
        history = collections.deque([0.15, 0.12, 0.09, 0.06], maxlen=8)
        ttc = estimate_ttc(history, interval=1.0)
        self.assertIsNone(ttc)

    def test_ttc_insufficient_history(self):
        history = collections.deque([0.05, 0.07], maxlen=8)
        ttc = estimate_ttc(history, interval=1.0)
        self.assertIsNone(ttc)

if __name__ == '__main__':
    unittest.main()
